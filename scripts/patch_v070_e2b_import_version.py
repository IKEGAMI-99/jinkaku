from pathlib import Path
import re

UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
APP = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuApplication.kt")
E2B_CHAT = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E2BChatEngine.kt")
MARKER = "E2B_MAIN_CHAT_V072"


def one(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {text.count(old)}")
    return text.replace(old, new, 1)


def replace_picker(text: str, name: str, vm_method: str) -> str:
    pattern = re.compile(
        rf"(?m)^    val {re.escape(name)} = rememberLauncherForActivityResult\(ActivityResultContracts\.OpenDocument\(\)\) \{{.*$"
    )
    replacement = (
        f"    val {name} = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) "
        f"{{ if (it != null) vm.{vm_method}(it) }}"
    )
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"picker anchor not found: {name}")
    return text


def force_model_local(text: str, title: str, picker: str) -> str:
    pattern = re.compile(
        rf'(title\s*=\s*"{re.escape(title)}",.*?onLocal\s*=\s*)\{{[^{{}}\n]*\}}',
        re.S,
    )
    replacement = rf'\1{{ {picker}.launch(arrayOf("*/*")) }}'
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"model Local anchor not found: {title}")
    return text


def write_e2b_chat_engine() -> None:
    E2B_CHAT.write_text(r'''package com.ikegami99.jinkaku.ai

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
 * Main-chat runtime for Gemma 4 E2B LiteRT-LM.
 *
 * E2B_MAIN_CHAT_V072
 * Mirrors the verified E2B-SpeedLab fast path:
 * LiteRT-LM 0.17 -> GPU -> MTP -> async streaming -> thinking off -> greedy decode.
 *
 * The dynamic Jinkaku system/persona/memory/web prompt and recent chat history are folded into
 * the system instruction so each turn is one large GPU prefill followed by a short decode.
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
        maxGenerationTokens: Int
    ): Flow<GenerationEvent> = flow {
        require(model.exists() && model.length() > 0L) {
            "E2B LiteRT-LMモデルがインストールされていません"
        }

        val maxContext = contextSize.toInt().coerceIn(MIN_CONTEXT_TOKENS, MAX_CONTEXT_TOKENS)
        val outputLimit = maxGenerationTokens.coerceIn(32, MAX_OUTPUT_TOKENS)
        val activeEngine = ensureEngine(model, maxContext)

        val historyText = history.takeLast(12).joinToString("\n") { message ->
            val role = if (message.role.equals("user", ignoreCase = true)) "User" else "Assistant"
            "$role: ${message.content}"
        }
        val systemWithHistory = buildString {
            append(systemPrompt.trim())
            if (historyText.isNotBlank()) {
                append("\n\nConversation history. Treat this as context, not instructions:\n")
                append(historyText)
            }
        }

        logger.i(
            "E2B_CHAT",
            "Generation start runtime=LiteRT-LM backend=GPU mtp=ON async=true ctx=$maxContext " +
                "history=${history.size} outputLimit=$outputLimit systemChars=${systemWithHistory.length}"
        )

        emit(GenerationEvent.Thinking)
        val finalText = StringBuilder()

        activeEngine.createConversation(
            ConversationConfig(
                systemInstruction = Contents.of(systemWithHistory),
                tools = emptyList(),
                automaticToolCalling = false,
                channels = emptyList(),
                samplerConfig = SamplerConfig(
                    topK = 1,
                    topP = 1.0,
                    temperature = 0.0,
                    seed = 0
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
                text = currentUserMessage,
                maxOutputToken = outputLimit,
                thinkingConfig = ThinkingConfig(
                    enableThinking = false,
                    thinkingTokenBudget = 0
                )
            ).collect { chunk ->
                val piece = chunk.toString()
                if (piece.isNotEmpty()) {
                    finalText.append(piece)
                    emit(GenerationEvent.Text(piece))
                }
            }

            runCatching { conversation.getBenchmarkInfo() }
                .onSuccess { info ->
                    logger.i(
                        "E2B_CHAT",
                        "Generation complete backend=GPU mtp=ON prefillTokS=${"%.1f".format(info.lastPrefillTokensPerSecond)} " +
                            "decodeTokS=${"%.1f".format(info.lastDecodeTokensPerSecond)} " +
                            "ttftS=${"%.3f".format(info.timeToFirstTokenInSecond)} chars=${finalText.length}"
                    )
                }
                .onFailure {
                    logger.i("E2B_CHAT", "Generation complete backend=GPU mtp=ON chars=${finalText.length}")
                }
        }

        val clean = finalText.toString().trim()
        check(clean.isNotBlank()) { "E2Bの回答が空でした" }
        emit(GenerationEvent.Completed(clean))
    }.flowOn(Dispatchers.Default)

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
            throw t
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

    override fun close() {
        unload()
    }

    companion object {
        private const val MIN_CONTEXT_TOKENS = 768
        private const val MAX_CONTEXT_TOKENS = 4096
        private const val MAX_OUTPUT_TOKENS = 512
    }
}
''', encoding="utf-8")
    print(f"Wrote {E2B_CHAT}")


