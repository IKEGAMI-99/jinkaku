from pathlib import Path

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
E2B = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E2BMemoryEngine.kt")


def one(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_view_model() -> None:
    text = VM.read_text(encoding="utf-8")
    if "MEMORY_ROLE_ATTRIBUTION_V061" in text:
        print("MEMORY_ROLE_ATTRIBUTION_V061 already applied to JinkakuViewModel")
        return

    text = one(
        text,
        "                    val system = buildSystemPrompt(relevant.map { it.content }, _ui.value.thinkingEnabled)\n",
        "                    val system = buildSystemPrompt(relevant, _ui.value.thinkingEnabled)\n",
        "pass full memory records to prompt builder",
    )

    old = '''    private fun buildSystemPrompt(memories: List<String>, enableThinking: Boolean): String {
        val persona = db.currentPersona()
        val memoryBlock = if (memories.isEmpty()) "(none)" else memories.joinToString("\\n") { "- $it" }
        val reasoning = if (enableThinking) {
            "<|think|>\\nThink carefully before answering, but keep internal reasoning private. Output only the final answer after thinking."
        } else {
            "Answer directly without a hidden thinking/reasoning phase. Do not emit thought or analysis markers."
        }
        return """$reasoning
You are Jinkaku, a persistent local AI with an evolving but coherent personality. Do not blindly agree. Be consistent with durable memories while treating them as fallible context. Reply naturally in the user's language.
Persona state: $persona
Relevant long-term memories:
$memoryBlock""".trimIndent()
    }
'''

    new = '''    // MEMORY_ROLE_ATTRIBUTION_V061: preserve who each memory is about when it is injected.
    private fun memoryOwner(memory: MemoryRecord): String = when {
        memory.type.equals("SELF", ignoreCase = true) || memory.origin.equals("AI_SELF", ignoreCase = true) -> "JINKAKU"
        memory.type.equals("USER", ignoreCase = true) || memory.type.equals("PREFERENCE", ignoreCase = true) || memory.origin.startsWith("USER_", ignoreCase = true) -> "USER"
        memory.type.equals("RELATIONSHIP", ignoreCase = true) -> "RELATIONSHIP"
        memory.type.equals("PROJECT", ignoreCase = true) || memory.origin.equals("PROJECT", ignoreCase = true) -> "PROJECT"
        else -> "CONTEXT"
    }

    private fun buildSystemPrompt(memories: List<MemoryRecord>, enableThinking: Boolean): String {
        val persona = db.currentPersona()
        val memoryBlock = if (memories.isEmpty()) "(none)" else memories.joinToString("\\n") { memory ->
            val owner = memoryOwner(memory)
            "- [owner=$owner type=${memory.type} origin=${memory.origin}] ${memory.content}"
        }
        val reasoning = if (enableThinking) {
            "<|think|>\\nThink carefully before answering, but keep internal reasoning private. Output only the final answer after thinking."
        } else {
            "Answer directly without a hidden thinking/reasoning phase. Do not emit thought or analysis markers."
        }
        return """$reasoning
You are Jinkaku, a persistent local AI with an evolving but coherent personality. Do not blindly agree. Be consistent with durable memories while treating them as fallible context. Reply naturally in the user's language.
Persona state: $persona
Relevant long-term memories (ownership metadata is authoritative):
$memoryBlock
Memory ownership rules:
- owner=USER describes the human user. Never treat it as your own biography, preference, experience, or statement.
- owner=JINKAKU describes you, the assistant.
- owner=RELATIONSHIP describes facts about the user-assistant relationship; do not assign them to only one side unless the content says so.
- owner=PROJECT describes project state or facts, not personal identity.
- If a memory sentence contains first-person words such as I / me / my / 私 / 僕 / 俺, interpret them according to owner metadata rather than the literal pronoun.""".trimIndent()
    }
'''

    text = one(text, old, new, "role-aware system memory block")
    VM.write_text(text, encoding="utf-8")
    print("Applied MEMORY_ROLE_ATTRIBUTION_V061 to JinkakuViewModel")


def patch_extractor() -> None:
    text = E2B.read_text(encoding="utf-8")
    marker = "MEMORY_ROLE_EXTRACTION_V061"
    if marker in text:
        print(f"{marker} already applied to E2BMemoryEngine")
        return

    # E2B originally used a compact one-line declaration. The GPU/MTP LiteRT-LM
    # implementation formats the same constant with spaces and a larger companion
    # object. Patch by locating the Kotlin triple-quoted constant instead of relying
    # on the exact old source line, so both runtimes remain supported.
    anchors = (
        'private const val MEMORY_SYSTEM = """',
        'private const val MEMORY_SYSTEM="""',
    )
    start = -1
    anchor = ""
    for candidate in anchors:
        start = text.find(candidate)
        if start >= 0:
            anchor = candidate
            break
    if start < 0:
        raise RuntimeError("anchor not found: E2B MEMORY_SYSTEM constant")

    body_start = start + len(anchor)
    close = text.find('"""', body_start)
    if close < 0:
        raise RuntimeError("unterminated E2B MEMORY_SYSTEM constant")

    line_start = text.rfind("\n", 0, start) + 1
    indent = text[line_start:start]
    prompt = (
        "You are a local memory extraction worker. Do not chat and do not reveal reasoning. "
        "Each input is explicitly a HUMAN USER message. Extract only durable facts, preferences, project state, "
        "relationship facts, or episodes worth remembering. Ignore transient small talk. Preserve the input language. "
        "Resolve pronouns before storing: when the human user says I / me / my / 私 / 僕 / 俺, write the memory with "
        "an explicit user subject such as The user... / ユーザーは..., never as first-person text. Use type SELF or "
        "origin AI_SELF only when the remembered fact is actually about Jinkaku/the assistant, not merely because the "
        "user spoke in first person. For facts or preferences about the human user, use type USER or PREFERENCE "
        "(or EPISODIC/PROJECT when appropriate) and origin USER_EXPLICIT or USER_INFERRED. Return exactly one JSON "
        "object: {\"memories\":[{\"content\":\"concise memory with explicit subject\",\"type\":\"USER|SELF|RELATIONSHIP|EPISODIC|PREFERENCE|PROJECT\","
        "\"importance\":\"CORE|HIGH|NORMAL|LOW\",\"confidence\":\"EXPLICIT|STRONG_INFERENCE|WEAK_INFERENCE\","
        "\"origin\":\"USER_EXPLICIT|USER_INFERRED|AI_SELF|SYSTEM|PROJECT\",\"tags\":[\"tag\"]}]}. "
        "Use an empty memories array when nothing is worth storing."
    )

    replacement = (
        f'{indent}// {marker}: make the grammatical subject explicit so USER memories cannot be mistaken for assistant self-memory.\n'
        f'{indent}private const val MEMORY_SYSTEM = """{prompt}"""'
    )
    text = text[:line_start] + replacement + text[close + 3:]
    E2B.write_text(text, encoding="utf-8")
    print("Applied MEMORY_ROLE_EXTRACTION_V061 to E2BMemoryEngine")


def main() -> None:
    patch_view_model()
    patch_extractor()


if __name__ == "__main__":
    main()
