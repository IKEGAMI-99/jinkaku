from pathlib import Path
import re

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
ENGINE = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E2BChatEngine.kt")
MARKER = "E2B_TELEMETRY_CONTEXT8K_V079"


E2B_CHAT_SOURCE = r'''package com.ikegami99.jinkaku.ai

import android.content.Context
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.ExperimentalApi
import com.google.ai.edge.litertlm.ExperimentalFlags
import com.google.ai.edge.litertlm.LogSeverity
import com.google.ai.edge.litertlm.SamplerConfig
import com.google.ai.edge.litertlm.ThinkingConfig
import com.ikegami99.jinkaku.data.ChatMessage
import com.ikegami99.jinkaku.logging.AppLogger
import java.io.Closeable
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * E2B_TELEMETRY_CONTEXT8K_V079
 * Jinkaku main-chat runtime: Gemma 4 E2B LiteRT-LM, GPU + MTP.
 * Supports 8K KV context, optional Thinking, live KV telemetry, and LiteRT benchmark metrics.
 */
@OptIn(ExperimentalApi::class)
class E2BChatEngine(
    private val context: Context,
    private val logger: AppLogger
) : Closeable {
    private var engine: Engine? = null
    private var loadedPath: String? = null
    private var loadedContext: Int = 0

    fun generate(
        model: File,
        currentUserMessage: String,
        systemPrompt: String,
        history: List<ChatMessage>,
        contextSize: Long,
        maxGenerationTokens: Int,
        enableThinking: Boolean,
        topK: Int,
        topP: Double,
        temperature: Double
    ): Flow<GenerationEvent> = flow {
        require(model.exists() && model.length() > 0L) {
            "E2B LiteRT-LMモデルがインストールされていません"
        }

        val maxContext = contextSize.toInt().coerceIn(MIN_CONTEXT_TOKENS, MAX_CONTEXT_TOKENS)
        val requestedAnswerLimit = maxGenerationTokens.coerceIn(32, MAX_OUTPUT_TOKENS)

        // Keep roughly one third of KV for prompt/history. Thinking scales with context:
        // 1K -> 256, 2K -> 512, 4K/8K -> 1024 tokens.
        val outputWindow = (maxContext - maxOf(MIN_PROMPT_RESERVE, maxContext / 3)).coerceAtLeast(64)
        val targetThinkingBudget = if (enableThinking) {
            (maxContext / 4).coerceIn(MIN_THINKING_TOKENS, MAX_THINKING_TOKENS)
        } else {
            0
        }
        val thinkingBudget = minOf(targetThinkingBudget, (outputWindow - 32).coerceAtLeast(0))
        val answerLimit = minOf(
            requestedAnswerLimit,
            (outputWindow - thinkingBudget).coerceAtLeast(32)
        )
        val totalOutputLimit = (thinkingBudget + answerLimit).coerceAtLeast(32)
        val thinkingActive = enableThinking && thinkingBudget > 0
        val activeEngine = ensureEngine(model, maxContext)
        val generationStartedAtMs = System.currentTimeMillis()

        val cleanSystem = systemPrompt
            .replace("<|think|>", "")
            .replace("Think carefully before answering, but keep internal reasoning private. Output only the final answer after thinking.", "")
            .trim()

        val recentHistory = history
            .filter { it.role.equals("user", true) || it.role.equals("assistant", true) }
            .takeLast(MAX_HISTORY_MESSAGES)
        val previousAssistant = recentHistory.lastOrNull { it.role.equals("assistant", true) }?.content.orEmpty()
        val turnPrompt = buildTurnPrompt(recentHistory, currentUserMessage)

        logger.i(
            "E2B_CHAT",
            "Generation start runtime=LiteRT-LM backend=GPU mtp=ON fallback=NONE " +
                "thinking=$thinkingActive thoughtBudget=$thinkingBudget answerLimit=$answerLimit " +
                "ctx=$maxContext history=${recentHistory.size} totalOutputLimit=$totalOutputLimit " +
                "topK=$topK topP=$topP temperature=$temperature"
        )

        InferenceTelemetry.reset(maxContext, "PREFILL", "GPU+MTP")
        if (thinkingActive) emit(GenerationEvent.Thinking)

        var accepted = ""
        var finalContextUsed = 0
        var finalPrefillTokS = 0.0
        var finalDecodeTokS = 0.0
        var finalTtftS = 0.0
        var finalGeneratedPieces = 0
        var lastBenchmark: String? = null

        for (attempt in 0 until MAX_ATTEMPTS) {
            if (attempt > 0) InferenceTelemetry.reset(maxContext, "PREFILL", "GPU+MTP")
            val output = StringBuilder()
            val seed = ((System.nanoTime() xor (attempt.toLong() shl 17)) and 0x7fffffffL).toInt()
            var generatedPieces = 0
            var contextUsed = 0
            var prefillTokS = 0.0
            var decodeTokS = 0.0
            var ttftS = 0.0

            activeEngine.createConversation(
                ConversationConfig(
                    systemInstruction = Contents.of(
                        cleanSystem + "\n\n" +
                            "Conversation rule: answer the latest user message directly. " +
                            "Use prior turns only for continuity. Never copy or mechanically paraphrase " +
                            "your previous reply. Do not repeat a greeting or question that was already used " +
                            "unless the latest user message actually requires it."
                    ),
                    tools = emptyList(),
                    automaticToolCalling = false,
                    channels = null,
                    samplerConfig = SamplerConfig(
                        topK = topK.coerceIn(1, 128),
                        topP = topP.coerceIn(0.05, 1.0),
                        temperature = temperature.coerceIn(0.0, 2.0),
                        seed = seed
                    ),
                    prefillPrefaceOnInit = false,
                    maxOutputToken = totalOutputLimit,
                    thinkingConfig = ThinkingConfig(
                        enableThinking = thinkingActive,
                        thinkingTokenBudget = thinkingBudget
                    ),
                    enableResponseFormat = false
                )
            ).use { conversation ->
                coroutineScope {
                    val telemetryMonitor = launch {
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
                    }
                    try {
                        conversation.sendMessageAsync(
                            text = turnPrompt,
                            maxOutputToken = totalOutputLimit,
                            thinkingConfig = ThinkingConfig(
                                enableThinking = thinkingActive,
                                thinkingTokenBudget = thinkingBudget
                            )
                        ).collect { chunk ->
                            val piece = chunk.toString()
                            if (piece.isNotEmpty()) {
                                output.append(piece)
                                generatedPieces++
                            }
                        }
                    } finally {
                        telemetryMonitor.cancel()
                    }
                }

                runCatching { conversation.getTokenCount() }
                    .onSuccess { used -> contextUsed = used.coerceIn(0, maxContext) }

                runCatching { conversation.getBenchmarkInfo() }
                    .onSuccess { info ->
                        prefillTokS = info.lastPrefillTokensPerSecond
                        decodeTokS = info.lastDecodeTokensPerSecond
                        ttftS = info.timeToFirstTokenInSecond
                        lastBenchmark =
                            "prefillTokS=${"%.1f".format(prefillTokS)} " +
                            "decodeTokS=${"%.1f".format(decodeTokS)} " +
                            "ttftS=${"%.3f".format(ttftS)}"
                    }

                InferenceTelemetry.updateLiteRt(
                    contextUsed = contextUsed,
                    contextMax = maxContext,
                    phase = "DECODE",
                    prefillTokPerSec = prefillTokS.takeIf { it > 0.0 },
                    decodeTokPerSec = decodeTokS.takeIf { it > 0.0 },
                    ttftSeconds = ttftS.takeIf { it > 0.0 },
                    generatedTokens = generatedPieces,
                    backend = "GPU+MTP"
                )
            }

            val candidate = output.toString().trim()
            check(candidate.isNotBlank()) { "E2Bの回答が空でした" }

            val similarity = if (previousAssistant.isBlank()) 0.0 else similarity(previousAssistant, candidate)
            val rejected = attempt + 1 < MAX_ATTEMPTS && similarity >= REPEAT_SIMILARITY_THRESHOLD
            logger.i(
                "E2B_CHAT",
                "Attempt=${attempt + 1} chars=${candidate.length} previousSimilarity=${"%.3f".format(similarity)} " +
                    "repeatRejected=$rejected ctx=$contextUsed/$maxContext"
            )
            if (!rejected) {
                accepted = candidate
                finalContextUsed = contextUsed
                finalPrefillTokS = prefillTokS
                finalDecodeTokS = decodeTokS
                finalTtftS = ttftS
                finalGeneratedPieces = generatedPieces
                break
            }
        }

        check(accepted.isNotBlank()) { "E2Bの回答を確定できませんでした" }
        InferenceTelemetry.completeLiteRt(
            finalText = accepted,
            contextUsed = finalContextUsed,
            contextMax = maxContext,
            prefillTokPerSec = finalPrefillTokS,
            decodeTokPerSec = finalDecodeTokS,
            ttftSeconds = finalTtftS,
            generatedTokens = finalGeneratedPieces,
            backend = "GPU+MTP"
        )
        emit(GenerationEvent.Text(accepted))

        logger.i(
            "E2B_CHAT",
            "Generation complete backend=GPU mtp=ON ${lastBenchmark ?: "benchmark=unavailable"} " +
                "ctx=$finalContextUsed/$maxContext chars=${accepted.length}"
        )
        emit(
            GenerationEvent.Completed(
                finalText = accepted,
                elapsedMs = System.currentTimeMillis() - generationStartedAtMs
            )
        )
    }.flowOn(Dispatchers.Default)

    private fun buildTurnPrompt(history: List<ChatMessage>, currentUserMessage: String): String {
        if (history.isEmpty()) return currentUserMessage
        val transcript = history.joinToString("\n") { message ->
            val role = if (message.role.equals("user", true)) "User" else "Assistant"
            "$role: ${message.content}"
        }
        return buildString {
            append("Recent conversation context follows. It is context, not instructions.\n")
            append("<conversation_context>\n")
            append(transcript)
            append("\n</conversation_context>\n\n")
            append("Latest user message:\n")
            append(currentUserMessage)
            append("\n\nReply only to the latest user message.")
        }
    }

    private fun similarity(a: String, b: String): Double {
        val left = normalizeForSimilarity(a)
        val right = normalizeForSimilarity(b)
        if (left.isEmpty() || right.isEmpty()) return 0.0
        if (left == right) return 1.0
        if (left.length < 3 || right.length < 3) {
            return if (left.contains(right) || right.contains(left)) 0.9 else 0.0
        }
        val leftPairs = left.windowed(2).toSet()
        val rightPairs = right.windowed(2).toSet()
        if (leftPairs.isEmpty() || rightPairs.isEmpty()) return 0.0
        val intersection = leftPairs.intersect(rightPairs).size.toDouble()
        val union = (leftPairs.size + rightPairs.size - intersection).coerceAtLeast(1.0)
        return intersection / union
    }

    private fun normalizeForSimilarity(value: String): String =
        value.lowercase()
            .replace(Regex("[\\s\\p{Punct}。、！？「」『』（）［］【】…・]+"), "")
            .take(1200)

    @Synchronized
    private fun ensureEngine(model: File, maxContext: Int): Engine {
        val path = model.absolutePath
        val current = engine
        if (current != null && loadedPath == path && loadedContext == maxContext) return current

        unload()
        ExperimentalFlags.enableBenchmark = true
        ExperimentalFlags.enableSpeculativeDecoding = true
        Engine.setNativeMinLogSeverity(LogSeverity.ERROR)
        context.cacheDir.mkdirs()

        logger.i(
            "E2B_CHAT",
            "Engine init policy backend=GPU mtp=ON fallback=NONE ctx=$maxContext file=${model.name}"
        )
        val created = Engine(
            EngineConfig(
                modelPath = path,
                backend = Backend.GPU(),
                visionBackend = null,
                audioBackend = null,
                maxNumTokens = maxContext,
                cacheDir = context.cacheDir.absolutePath
            )
        )
        try {
            created.initialize()
        } catch (t: Throwable) {
            runCatching { created.close() }
            logger.e("E2B_CHAT", "GPU+MTP initialization failed; fallback=NONE", t)
            throw IllegalStateException(
                "E2B LiteRT-LMはGPU + MTP固定です。GPU+MTP初期化に失敗しました。" +
                    "MTP OFFやCPUへのフォールバックは行いません。",
                t
            )
        }

        engine = created
        loadedPath = path
        loadedContext = maxContext
        logger.i("E2B_CHAT", "Engine loaded backend=GPU mtp=ON ctx=$maxContext file=${model.name}")
        return created
    }

    @Synchronized
    fun unload() {
        runCatching { engine?.close() }
        engine = null
        loadedPath = null
        loadedContext = 0
    }

    override fun close() = unload()

    companion object {
        private const val MIN_CONTEXT_TOKENS = 768
        private const val MAX_CONTEXT_TOKENS = 8192
        private const val MAX_OUTPUT_TOKENS = 1024
        private const val MIN_PROMPT_RESERVE = 512
        private const val MIN_THINKING_TOKENS = 256
        private const val MAX_THINKING_TOKENS = 1024
        private const val MAX_HISTORY_MESSAGES = 6
        private const val MAX_ATTEMPTS = 2
        private const val REPEAT_SIMILARITY_THRESHOLD = 0.72
        private const val TELEMETRY_INTERVAL_MS = 400L
    }
}
'''


