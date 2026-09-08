from pathlib import Path
import re


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_view_model() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
    text = path.read_text(encoding="utf-8")
    if "THINKING_IDLE_MEMORY_V024" in text:
        print("JinkakuViewModel v0.1.24 patch already applied")
        return

    text = replace_once(
        text,
        "    val contextSize: Long = 2048,\n    val error: String? = null,\n",
        "    val contextSize: Long = 2048,\n    val thinkingEnabled: Boolean = true,\n    val error: String? = null,\n",
        "UiState thinkingEnabled",
    )

    text = replace_once(
        text,
        "    private val _ui = MutableStateFlow(UiState(contextSize = initialContext, currentChatId = currentChatId))\n",
        """    // THINKING_IDLE_MEMORY_V024: keep the user's Thinking preference in UI state.\n    private val _ui = MutableStateFlow(\n        UiState(\n            contextSize = initialContext,\n            currentChatId = currentChatId,\n            thinkingEnabled = prefs.getBoolean(KEY_THINKING_ENABLED, true)\n        )\n    )\n""",
        "initial UI state",
    )

    text = replace_once(
        text,
        """                        busy = true,\n                        thinking = true,\n                        generatingText = \"\",\n                        runtimeStatus = \"入力中\",\n""",
        """                        busy = true,\n                        thinking = _ui.value.thinkingEnabled,\n                        generatingText = \"\",\n                        runtimeStatus = \"入力中\",\n""",
        "send initial thinking state",
    )

    text = replace_once(
        text,
        "                    val system = buildSystemPrompt(relevant.map { it.content })\n",
        "                    val system = buildSystemPrompt(relevant.map { it.content }, _ui.value.thinkingEnabled)\n",
        "system prompt thinking mode",
    )

    text = replace_once(
        text,
        """                        history = history,\n                        contextSize = _ui.value.contextSize\n                    ).collect { event ->\n""",
        """                        history = history,\n                        contextSize = _ui.value.contextSize,\n                        enableThinking = _ui.value.thinkingEnabled\n                    ).collect { event ->\n""",
        "generate thinking flag",
    )

    text = replace_once(
        text,
        """    private fun scheduleMemoryMaintenance() {\n        memoryIdleJob?.cancel()\n        memoryIdleJob = viewModelScope.launch {\n            delay(60_000)\n            runMemoryMaintenance()\n        }\n    }\n""",
        """    private fun scheduleMemoryMaintenance() {\n        memoryIdleJob?.cancel()\n        memoryIdleJob = viewModelScope.launch {\n            // Keep E4B + KV cache resident while the conversation is active.\n            // Every new send cancels and restarts this timer. E2B maintenance is\n            // therefore deferred until the chat has genuinely been idle.\n            logger.i(\"MEMORY\", \"Maintenance deferred until chat idle for ${MEMORY_IDLE_DELAY_MS / 60_000}m\")\n            delay(MEMORY_IDLE_DELAY_MS)\n            if (_ui.value.busy || anyModelImporting()) return@launch\n            runMemoryMaintenance()\n        }\n    }\n""",
        "idle memory maintenance",
    )

    prompt_pattern = re.compile(
        r'''    private fun buildSystemPrompt\(memories: List<String>\): String \{.*?\n    \}\n\n    fun downloadE4B\(\) \{''',
        re.S,
    )
    prompt_replacement = '''    private fun buildSystemPrompt(memories: List<String>, enableThinking: Boolean): String {\n        val persona = db.currentPersona()\n        val memoryBlock = if (memories.isEmpty()) "(none)" else memories.joinToString("\\n") { "- $it" }\n        val reasoning = if (enableThinking) {\n            "<|think|>\\nThink carefully before answering, but keep internal reasoning private. Output only the final answer after thinking."\n        } else {\n            "Answer directly without a hidden thinking/reasoning phase. Do not emit thought or analysis markers."\n        }\n        return """$reasoning\nYou are Jinkaku, a persistent local AI with an evolving but coherent personality. Do not blindly agree. Be consistent with durable memories while treating them as fallible context. Reply naturally in the user's language.\nPersona state: $persona\nRelevant long-term memories:\n$memoryBlock""".trimIndent()\n    }\n\n    fun downloadE4B() {'''
    text, count = prompt_pattern.subn(prompt_replacement, text, count=1)
    if count != 1:
        raise RuntimeError("anchor not found: buildSystemPrompt")

    text = replace_once(
        text,
        """    fun setContext(value: Long) {\n""",
        """    fun setThinkingEnabled(enabled: Boolean) {\n        if (_ui.value.busy || anyModelImporting()) {\n            setError(\"推論・モデル処理中はThinkingを切り替えられません\")\n            return\n        }\n        if (_ui.value.thinkingEnabled == enabled) return\n        prefs.edit().putBoolean(KEY_THINKING_ENABLED, enabled).apply()\n        // The rendered Jinja prompt changes with this flag, so reset the native\n        // conversation cache once when the user switches modes.\n        e4b.unload()\n        _ui.value = _ui.value.copy(\n            thinkingEnabled = enabled,\n            thinking = false,\n            runtimeStatus = \"IDLE\",\n            notice = if (enabled) \"ThinkingをONにしました\" else \"ThinkingをOFFにしました\"\n        )\n        logger.i(\"E4B\", \"Thinking mode enabled=$enabled\")\n    }\n\n    fun setContext(value: Long) {\n""",
        "thinking setter",
    )

    text = replace_once(
        text,
        """        private const val KEY_CURRENT_CHAT_ID = \"current_chat_id\"\n        private const val RUNTIME_PROFILE_VERSION = 3\n""",
        """        private const val KEY_CURRENT_CHAT_ID = \"current_chat_id\"\n        private const val KEY_THINKING_ENABLED = \"thinking_enabled\"\n        private const val MEMORY_IDLE_DELAY_MS = 15L * 60L * 1000L\n        private const val RUNTIME_PROFILE_VERSION = 3\n""",
        "view model constants",
    )

    path.write_text(text, encoding="utf-8")


