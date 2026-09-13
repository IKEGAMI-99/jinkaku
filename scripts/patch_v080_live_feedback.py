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

    if "import androidx.compose.animation.core.animateFloatAsState\n" not in text:
        text = one(
            text,
            "import android.content.Intent\n",
            "import android.content.Intent\nimport androidx.compose.animation.core.animateFloatAsState\n",
            "animateFloatAsState import",
        )
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

    chat_anchor = '''    val listState = rememberLazyListState()
    val showTypingBubble = ui.busy && telemetry.phase in setOf("PREFILL", "THINKING", "DECODE")

    fun submit() {'''
    chat_replacement = '''    val listState = rememberLazyListState()
    val showTypingBubble = ui.busy && telemetry.phase in setOf("PREFILL", "THINKING", "DECODE")
    var typingTick by remember { mutableStateOf(0) }

    LaunchedEffect(showTypingBubble) {
        if (!showTypingBubble) {
            typingTick = 0
            return@LaunchedEffect
        }
        while (true) {
            delay(360L)
            typingTick = (typingTick + 1) % 3
        }
    }

    fun submit() {'''
    text = one(text, chat_anchor, chat_replacement, "chat typing ticker")

    typing_calls = text.count("modernTypingLabel(telemetry.generatedTokens)")
    if typing_calls < 2:
        raise RuntimeError(f"typing label calls: expected at least 2, found {typing_calls}")
    text = text.replace("modernTypingLabel(telemetry.generatedTokens)", "modernTypingLabel(typingTick)")

    context_anchor = '''    val remaining = (max - used).coerceAtLeast(0)
    val fraction = if (max > 0) used.toFloat() / max else 0f

    Card('''
    context_replacement = '''    val remaining = (max - used).coerceAtLeast(0)
    val fraction = if (max > 0) used.toFloat() / max else 0f
    val animatedFraction by animateFloatAsState(
        targetValue = fraction.coerceIn(0f, 1f),
        label = "contextMeter"
    )

    Card('''
    text = one(text, context_anchor, context_replacement, "context progress animation")

    text = one(
        text,
        "                progress = { fraction.coerceIn(0f, 1f) },",
        "                progress = { animatedFraction },",
        "context progress value",
    )

    UI.write_text(text, encoding="utf-8")
    print("Applied V080 UI: independent animated ellipsis + smooth live context meter")


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

                            // LiteRT-LM may keep getTokenCount() unchanged while sendMessageAsync
                            // owns the conversation. Keep the UI alive with a conservative estimate,
                            // then replace it with the exact count once LiteRT exposes it.
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

    helper_anchor = '''    private fun normalizeForSimilarity(value: String): String =
        value.lowercase()
            .replace(Regex("[\\\\s\\\\p{Punct}。、！？「」『』（）［］【】…・]+"), "")
            .take(1200)

    @Synchronized'''
    helper_replacement = '''    private fun normalizeForSimilarity(value: String): String =
        value.lowercase()
            .replace(Regex("[\\\\s\\\\p{Punct}。、！？「」『』（）［］【】…・]+"), "")
            .take(1200)

    // Fast UI-only estimate. Japanese/CJK characters are counted roughly one token
    // each, while ASCII runs use ~4 chars/token. The exact LiteRT count wins at end.
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

    @Synchronized'''
    text = one(text, helper_anchor, helper_replacement, "token estimate helper")

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
