from pathlib import Path
import re

UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
ENGINE = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E2BChatEngine.kt")
MARKER = "LIVE_FEEDBACK_V080"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to UI")
        return

    if "import kotlinx.coroutines.delay\n" not in text:
        text = one(
            text,
            "import kotlinx.coroutines.launch\n",
            "import kotlinx.coroutines.delay\nimport kotlinx.coroutines.launch\n",
            "delay import",
        )

    # The old dots were driven by generatedTokens. During hidden Thinking that value
    # is intentionally zero, so the ellipsis looked frozen.
    pattern = re.compile(r"private fun modernTypingLabel\([^\n]*\): String = [^\n]*")
    text, count = pattern.subn(
        'private fun modernTypingLabel(tick: Int): String = "書き込み中" + ".".repeat((tick.mod(3)) + 1) // LIVE_FEEDBACK_V080',
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"typing label function: expected exactly one match, found {count}")

    # Header/status ticker. This anchor is stable across the generated UI patches.
    top_anchor = "    val keyboard = LocalSoftwareKeyboardController.current\n\n    fun dismissIme() {"
    top_replacement = '''    val keyboard = LocalSoftwareKeyboardController.current
    var typingTick by remember { mutableStateOf(0) }

    LaunchedEffect(ui.busy) {
        if (!ui.busy) {
            typingTick = 0
            return@LaunchedEffect
        }
        while (true) {
            delay(360L)
            typingTick = (typingTick + 1) % 3
        }
    }

    fun dismissIme() {'''
    text = one(text, top_anchor, top_replacement, "top-bar typing ticker")

    # Earlier visual patches change the lines around this declaration, so insert by
    # the declaration itself rather than assuming the surrounding source is unchanged.
    chat_match = re.search(r'(?m)^(\s*)val showTypingBubble = [^\n]+\n', text)
    if chat_match is None:
        raise RuntimeError("chat typing ticker: showTypingBubble declaration not found")
    indent = chat_match.group(1)
    chat_ticker = (
        chat_match.group(0)
        + f'{indent}var typingTick by remember {{ mutableStateOf(0) }}\n\n'
        + f'{indent}LaunchedEffect(showTypingBubble) {{\n'
        + f'{indent}    if (!showTypingBubble) {{\n'
        + f'{indent}        typingTick = 0\n'
        + f'{indent}        return@LaunchedEffect\n'
        + f'{indent}    }}\n'
        + f'{indent}    while (true) {{\n'
        + f'{indent}        delay(360L)\n'
        + f'{indent}        typingTick = (typingTick + 1) % 3\n'
        + f'{indent}    }}\n'
        + f'{indent}}}\n'
    )
    text = text[:chat_match.start()] + chat_ticker + text[chat_match.end():]

    typing_calls = text.count("modernTypingLabel(telemetry.generatedTokens)")
    if typing_calls < 1:
        raise RuntimeError("typing label calls: telemetry.generatedTokens call not found")
    text = text.replace("modernTypingLabel(telemetry.generatedTokens)", "modernTypingLabel(typingTick)")

    UI.write_text(text, encoding="utf-8")
    print("Applied V080 UI: independent animated ellipsis")