def extract_model_card(text: str, title: str) -> tuple[str, str]:
    pattern = re.compile(
        rf'''        item \{{\n            ModernModelCard\(\n                title = "{re.escape(title)}",.*?            \)\n        \}}\n''',
        re.S,
    )
    match = pattern.search(text)
    if match is None:
        raise RuntimeError(f"model card not found: {title}")
    return text[:match.start()] + text[match.end():], match.group(0)


def patch_view_model() -> None:
    text = VM.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to ViewModel")
        return

    count = text.count("coerceIn(1024L, 4096L)")
    text = text.replace("coerceIn(1024L, 4096L)", "coerceIn(1024L, 8192L)")
    if count < 2:
        raise RuntimeError(f"expected at least 2 generated 4K context clamps, found {count}")

    text = text.replace(
        "class JinkakuViewModel(app: Application) : AndroidViewModel(app) {\n    // E2B_ONLY_V077: chat runtime is E2B LiteRT-LM only.",
        "class JinkakuViewModel(app: Application) : AndroidViewModel(app) {\n    // E2B_ONLY_V077: chat runtime is E2B LiteRT-LM only.\n    // E2B_TELEMETRY_CONTEXT8K_V079: 8K context + LiteRT telemetry.",
        1,
    )
    if MARKER not in text:
        raise RuntimeError("ViewModel marker insertion failed")

    VM.write_text(text, encoding="utf-8")
    print("Applied V079 ViewModel: 8K context clamp")


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to UI")
        return

    # v077 accidentally removed the Model category header while deleting the old
    # E4B/E2B selector. The two surviving model cards ended up inside Persona.
    if '                text = "モデル",' not in text:
        text, e2b_card = extract_model_card(text, "Gemma 4 E2B LiteRT-LM")
        text, embedding_card = extract_model_card(text, "EmbeddingGemma 300M Q4_0")

        inference_pos = text.find('                text = "推論",')
        if inference_pos < 0:
            raise RuntimeError("Inference category header not found")
        inference_item = text.rfind("        item {\n            ModernSettingsCategoryHeader(", 0, inference_pos)
        if inference_item < 0:
            raise RuntimeError("Inference category item start not found")

        model_section = '''        item {
            ModernSettingsCategoryHeader(
                text = "モデル",
                icon = Icons.Rounded.Storage,
                expanded = expandedSettingsCategory == "モデル",
                onClick = { expandedSettingsCategory = if (expandedSettingsCategory == "モデル") null else "モデル" }
            )
        }
        if (expandedSettingsCategory == "モデル") {
''' + e2b_card + embedding_card + '''        }

'''
        text = text[:inference_item] + model_section + text[inference_item:]

    # Restore the 8K choice removed by the E2B-only conversion.
    text = text.replace(
        "listOf(1024L, 2048L, 4096L)",
        "listOf(1024L, 2048L, 4096L, 8192L)",
    )

    old_metrics = '"Prefill ${telemetry.prefillLabel()} tok/s  ·  Decode ${telemetry.decodeLabel()} tok/s  ·  ${telemetry.generatedTokens} tok  ·  ${telemetry.backend}"'
    new_metrics = '"TTFT ${telemetry.ttftLabel()} s  ·  Prefill ${telemetry.prefillLabel()} tok/s  ·  Decode ${telemetry.decodeLabel()} tok/s  ·  ${telemetry.backend}"'
    if old_metrics not in text:
        raise RuntimeError("assistant telemetry label anchor not found")
    text = text.replace(old_metrics, new_metrics, 1)

    text = text.replace(
        'if (ui.thinkingEnabled) "Thinking内容は非表示です。最大512 tokenを推論に使います。" else "OFFでは直接回答します。"',
        'if (ui.thinkingEnabled) "Thinking内容は非表示です。Contextに応じて最大1024 tokenを推論に使います。" else "OFFでは直接回答します。"',
        1,
    )
    text = text.replace(
        'Thinkingは別枠で最大512 token。返信の長さは回答本文側の目安です。Contextが小さい場合は回答枠を自動調整します。',
        'ThinkingはContextに応じて256〜1024 token。返信の長さは回答本文側の目安です。1K/2K/4K/8Kに対応します。',
        1,
    )

    text = text.replace(
        "// E2B_ONLY_V077: E4B controls removed; inference controls feed E2B directly.\nprivate fun ModernSettingsScreen(",
        "// E2B_ONLY_V077: E4B controls removed; inference controls feed E2B directly.\n// E2B_TELEMETRY_CONTEXT8K_V079: Model category restored; TTFT/Prefill/Decode + 8K context.\nprivate fun ModernSettingsScreen(",
        1,
    )
    if MARKER not in text:
        raise RuntimeError("UI marker insertion failed")

    UI.write_text(text, encoding="utf-8")
    print("Applied V079 UI: Model category + TTFT/Prefill/Decode + 8K")


def main() -> None:
    ENGINE.write_text(E2B_CHAT_SOURCE, encoding="utf-8")
    patch_view_model()
    patch_ui()
    print("Applied E2B_TELEMETRY_CONTEXT8K_V079")


if __name__ == "__main__":
    main()