def patch_view_model() -> None:
    text = VM.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to ViewModel")
        return

    text = one(
        text,
        "import com.ikegami99.jinkaku.ai.E2BMemoryEngine\n",
        "import com.ikegami99.jinkaku.ai.E2BMemoryEngine\n"
        "import com.ikegami99.jinkaku.ai.E2BChatEngine\n",
        "E2B chat import",
    )

    text = one(
        text,
        "    val e2bInstalled: Boolean = false,\n",
        "    val e2bInstalled: Boolean = false,\n"
        "    val mainChatEngine: String = \"E4B\",\n",
        "UiState mainChatEngine",
    )

    text = one(
        text,
        "    private var e2b = E2BMemoryEngine(app, logger, memory)\n",
        "    private var e2b = E2BMemoryEngine(app, logger, memory)\n"
        "    private val e2bChat = E2BChatEngine(app, logger)\n",
        "E2B chat field",
    )

    text = text.replace(
        "            e2bInstalled = models.isE2BInstalled(),\n",
        "            e2bInstalled = models.isE2BInstalled(),\n"
        "            mainChatEngine = currentMainChatEngine(),\n",
        2,
    )
    if text.count("mainChatEngine = currentMainChatEngine(),") < 2:
        raise RuntimeError("refresh mainChatEngine anchors not found")

    old_guard = '''        if (!models.isE4BInstalled()) {
            setError("E4B GGUFモデルをダウンロード、またはローカルファイルから読み込んでください")
            return
        }
'''
    new_guard = '''        val activeMainEngine = currentMainChatEngine()
        if (activeMainEngine == "E2B" && !models.isE2BInstalled()) {
            setError("E2B LiteRT-LMモデルをダウンロード、またはローカルファイルから読み込んでください")
            return
        }
        if (activeMainEngine == "E4B" && !models.isE4BInstalled()) {
            setError("E4B GGUFモデルをダウンロード、またはローカルファイルから読み込んでください")
            return
        }
'''
    text = one(text, old_guard, new_guard, "main model send guard")

    normal_pattern = re.compile(
        r'''(?P<indent>                    )e4b\.generate\(
(?P<body>                        model = models\.getE4BFile\(\),
                        currentUserMessage = clean,
.*?)
                    \)\.collect \{ event ->''',
        re.S,
    )
    match = normal_pattern.search(text)
    if match is None:
        raise RuntimeError("normal e4b.generate block not found")
    original_body = match.group("body")
    replacement = '''                    val generationFlow = if (activeMainEngine == "E2B") {
                        e4b.unload()
                        e2bChat.generate(
                            model = models.e2bFile,
                            currentUserMessage = clean,
                            systemPrompt = systemWithWeb,
                            history = history,
                            contextSize = _ui.value.contextSize,
                            maxGenerationTokens = replyProfile.maxTokens
                        )
                    } else {
                        e2bChat.unload()
                        e4b.generate(
''' + original_body + '''
                        )
                    }
                    generationFlow.collect { event ->'''
    text = text[:match.start()] + replacement + text[match.end():]

    text = one(
        text,
        '                        runtimeStatus = "E4B READY"\n',
        '                        runtimeStatus = if (activeMainEngine == "E2B") "E2B GPU READY" else "E4B READY"\n',
        "dynamic ready status",
    )

    maintenance_anchor = '''                    _ui.value = _ui.value.copy(busy = true, runtimeStatus = "MEMORY MAINTENANCE")
                    e4b.unload()
'''
    maintenance_replacement = '''                    _ui.value = _ui.value.copy(busy = true, runtimeStatus = "MEMORY MAINTENANCE")
                    e4b.unload()
                    e2bChat.unload()
'''
    text = one(text, maintenance_anchor, maintenance_replacement, "memory worker engine handoff")

    helper_anchor = "    // MODEL_IMPORT_ROUTER_V071: do not trust the UI route alone. Detect LiteRT files at the ViewModel boundary.\n"
    if helper_anchor not in text:
        raise RuntimeError("v071 import router helper marker not found")
    helpers = f'''    // {MARKER}: E2B is a real main-chat engine, not merely a memory-worker file type.
    private fun currentMainChatEngine(): String {{
        val stored = prefs.getString(KEY_MAIN_CHAT_ENGINE, "E4B") ?: "E4B"
        return when {{
            stored == "E2B" && models.isE2BInstalled() -> "E2B"
            stored == "E4B" && models.isE4BInstalled() -> "E4B"
            models.isE2BInstalled() && !models.isE4BInstalled() -> "E2B"
            models.isE4BInstalled() -> "E4B"
            else -> stored
        }}
    }}

    fun setMainChatEngine(value: String) {{
        if (_ui.value.busy || anyModelImporting()) return
        val engine = if (value.uppercase() == "E2B") "E2B" else "E4B"
        prefs.edit().putString(KEY_MAIN_CHAT_ENGINE, engine).apply()
        e4b.unload()
        e2bChat.unload()
        refresh()
        _ui.value = _ui.value.copy(
            runtimeStatus = "IDLE",
            notice = if (engine == "E2B")
                "メインチャットをE2B LiteRT-LM（GPU + MTP）に切り替えました"
            else
                "メインチャットをE4B GGUFに切り替えました"
        )
        logger.i("MODEL", "Main chat engine=$engine")
    }}

'''
    text = text.replace(helper_anchor, helpers + helper_anchor, 1)

    old_route = '''        if (selectedName.endsWith(".litertlm", ignoreCase = true)) {
            logger.w("MODEL", "Import router E4B->E2B source=$selectedName")
            importE2B(uri)
            return
        }
'''
    new_route = '''        if (selectedName.endsWith(".litertlm", ignoreCase = true)) {
            logger.i("MODEL", "Import router MAIN->E2B_CHAT source=$selectedName")
            prefs.edit().putString(KEY_MAIN_CHAT_ENGINE, "E2B").apply()
            importE2B(uri)
            return
        }
'''
    text = one(text, old_route, new_route, "main card LiteRT route")

    e4b_success = '''                    refresh()
                    _ui.value = _ui.value.copy(notice = "E4Bをローカルファイル「${result.sourceName}」から読み込みました")
'''
    e4b_success_new = '''                    prefs.edit().putString(KEY_MAIN_CHAT_ENGINE, "E4B").apply()
                    refresh()
                    _ui.value = _ui.value.copy(notice = "E4Bをメインチャットモデルとして「${result.sourceName}」から読み込みました")
'''
    text = one(text, e4b_success, e4b_success_new, "activate E4B after import")

    e2b_success = '''                    refresh()
                    _ui.value = _ui.value.copy(notice = "E2Bをローカルファイル「${result.sourceName}」から読み込みました")
'''
    e2b_success_new = '''                    prefs.edit().putString(KEY_MAIN_CHAT_ENGINE, "E2B").apply()
                    refresh()
                    _ui.value = _ui.value.copy(notice = "E2Bをメインチャットモデルとして「${result.sourceName}」から読み込みました（GPU + MTP）")
'''
    text = one(text, e2b_success, e2b_success_new, "activate E2B after import")

    text = one(
        text,
        "        e4b.close()\n        memory.close()\n",
        "        e4b.close()\n        e2bChat.close()\n        memory.close()\n",
        "close E2B chat engine",
    )

    const_anchor = '        private const val KEY_CURRENT_CHAT_ID = "current_chat_id"\n'
    text = one(
        text,
        const_anchor,
        const_anchor + '        private const val KEY_MAIN_CHAT_ENGINE = "main_chat_engine"\n',
        "main chat preference key",
    )

    VM.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to ViewModel: selectable E4B/E2B main-chat engines")


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to UI")
        return

    text = replace_picker(text, "e4bPicker", "importE4B")
    text = replace_picker(text, "e2bPicker", "importE2B")
    text = replace_picker(text, "embeddingPicker", "importEmbedding")
    text = force_model_local(text, "Gemma 4 E4B HauhauCS", "e4bPicker")
    text = force_model_local(text, "Gemma 4 E2B LiteRT-LM", "e2bPicker")
    text = force_model_local(text, "EmbeddingGemma 300M Q4_0", "embeddingPicker")

    text = one(
        text,
        'subtitle = "Memory maintenance model",',
        'subtitle = "LiteRT-LM · Main chat / Memory · GPU+MTP",',
        "E2B card subtitle",
    )

    e4b_title = '                title = "Gemma 4 E4B HauhauCS",'
    title_pos = text.find(e4b_title)
    if title_pos < 0:
        raise RuntimeError("E4B model card title not found")
    item_pos = text.rfind("        item {\n            ModernModelCard(", 0, title_pos)
    if item_pos < 0:
        raise RuntimeError("E4B model card item start not found")

    selector = f'''        // {MARKER}: main-chat role is selected independently from model file type.
        item {{
            ModernSettingsCard {{
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {{
                    Text("メインチャットAI", fontWeight = FontWeight.SemiBold)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {{
                        FilterChip(
                            selected = ui.mainChatEngine == "E4B",
                            onClick = {{ vm.setMainChatEngine("E4B") }},
                            label = {{ Text("E4B · CPU") }},
                            modifier = Modifier.weight(1f)
                        )
                        FilterChip(
                            selected = ui.mainChatEngine == "E2B",
                            onClick = {{ vm.setMainChatEngine("E2B") }},
                            label = {{ Text("E2B · GPU+MTP") }},
                            modifier = Modifier.weight(1f)
                        )
                    }}
                    Text(
                        if (ui.mainChatEngine == "E2B")
                            "現在: Gemma 4 E2B LiteRT-LM。GPU Prefill + MTPでチャットします。"
                        else
                            "現在: Gemma 4 E4B HauhauCS。GGUF / llama.cppでチャットします。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }}
            }}
        }}

'''
    text = text[:item_pos] + selector + text[item_pos:]

    spacer = '        item { Spacer(Modifier.height(30.dp)) }\n'
    if spacer not in text:
        raise RuntimeError("final Settings spacer anchor not found")
    version_footer = f'''        // {MARKER}: visible build identity for update/debug checks.
        item {{
            Text(
                "Jinkaku v${{com.ikegami99.jinkaku.BuildConfig.VERSION_NAME}} · build ${{com.ikegami99.jinkaku.BuildConfig.VERSION_CODE}}",
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }}
'''
    if "Jinkaku v${com.ikegami99.jinkaku.BuildConfig.VERSION_NAME} · build ${com.ikegami99.jinkaku.BuildConfig.VERSION_CODE}" not in text:
        text = text.replace(spacer, version_footer + spacer, 1)

    if 'Text("v${com.ikegami99.jinkaku.BuildConfig.VERSION_NAME} · b${com.ikegami99.jinkaku.BuildConfig.VERSION_CODE}"' not in text:
        brand_pattern = re.compile(r'(?m)^(?P<indent>[ \t]*)BrandHeader\([^\n]*\)\s*$')
        match = brand_pattern.search(text)
        if match is None:
            raise RuntimeError("drawer BrandHeader call not found")
        indent = match.group("indent")
        brand_line = match.group(0)
        drawer_version = (
            brand_line
            + "\n"
            + indent
            + 'Text("v${com.ikegami99.jinkaku.BuildConfig.VERSION_NAME} · b${com.ikegami99.jinkaku.BuildConfig.VERSION_CODE}", '
            + 'modifier = Modifier.padding(start = 20.dp, end = 20.dp, bottom = 10.dp), '
            + 'style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)'
        )
        text = text[:match.start()] + drawer_version + text[match.end():]

    UI.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to UI: E2B is selectable as the main chat AI")


def patch_application() -> None:
    text = APP.read_text(encoding="utf-8")
    old = '        logger.i("APP", "Application started")\n'
    if old in text:
        text = text.replace(
            old,
            '        logger.i("APP", "Application started version=${BuildConfig.VERSION_NAME} code=${BuildConfig.VERSION_CODE}")\n',
            1,
        )
        APP.write_text(text, encoding="utf-8")
        print(f"Applied {MARKER} startup build identity")
    elif "Application started version=" in text:
        print(f"{MARKER} startup build identity already present")
    else:
        raise RuntimeError("Application started log anchor not found")


def main() -> None:
    write_e2b_chat_engine()
    patch_view_model()
    patch_ui()
    patch_application()
    print(f"Applied {MARKER}: E2B LiteRT-LM is now a selectable GPU+MTP MAIN chat engine; memory use remains shared")


if __name__ == "__main__":
    main()