def patch_e4b_engine() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E4BEngine.kt")
    text = path.read_text(encoding="utf-8")
    if "enableThinking: Boolean" in text:
        print("E4BEngine v0.1.24 patch already applied")
        return

    text = text.replace(" jinja=true thinking=true threads=6", " jinja=true threads=6")

    text = replace_once(
        text,
        """        history: List<ChatMessage>,\n        contextSize: Long\n    ): Flow<GenerationEvent> = flow {\n""",
        """        history: List<ChatMessage>,\n        contextSize: Long,\n        enableThinking: Boolean\n    ): Flow<GenerationEvent> = flow {\n""",
        "E4B generate signature",
    )

    text = replace_once(
        text,
        " history=${history.size} availMem=${memoryInfo.availMem} lowMemory=${memoryInfo.lowMemory}\"\n",
        " history=${history.size} thinking=$enableThinking availMem=${memoryInfo.availMem} lowMemory=${memoryInfo.lowMemory}\"\n",
        "generation start log",
    )

    text = replace_once(
        text,
        "        bridge.begin(roles.toTypedArray(), contents.toTypedArray(), MAX_GENERATION_TOKENS)\n",
        "        bridge.begin(roles.toTypedArray(), contents.toTypedArray(), MAX_GENERATION_TOKENS, enableThinking)\n",
        "bridge begin thinking",
    )

    text = replace_once(
        text,
        "        InferenceTelemetry.update(nativeStats, \"THINKING\")\n",
        "        InferenceTelemetry.update(nativeStats, if (enableThinking) \"THINKING\" else \"DECODE\")\n",
        "initial telemetry mode",
    )

    text = replace_once(
        text,
        " enableThinking=true maxTokens=${nativeStats.maxGenerationTokens}",
        " enableThinking=$enableThinking maxTokens=${nativeStats.maxGenerationTokens}",
        "thinking log flag",
    )

    text = replace_once(
        text,
        "        emit(GenerationEvent.Thinking)\n",
        "        if (enableThinking) emit(GenerationEvent.Thinking)\n",
        "conditional thinking event",
    )

    text = replace_once(
        text,
        "                    InferenceTelemetry.update(nativeStats, if (visibleStarted) \"DECODE\" else \"THINKING\")\n",
        "                    InferenceTelemetry.update(nativeStats, if (visibleStarted || !enableThinking) \"DECODE\" else \"THINKING\")\n",
        "stream telemetry mode",
    )

    path.write_text(text, encoding="utf-8")