def patch_engine() -> None:
    text = ENGINE.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to E2BChatEngine")
        return

    reset_anchor = '''        InferenceTelemetry.reset(maxContext, "PREFILL", "GPU+MTP")
        if (thinkingActive) emit(GenerationEvent.Thinking)

        var accepted = ""'''
    reset_replacement = '''        InferenceTelemetry.reset(maxContext, "PREFILL", "GPU+MTP")
        val estimatedPromptTokens = estimateTokenCount(cleanSystem + "\\n" + turnPrompt)
            .coerceIn(1, maxContext)
        val livePhase = if (thinkingActive) "THINKING" else "DECODE"
        InferenceTelemetry.updateLiteRt(
            contextUsed = estimatedPromptTokens,
            contextMax = maxContext,
            phase = livePhase,
            promptTokens = estimatedPromptTokens,
            backend = "GPU+MTP"
        )
        if (thinkingActive) emit(GenerationEvent.Thinking)

        var accepted = ""'''
    text = one(text, reset_anchor, reset_replacement, "initial live context estimate")

    vars_anchor = '''            var generatedPieces = 0
            var contextUsed = 0
            var prefillTokS = 0.0'''
    vars_replacement = '''            var generatedPieces = 0
            var contextUsed = estimatedPromptTokens
            var lastLiveContextUsed = estimatedPromptTokens
            var prefillTokS = 0.0'''
    text = one(text, vars_anchor, vars_replacement, "live context variables")

    monitor_anchor = '''                    val telemetryMonitor = launch {
                        val livePhase = if (thinkingActive) "THINKING" else "DECODE"
                        while (isActive) {
                            delay(TELEMETRY_INTERVAL_MS)
                            runCatching { conversation.getTokenCount() }
                                .onSuccess { used ->
                                    contextUsed = used.coerceIn(0, maxContext)
                                    InferenceTelemetry.updateLiteRt(
                                        contextUsed = contextUsed,
                                        contextMax = maxContext,
                                        phase = livePhase,
                                        backend = "GPU+MTP"
                                    )
                                }
                        }
                    }'''
    monitor_replacement = '''                    val telemetryMonitor = launch {
                        while (isActive) {
                            delay(TELEMETRY_INTERVAL_MS)
                            val actualUsed = runCatching { conversation.getTokenCount() }
                                .getOrNull()
                                ?.coerceIn(0, maxContext)
                                ?: 0

                            // LiteRT-LM can leave getTokenCount() unchanged while
                            // sendMessageAsync owns the conversation. Prefer the real
                            // count whenever it advances, otherwise keep the UI moving
                            // with a conservative estimate. The exact count replaces it
                            // immediately after generation completes.
                            val fallbackStep = (
                                LIVE_CONTEXT_FALLBACK_TOK_S * TELEMETRY_INTERVAL_MS / 1000.0
                            ).toInt().coerceAtLeast(1)
                            val nextUsed = if (actualUsed > lastLiveContextUsed) {
                                actualUsed
                            } else {
                                (lastLiveContextUsed + fallbackStep).coerceAtMost(maxContext)
                            }
                            lastLiveContextUsed = nextUsed
                            contextUsed = nextUsed
                            InferenceTelemetry.updateLiteRt(
                                contextUsed = contextUsed,
                                contextMax = maxContext,
                                phase = livePhase,
                                promptTokens = estimatedPromptTokens,
                                backend = "GPU+MTP"
                            )
                        }
                    }'''
    text = one(text, monitor_anchor, monitor_replacement, "live telemetry monitor")

    ensure_anchor = "    @Synchronized\n    private fun ensureEngine(model: File, maxContext: Int): Engine {"
    helper = '''    // Fast UI-only estimate. CJK characters are counted roughly one token
    // each; ASCII runs use about four chars/token. Exact LiteRT count wins at end.
    private fun estimateTokenCount(value: String): Int {
        var tokens = 0
        var asciiRun = 0

        fun flushAscii() {
            if (asciiRun > 0) {
                tokens += (asciiRun + 3) / 4
                asciiRun = 0
            }
        }

        value.forEach { ch ->
            when {
                ch.isWhitespace() -> flushAscii()
                ch.code < 128 -> asciiRun++
                else -> {
                    flushAscii()
                    tokens++
                }
            }
        }
        flushAscii()
        return tokens.coerceAtLeast(1)
    }

    @Synchronized
    private fun ensureEngine(model: File, maxContext: Int): Engine {'''
    text = one(text, ensure_anchor, helper, "token estimate helper")

    constants_anchor = '''        private const val REPEAT_SIMILARITY_THRESHOLD = 0.72
        private const val TELEMETRY_INTERVAL_MS = 400L
    }'''
    constants_replacement = '''        private const val REPEAT_SIMILARITY_THRESHOLD = 0.72
        private const val TELEMETRY_INTERVAL_MS = 250L
        private const val LIVE_CONTEXT_FALLBACK_TOK_S = 14.0
        private const val LIVE_FEEDBACK_V080 = true
    }'''
    text = one(text, constants_anchor, constants_replacement, "live telemetry constants")

    ENGINE.write_text(text, encoding="utf-8")
    print("Applied V080 engine: live context updates during Thinking/Decode")


def main() -> None:
    patch_ui()
    patch_engine()
    print("Applied LIVE_FEEDBACK_V080")


if __name__ == "__main__":
    main()
