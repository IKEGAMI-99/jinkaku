from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_view_model() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
    text = path.read_text(encoding="utf-8")
    if "SAMPLING_CONTROLS_V028" in text:
        print("JinkakuViewModel sampling controls already applied")
        return

    text = replace_once(
        text,
        "    val thinkingEnabled: Boolean = true,\n    val error: String? = null,\n",
        "    val thinkingEnabled: Boolean = true,\n    val topK: Int = 64,\n    val temperature: Float = 1.0f,\n    val error: String? = null,\n",
        "UiState sampling fields",
    )

    text = replace_once(
        text,
        "            thinkingEnabled = prefs.getBoolean(KEY_THINKING_ENABLED, true)\n        )\n",
        "            thinkingEnabled = prefs.getBoolean(KEY_THINKING_ENABLED, true),\n            topK = prefs.getInt(\"top_k\", 64).coerceIn(1, 128),\n            temperature = prefs.getFloat(\"temperature\", 1.0f).coerceIn(0.1f, 1.5f)\n        )\n",
        "initial sampling preferences",
    )

    text = replace_once(
        text,
        "                        contextSize = _ui.value.contextSize,\n                        enableThinking = _ui.value.thinkingEnabled\n",
        "                        contextSize = _ui.value.contextSize,\n                        enableThinking = _ui.value.thinkingEnabled,\n                        topK = _ui.value.topK,\n                        temperature = _ui.value.temperature\n",
        "generation sampling arguments",
    )

    text = replace_once(
        text,
        "    fun setContext(value: Long) {\n",
        "    // SAMPLING_CONTROLS_V028\n    fun setTopK(value: Int) {\n        if (_ui.value.busy || anyModelImporting()) return\n        val safe = value.coerceIn(1, 128)\n        prefs.edit().putInt(\"top_k\", safe).apply()\n        _ui.value = _ui.value.copy(topK = safe)\n        logger.i(\"E4B\", \"Sampling Top-K=$safe\")\n    }\n\n    fun setTemperature(value: Float) {\n        if (_ui.value.busy || anyModelImporting()) return\n        val safe = value.coerceIn(0.1f, 1.5f)\n        prefs.edit().putFloat(\"temperature\", safe).apply()\n        _ui.value = _ui.value.copy(temperature = safe)\n        logger.i(\"E4B\", \"Sampling Temperature=$safe\")\n    }\n\n    fun setContext(value: Long) {\n",
        "sampling setters",
    )

    path.write_text(text, encoding="utf-8")


def patch_e4b_engine() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E4BEngine.kt")
    text = path.read_text(encoding="utf-8")
    if "SAMPLING_CONTROLS_V028" in text:
        print("E4BEngine sampling controls already applied")
        return

    text = replace_once(
        text,
        "        contextSize: Long,\n        enableThinking: Boolean\n    ): Flow<GenerationEvent> = flow {\n",
        "        contextSize: Long,\n        enableThinking: Boolean,\n        topK: Int,\n        temperature: Float\n    ): Flow<GenerationEvent> = flow {\n",
        "E4B generate sampling signature",
    )

    text = replace_once(
        text,
        " history=${history.size} thinking=$enableThinking availMem=${memoryInfo.availMem} lowMemory=${memoryInfo.lowMemory}\"\n",
        " history=${history.size} thinking=$enableThinking topK=$topK temperature=$temperature availMem=${memoryInfo.availMem} lowMemory=${memoryInfo.lowMemory}\"\n",
        "generation sampling log",
    )

    text = replace_once(
        text,
        "        bridge.begin(roles.toTypedArray(), contents.toTypedArray(), MAX_GENERATION_TOKENS, enableThinking)\n",
        "        // SAMPLING_CONTROLS_V028: configure the llama.cpp sampler per turn without reloading the model.\n        bridge.begin(\n            roles.toTypedArray(),\n            contents.toTypedArray(),\n            MAX_GENERATION_TOKENS,\n            enableThinking,\n            topK,\n            temperature\n        )\n",
        "bridge sampling call",
    )

    path.write_text(text, encoding="utf-8")


