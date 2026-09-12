from pathlib import Path
import re

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
E2B_CHAT = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E2BChatEngine.kt")
MARKER = "E2B_ONLY_V077"


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
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn

/**
 * E2B_ONLY_V077
 * Jinkaku's only chat runtime: Gemma 4 E2B LiteRT-LM, GPU + MTP.
 *
 * Recent history is intentionally kept out of the system instruction. It is supplied as
 * bounded conversation context in the user turn so previous assistant wording does not gain
 * system-level weight. A lightweight similarity guard retries once when the model collapses
 * into a near-copy of its previous reply.
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
        topK: Int,
        topP: Double,
        temperature: Double
    ): Flow<GenerationEvent> = flow {
        require(model.exists() && model.length() > 0L) {
            "E2B LiteRT-LMモデルがインストールされていません"
        }

        val maxContext = contextSize.toInt().coerceIn(MIN_CONTEXT_TOKENS, MAX_CONTEXT_TOKENS)
        val outputLimit = maxGenerationTokens.coerceIn(32, MAX_OUTPUT_TOKENS)
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
            "Generation start runtime=LiteRT-LM backend=GPU mtp=ON fallback=NONE thinking=OFF " +
                "ctx=$maxContext history=${recentHistory.size} outputLimit=$outputLimit " +
                "topK=$topK topP=$topP temperature=$temperature"
        )

        emit(GenerationEvent.Thinking)

        var accepted = ""
        var lastBenchmark: String? = null
        for (attempt in 0 until MAX_ATTEMPTS) {
            val output = StringBuilder()
            val seed = ((System.nanoTime() xor (attempt.toLong() shl 17)) and 0x7fffffffL).toInt()

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
                    maxOutputToken = outputLimit,
                    thinkingConfig = ThinkingConfig(
                        enableThinking = false,
                        thinkingTokenBudget = 0
                    ),
                    enableResponseFormat = false
                )
            ).use { conversation ->
                conversation.sendMessageAsync(
                    text = turnPrompt,
                    maxOutputToken = outputLimit,
                    thinkingConfig = ThinkingConfig(
                        enableThinking = false,
                        thinkingTokenBudget = 0
                    )
                ).collect { chunk ->
                    val piece = chunk.toString()
                    if (piece.isNotEmpty()) output.append(piece)
                }

                runCatching { conversation.getBenchmarkInfo() }
                    .onSuccess { info ->
                        lastBenchmark =
                            "prefillTokS=${"%.1f".format(info.lastPrefillTokensPerSecond)} " +
                            "decodeTokS=${"%.1f".format(info.lastDecodeTokensPerSecond)} " +
                            "ttftS=${"%.3f".format(info.timeToFirstTokenInSecond)}"
                    }
            }

            val candidate = output.toString().trim()
            check(candidate.isNotBlank()) { "E2Bの回答が空でした" }

            val similarity = if (previousAssistant.isBlank()) 0.0 else similarity(previousAssistant, candidate)
            val rejected = attempt + 1 < MAX_ATTEMPTS && similarity >= REPEAT_SIMILARITY_THRESHOLD
            logger.i(
                "E2B_CHAT",
                "Attempt=${attempt + 1} chars=${candidate.length} previousSimilarity=${"%.3f".format(similarity)} " +
                    "repeatRejected=$rejected"
            )
            if (!rejected) {
                accepted = candidate
                break
            }
        }

        check(accepted.isNotBlank()) { "E2Bの回答を確定できませんでした" }
        emit(GenerationEvent.Text(accepted))

        logger.i(
            "E2B_CHAT",
            "Generation complete backend=GPU mtp=ON ${lastBenchmark ?: ""} chars=${accepted.length}"
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
        private const val MAX_CONTEXT_TOKENS = 4096
        private const val MAX_OUTPUT_TOKENS = 1024
        private const val MAX_HISTORY_MESSAGES = 6
        private const val MAX_ATTEMPTS = 2
        private const val REPEAT_SIMILARITY_THRESHOLD = 0.72
    }
}
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_view_model() -> None:
    text = VM.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to ViewModel")
        return

    if "val topP:" not in text:
        text = replace_once(
            text,
            "    val temperature: Float = 1.0f,\n",
            "    val temperature: Float = 1.0f,\n    val topP: Float = 0.90f,\n",
            "UiState topP",
        )
        text = replace_once(
            text,
            '            temperature = prefs.getFloat("temperature", 1.0f).coerceIn(0.1f, 1.5f)\n',
            '            temperature = prefs.getFloat("temperature", 1.0f).coerceIn(0.1f, 1.5f),\n'
            '            topP = prefs.getFloat("top_p", 0.90f).coerceIn(0.05f, 1.0f)\n',
            "initial topP preference",
        )

    if "fun setTopP(" not in text:
        setter_anchor = re.search(
            r'''    fun setTemperature\(value: Float\) \{.*?^    \}\n\n''',
            text,
            re.S | re.M,
        )
        if setter_anchor is None:
            raise RuntimeError("setTemperature anchor not found")
        top_p_setter = '''    fun setTopP(value: Float) {
        if (_ui.value.busy || anyModelImporting()) return
        val safe = value.coerceIn(0.05f, 1.0f)
        prefs.edit().putFloat("top_p", safe).apply()
        _ui.value = _ui.value.copy(topP = safe)
        logger.i("E2B_CHAT", "Sampling Top-P=$safe")
    }

'''
        text = text[:setter_anchor.end()] + top_p_setter + text[setter_anchor.end():]

    guard_pattern = re.compile(
        r'''        val activeMainEngine = currentMainChatEngine\(\)\n'''
        r'''        if \(activeMainEngine == "E2B" && !models\.isE2BInstalled\(\)\) \{.*?'''
        r'''        if \(activeMainEngine == "E4B" && !models\.isE4BInstalled\(\)\) \{.*?        \}\n''',
        re.S,
    )
    text, guard_count = guard_pattern.subn(
        '''        if (!models.isE2BInstalled()) {
            setError("E2B LiteRT-LMモデルをダウンロード、またはローカルファイルから読み込んでください")
            return
        }
''',
        text,
        count=1,
    )
    if guard_count != 1:
        raise RuntimeError(f"E2B-only send guard: expected 1 replacement, got {guard_count}")

    generation_pattern = re.compile(
        r'''                    val generationFlow = if \(activeMainEngine == "E2B"\) \{.*?'''
        r'''                    generationFlow\.collect \{ event ->''',
        re.S,
    )
    normal_generation = '''                    e2bChat.generate(
                        model = models.e2bFile,
                        currentUserMessage = clean,
                        systemPrompt = systemWithWeb,
                        history = history,
                        contextSize = _ui.value.contextSize,
                        maxGenerationTokens = replyProfile.maxTokens,
                        topK = _ui.value.topK,
                        topP = _ui.value.topP.toDouble(),
                        temperature = _ui.value.temperature.toDouble()
                    ).collect { event ->'''
    text, gen_count = generation_pattern.subn(normal_generation, text, count=1)
    if gen_count != 1:
        raise RuntimeError(f"E2B-only normal generation: expected 1 replacement, got {gen_count}")

    text = text.replace(
        'runtimeStatus = if (activeMainEngine == "E2B") "E2B GPU READY" else "E4B READY"',
        'runtimeStatus = "E2B GPU+MTP READY"',
    )

    text = text.replace("buildSystemPrompt(relevant, _ui.value.thinkingEnabled)", "buildSystemPrompt(relevant, false)")

    text = text.replace(
        "if (_ui.value.busy || anyModelImporting() || !models.isE4BInstalled()) return",
        "if (_ui.value.busy || anyModelImporting() || !models.isE2BInstalled()) return",
        1,
    )
    monologue_pattern = re.compile(
        r'''                    e4b\.generate\(\n'''
        r'''                        model = models\.getE4BFile\(\),\n'''
        r'''                        currentUserMessage = "Make one spontaneous remark for the quiet chat\.",.*?'''
        r'''                    \)\.collect \{ event ->''',
        re.S,
    )
    monologue_generation = '''                    e2bChat.generate(
                        model = models.e2bFile,
                        currentUserMessage = "Make one spontaneous remark for the quiet chat.",
                        systemPrompt = system,
                        history = history,
                        contextSize = _ui.value.contextSize,
                        maxGenerationTokens = 96,
                        topK = _ui.value.topK,
                        topP = _ui.value.topP.toDouble(),
                        temperature = _ui.value.temperature.toDouble()
                    ).collect { event ->'''
    text, mono_count = monologue_pattern.subn(monologue_generation, text, count=1)
    if mono_count != 1:
        raise RuntimeError(f"E2B-only monologue generation: expected 1 replacement, got {mono_count}")

    text = re.sub(r'(?m)^[ \t]*e4b\.unload\(\)\n', '', text)
    text = text.replace("        e4b.unload(); models.deleteE4B(); refresh()\n", "        models.deleteE4B(); refresh()\n")
    text = text.replace("        e4b.close()\n", "        e2bChat.close()\n")
    text = text.replace('runtimeStatus = "E4B READY"', 'runtimeStatus = "E2B GPU+MTP READY"')

    if "e4b.generate(" in text or "e4b." in text:
        raise RuntimeError("Unexpected live E4B runtime reference remains in ViewModel")
    text = text.replace("import com.ikegami99.jinkaku.ai.E4BEngine\n", "")
    text = re.sub(
        r'(?m)^    private val e4b = E4BEngine\(app, viewModelScope, logger\)\n',
        '',
        text,
        count=1,
    )

    text = text.replace("value.coerceIn(1024L, 8192L)", "value.coerceIn(1024L, 4096L)")
    text = text.replace("return context.coerceIn(1024L, 8192L)", "return context.coerceIn(1024L, 4096L)")

    text = text.replace(
        "class JinkakuViewModel(app: Application) : AndroidViewModel(app) {",
        f"class JinkakuViewModel(app: Application) : AndroidViewModel(app) {{\n    // {MARKER}: chat runtime is E2B LiteRT-LM only.",
        1,
    )
    VM.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to ViewModel: E2B-only chat + live Top-P")


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to UI")
        return

    text = re.sub(
        r'(?m)^    val e4bPicker = rememberLauncherForActivityResult\(ActivityResultContracts\.OpenDocument\(\)\) \{.*\}\n',
        '',
        text,
        count=1,
    )
    e4b_card = re.compile(
        r'''        item \{\n            ModernModelCard\(\n'''
        r'''                title = "Gemma 4 E4B HauhauCS",.*?'''
        r'''                onDelete = vm::deleteE4B\n'''
        r'''            \)\n        \}\n''',
        re.S,
    )
    text, card_count = e4b_card.subn('', text, count=1)
    if card_count != 1:
        raise RuntimeError(f"E4B model card removal: expected 1, got {card_count}")

    selector_start = text.find("// E2B_MAIN_CHAT_V072: main-chat role is selected independently from model file type.")
    if selector_start >= 0:
        selector_start = text.rfind("        item {", 0, selector_start)
        next_card = text.find('        item {\n            ModernModelCard(', selector_start + 1)
        if selector_start < 0 or next_card < 0:
            raise RuntimeError("main chat selector boundaries not found")
        text = text[:selector_start] + text[next_card:]

    text = text.replace(
        'subtitle = "LiteRT-LM · Main chat / Memory · GPU+MTP",',
        'subtitle = "Main chat + Memory · LiteRT-LM · GPU + MTP",',
    )
    text = text.replace(
        'subtitle = "Memory maintenance model",',
        'subtitle = "Main chat + Memory · LiteRT-LM · GPU + MTP",',
    )

    text = text.replace(
        "listOf(1024L, 2048L, 4096L, 8192L)",
        "listOf(1024L, 2048L, 4096L)",
    )

    thinking_label = 'Text("Thinking", fontWeight = FontWeight.SemiBold)'
    if thinking_label in text:
        divider_pos = text.rfind("                    HorizontalDivider()", 0, text.find(thinking_label))
        tail_marker = '"OFFではJinjaのenable_thinkingも無効化します。"'
        tail_pos = text.find(tail_marker, text.find(thinking_label))
        if divider_pos < 0 or tail_pos < 0:
            raise RuntimeError("Thinking UI boundaries not found")
        block_end = text.find("                    )\n", tail_pos)
        if block_end < 0:
            raise RuntimeError("Thinking UI end not found")
        block_end += len("                    )\n")
        runtime_block = '''                    HorizontalDivider()
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("E2B Runtime", fontWeight = FontWeight.SemiBold)
                            Text(
                                "LiteRT-LM · GPU + MTP · Thinking OFF固定",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        AssistChip(onClick = {}, label = { Text("E2B ONLY") })
                    }
'''
        text = text[:divider_pos] + runtime_block + text[block_end:]

    if 'Text("Top-P  ${"%.2f".format(ui.topP)}"' not in text:
        topk_pos = text.find('Text("Top-K  ${ui.topK}", fontWeight = FontWeight.SemiBold)')
        if topk_pos < 0:
            raise RuntimeError("Top-K UI anchor not found")
        insert_at = text.find("                    HorizontalDivider()", topk_pos)
        if insert_at < 0:
            raise RuntimeError("Top-K section end not found")
        top_p_block = '''                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                        Text("Top-P  ${"%.2f".format(ui.topP)}", fontWeight = FontWeight.SemiBold)
                        Slider(
                            value = ui.topP,
                            onValueChange = vm::setTopP,
                            valueRange = 0.05f..1.0f,
                            steps = 18,
                            enabled = !ui.busy
                        )
                        Text(
                            "確率質量で候補を絞ります。0.90前後が自然会話向け。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }

'''
        text = text[:insert_at] + top_p_block + text[insert_at:]

    text = text.replace(
        "小さいほど候補を絞り、大きいほど語彙の選択肢を広げます。Top-Pは0.95固定です。",
        "小さいほど候補を絞り、大きいほど語彙の選択肢を広げます。",
    )

    text = text.replace(
        "private fun ModernSettingsScreen(",
        f"// {MARKER}: E4B controls removed; inference controls feed E2B directly.\nprivate fun ModernSettingsScreen(",
        1,
    )
    UI.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to UI: E4B hidden, Top-P live, E2B runtime explicit")


def main() -> None:
    E2B_CHAT.write_text(E2B_CHAT_SOURCE, encoding="utf-8")
    patch_view_model()
    patch_ui()
    print(f"Applied {MARKER}: Jinkaku is now E2B LiteRT-LM / GPU+MTP only")


if __name__ == "__main__":
    main()