def patch_bridge() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ai/UpstreamLlamaBridge.kt")
    text = path.read_text(encoding="utf-8")
    if "enableThinking: Boolean" in text:
        print("UpstreamLlamaBridge v0.1.24 patch already applied")
        return

    text = replace_once(
        text,
        """    fun begin(roles: Array<String>, contents: Array<String>, maxTokens: Int) {\n        val error = nativeBegin(roles, contents, maxTokens)\n""",
        """    fun begin(roles: Array<String>, contents: Array<String>, maxTokens: Int, enableThinking: Boolean) {\n        val error = nativeBegin(roles, contents, maxTokens, enableThinking)\n""",
        "bridge begin signature",
    )
    text = replace_once(
        text,
        "    private external fun nativeBegin(roles: Array<String>, contents: Array<String>, maxTokens: Int): String?\n",
        "    private external fun nativeBegin(roles: Array<String>, contents: Array<String>, maxTokens: Int, enableThinking: Boolean): String?\n",
        "native begin signature",
    )
    path.write_text(text, encoding="utf-8")


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")
    if 'Text("Thinking", fontWeight = FontWeight.SemiBold)' in text:
        print("ModernJinkakuApp v0.1.24 patch already applied")
        return

    old = '''                    Text("CoTは有効で非表示。回答本文はDecode完了後に一括表示します。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)\n'''
    new = '''                    HorizontalDivider()\n                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {\n                        Column(Modifier.weight(1f)) {\n                            Text("Thinking", fontWeight = FontWeight.SemiBold)\n                            Text(\n                                if (ui.thinkingEnabled) "内部Thinkingを使ってから回答" else "Thinkingを省略して直接回答",\n                                style = MaterialTheme.typography.bodySmall,\n                                color = MaterialTheme.colorScheme.onSurfaceVariant\n                            )\n                        }\n                        Switch(\n                            checked = ui.thinkingEnabled,\n                            onCheckedChange = vm::setThinkingEnabled,\n                            enabled = !ui.busy && !ui.e4bImporting\n                        )\n                    }\n                    Text(\n                        if (ui.thinkingEnabled) "Thinking内容は非表示です。" else "OFFではJinjaのenable_thinkingも無効化します。",\n                        style = MaterialTheme.typography.bodySmall,\n                        color = MaterialTheme.colorScheme.onSurfaceVariant\n                    )\n'''
    text = replace_once(text, old, new, "Thinking settings UI")
    path.write_text(text, encoding="utf-8")


def patch_native() -> None:
    # This script runs after patch_cpu_speed_v022.py, so the KV cache and 512/256
    # prompt batching are already present in this generated build source.
    path = Path("app/src/main/cpp/upstream_llama_jni.cpp")
    text = path.read_text(encoding="utf-8")
    if "jboolean enableThinking" in text:
        print("native v0.1.24 patch already applied")
        return

    text = replace_once(
        text,
        """        jobjectArray contents,\n        jint maxTokens) {\n""",
        """        jobjectArray contents,\n        jint maxTokens,\n        jboolean enableThinking) {\n""",
        "nativeBegin bool parameter",
    )
    text = replace_once(
        text,
        "        inputs.enable_thinking = true;\n",
        "        inputs.enable_thinking = enableThinking == JNI_TRUE;\n",
        "Jinja enable_thinking",
    )

    text = replace_once(
        text,
        '            "generation begun totalPrompt=%d prefillTokens=%d cachedPrefix=%zu cacheHit=%.1f%% maxTokens=%d thinking=true prefill=%.2f tok/s backend=%s",\n',
        '            "generation begun totalPrompt=%d prefillTokens=%d cachedPrefix=%zu cacheHit=%.1f%% maxTokens=%d thinking=%s prefill=%.2f tok/s backend=%s",\n',
        "native thinking log format",
    )
    text = replace_once(
        text,
        """            cache_pct,\n            g_max_tokens,\n            prefill_tps,\n""",
        """            cache_pct,\n            g_max_tokens,\n            enableThinking == JNI_TRUE ? "true" : "false",\n            prefill_tps,\n""",
        "native thinking log value",
    )

    # Keep only the rendered prompt in the comparison vector. Generated hidden
    # thought tokens differ from the assistant history (which stores final text),
    # so appending them poisoned the next-turn common-prefix match. The KV itself
    # still contains generated tokens; nativeBegin removes that tail before reuse.
    text = replace_once(
        text,
        """        ++g_position;\n        ++g_generated;\n        g_cached_tokens.push_back(token);\n        return to_byte_array(env, piece);\n""",
        """        ++g_position;\n        ++g_generated;\n        return to_byte_array(env, piece);\n""",
        "do not append generated tokens to prefix vector",
    )

    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_view_model()
    patch_e4b_engine()
    patch_bridge()
    patch_ui()
    patch_native()
    print("Applied THINKING_IDLE_MEMORY_V024: 15m idle memory maintenance + Thinking toggle + cleaner KV prefix reuse")


if __name__ == "__main__":
    main()