def patch_bridge() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ai/UpstreamLlamaBridge.kt")
    text = path.read_text(encoding="utf-8")
    if "SAMPLING_CONTROLS_V028" in text:
        print("UpstreamLlamaBridge sampling controls already applied")
        return

    text = replace_once(
        text,
        "    fun begin(roles: Array<String>, contents: Array<String>, maxTokens: Int, enableThinking: Boolean) {\n        val error = nativeBegin(roles, contents, maxTokens, enableThinking)\n",
        "    // SAMPLING_CONTROLS_V028\n    fun begin(\n        roles: Array<String>,\n        contents: Array<String>,\n        maxTokens: Int,\n        enableThinking: Boolean,\n        topK: Int,\n        temperature: Float\n    ) {\n        val error = nativeBegin(roles, contents, maxTokens, enableThinking, topK, temperature)\n",
        "bridge begin sampling signature",
    )

    text = replace_once(
        text,
        "    private external fun nativeBegin(roles: Array<String>, contents: Array<String>, maxTokens: Int, enableThinking: Boolean): String?\n",
        "    private external fun nativeBegin(\n        roles: Array<String>,\n        contents: Array<String>,\n        maxTokens: Int,\n        enableThinking: Boolean,\n        topK: Int,\n        temperature: Float\n    ): String?\n",
        "native begin sampling signature",
    )

    path.write_text(text, encoding="utf-8")


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")
    if "SAMPLING_CONTROLS_V028" in text:
        print("ModernJinkakuApp sampling controls already applied")
        return

    text = replace_once(
        text,
        "import androidx.compose.material3.Surface\nimport androidx.compose.material3.Switch\n",
        "import androidx.compose.material3.Surface\nimport androidx.compose.material3.Slider\nimport androidx.compose.material3.Switch\n",
        "Slider import",
    )

    anchor = '''                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                        listOf(1024L, 2048L, 4096L, 8192L).forEach { size ->\n                            FilterChip(\n                                selected = ui.contextSize == size,\n                                onClick = { vm.setContext(size) },\n                                label = { Text("${size / 1024}K") }\n                            )\n                        }\n                    }\n                    HorizontalDivider()\n'''
    replacement = '''                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                        listOf(1024L, 2048L, 4096L, 8192L).forEach { size ->\n                            FilterChip(\n                                selected = ui.contextSize == size,\n                                onClick = { vm.setContext(size) },\n                                label = { Text("${size / 1024}K") }\n                            )\n                        }\n                    }\n\n                    // SAMPLING_CONTROLS_V028\n                    HorizontalDivider()\n                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {\n                        Text(\n                            "Temperature  ${"%.1f".format(ui.temperature)}",\n                            fontWeight = FontWeight.SemiBold\n                        )\n                        Slider(\n                            value = ui.temperature,\n                            onValueChange = vm::setTemperature,\n                            valueRange = 0.1f..1.5f,\n                            steps = 13,\n                            enabled = !ui.busy\n                        )\n                        Text(\n                            "低いほど安定、高いほど自由で意外な回答になります。",\n                            style = MaterialTheme.typography.bodySmall,\n                            color = MaterialTheme.colorScheme.onSurfaceVariant\n                        )\n                    }\n\n                    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {\n                        Text("Top-K  ${ui.topK}", fontWeight = FontWeight.SemiBold)\n                        Slider(\n                            value = ui.topK.toFloat(),\n                            onValueChange = { vm.setTopK(it.toInt()) },\n                            valueRange = 1f..128f,\n                            steps = 126,\n                            enabled = !ui.busy\n                        )\n                        Text(\n                            "小さいほど候補を絞り、大きいほど語彙の選択肢を広げます。Top-Pは0.95固定です。",\n                            style = MaterialTheme.typography.bodySmall,\n                            color = MaterialTheme.colorScheme.onSurfaceVariant\n                        )\n                    }\n\n                    HorizontalDivider()\n'''
    text = replace_once(text, anchor, replacement, "sampling settings UI")
    path.write_text(text, encoding="utf-8")


def patch_native() -> None:
    path = Path("app/src/main/cpp/upstream_llama_jni.cpp")
    text = path.read_text(encoding="utf-8")
    if "SAMPLING_CONTROLS_V028" in text:
        print("native sampling controls already applied")
        return

    text = replace_once(
        text,
        "        jint maxTokens,\n        jboolean enableThinking) {\n",
        "        jint maxTokens,\n        jboolean enableThinking,\n        jint topK,\n        jfloat temperature) {\n",
        "nativeBegin sampling parameters",
    )

    anchor = '''        if (!g_model || !g_ctx || !g_vocab || !g_sampler || !g_chat_templates) {\n            return error_string(env, "model is not loaded");\n        }\n'''
    replacement = '''        if (!g_model || !g_ctx || !g_vocab || !g_sampler || !g_chat_templates) {\n            return error_string(env, "model is not loaded");\n        }\n\n        // SAMPLING_CONTROLS_V028: recreate the sampler per turn so UI changes\n        // take effect immediately while the expensive model/KV context stays resident.\n        const int32_t safeTopK = std::clamp(static_cast<int32_t>(topK), 1, 128);\n        const float safeTemperature = std::clamp(static_cast<float>(temperature), 0.1f, 1.5f);\n        llama_sampler_free(g_sampler);\n        g_sampler = nullptr;\n        llama_sampler_chain_params chainParams = llama_sampler_chain_default_params();\n        g_sampler = llama_sampler_chain_init(chainParams);\n        if (!g_sampler) {\n            return error_string(env, "llama_sampler_chain_init failed");\n        }\n        llama_sampler_chain_add(g_sampler, llama_sampler_init_top_k(safeTopK));\n        llama_sampler_chain_add(g_sampler, llama_sampler_init_top_p(0.95f, 1));\n        llama_sampler_chain_add(g_sampler, llama_sampler_init_temp(safeTemperature));\n        llama_sampler_chain_add(g_sampler, llama_sampler_init_dist(LLAMA_DEFAULT_SEED));\n        LOGI("sampling configured topK=%d temperature=%.2f topP=0.95", safeTopK, safeTemperature);\n'''
    text = replace_once(text, anchor, replacement, "native sampler recreation")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_view_model()
    patch_e4b_engine()
    patch_bridge()
    patch_ui()
    patch_native()
    print("Applied SAMPLING_CONTROLS_V028: persistent Temperature + Top-K controls wired to llama.cpp")


if __name__ == "__main__":
    main()
