from pathlib import Path

PATCH = Path("scripts/patch_v070_e2b_import_version.py")
text = PATCH.read_text(encoding="utf-8")
changed = False

# 1) There are two E4B READY states after the monologue patch. Only the first belongs
# to normal send(), which is where activeMainEngine exists.
old_ready = '''    text = one(
        text,
        '                        runtimeStatus = "E4B READY"\\n',
        '                        runtimeStatus = if (activeMainEngine == "E2B") "E2B GPU READY" else "E4B READY"\\n',
        "dynamic ready status",
    )
'''
new_ready = '''    ready_anchor = '                        runtimeStatus = "E4B READY"\\n'
    if ready_anchor not in text:
        raise RuntimeError("normal ready status anchor not found")
    # Normal send() appears before monologue generation. Leave monologue E4B-only for now.
    text = text.replace(
        ready_anchor,
        '                        runtimeStatus = if (activeMainEngine == "E2B") "E2B GPU READY" else "E4B READY"\\n',
        1,
    )
'''
if old_ready in text:
    text = text.replace(old_ready, new_ready, 1)
    changed = True

# 2) V072 replaces the old V071 router script, so it must not require V071's marker.
# Insert the main-engine helpers immediately before importE4B(), which is a stable ViewModel anchor.
old_helper = '''    helper_anchor = "    // MODEL_IMPORT_ROUTER_V071: do not trust the UI route alone. Detect LiteRT files at the ViewModel boundary.\\n"
    if helper_anchor not in text:
        raise RuntimeError("v071 import router helper marker not found")
'''
new_helper = '''    helper_anchor = "    fun importE4B(uri: Uri) {\\n"
    if helper_anchor not in text:
        raise RuntimeError("importE4B helper insertion anchor not found")
'''
if old_helper in text:
    text = text.replace(old_helper, new_helper, 1)
    changed = True

# 3) Drop the obsolete E4B->memory-router rewrite entirely. The E2B card has its own picker,
# and importE2B() now activates E2B as the main-chat engine while sharing the same model file
# with memory maintenance. This avoids routing a main-chat selection into a memory-only role.
route_start = text.find("    old_route = '''        if (selectedName.endsWith(\".litertlm\", ignoreCase = true)) {")
if route_start >= 0:
    route_end_marker = '    text = one(text, old_route, new_route, "main card LiteRT route")\n\n'
    route_end = text.find(route_end_marker, route_start)
    if route_end < 0:
        raise RuntimeError("obsolete V071 route end anchor not found")
    route_end += len(route_end_marker)
    text = text[:route_start] + text[route_end:]
    changed = True

# 4) GenerationEvent.Completed is shared with E4B and requires elapsedMs.
# Start the timer before Engine/prefill work so the E2B completion event carries the real
# end-to-end latency instead of a dummy zero value.
old_timer_anchor = '''        val maxContext = contextSize.toInt().coerceIn(MIN_CONTEXT_TOKENS, MAX_CONTEXT_TOKENS)
        val outputLimit = maxGenerationTokens.coerceIn(32, MAX_OUTPUT_TOKENS)
        val activeEngine = ensureEngine(model, maxContext)
'''
new_timer_anchor = '''        val maxContext = contextSize.toInt().coerceIn(MIN_CONTEXT_TOKENS, MAX_CONTEXT_TOKENS)
        val outputLimit = maxGenerationTokens.coerceIn(32, MAX_OUTPUT_TOKENS)
        val generationStartedAtMs = System.currentTimeMillis()
        val activeEngine = ensureEngine(model, maxContext)
'''
if old_timer_anchor in text:
    text = text.replace(old_timer_anchor, new_timer_anchor, 1)
    changed = True

old_completed = '        emit(GenerationEvent.Completed(clean))\n'
new_completed = '''        emit(
            GenerationEvent.Completed(
                finalText = clean,
                elapsedMs = System.currentTimeMillis() - generationStartedAtMs
            )
        )
'''
if old_completed in text:
    text = text.replace(old_completed, new_completed, 1)
    changed = True

if not changed:
    if (
        "importE4B helper insertion anchor not found" in text
        and "normal ready status anchor not found" in text
        and "generationStartedAtMs" in text
        and "elapsedMs = System.currentTimeMillis() - generationStartedAtMs" in text
    ):
        print("V072 compatibility fixes already applied")
    else:
        raise RuntimeError("No V072 compatibility anchors changed")
else:
    PATCH.write_text(text, encoding="utf-8")
    print("Applied V072 fixes: routing compatibility + real E2B completion elapsedMs")
