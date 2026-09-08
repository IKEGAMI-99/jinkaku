from pathlib import Path


def patch_backend_config() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ai/BackendConfig.kt")
    text = path.read_text(encoding="utf-8")
    if "GPU_LAYERS_MAX = 999" in text:
        return

    text = text.replace(
        "enum class InferenceBackend(val id: Int, val label: String) {\n",
        "const val GPU_LAYERS_MAX = 999\n\nenum class InferenceBackend(val id: Int, val label: String) {\n",
        1,
    )
    text = text.replace(
        '        gpuLayers = prefs.getInt(KEY_GPU_LAYERS, 20).coerceIn(1, 64)\n',
        '        gpuLayers = normalizeGpuLayers(prefs.getInt(KEY_GPU_LAYERS, 20))\n',
        1,
    )
    text = text.replace(
        '    fun setGpuLayers(value: Int) {\n        prefs.edit().putInt(KEY_GPU_LAYERS, value.coerceIn(1, 64)).apply()\n    }\n\n',
        '    fun setGpuLayers(value: Int) {\n        prefs.edit().putInt(KEY_GPU_LAYERS, normalizeGpuLayers(value)).apply()\n    }\n\n'
        '    private fun normalizeGpuLayers(value: Int): Int =\n'
        '        if (value >= GPU_LAYERS_MAX) GPU_LAYERS_MAX else value.coerceIn(1, 64)\n\n',
        1,
    )
    path.write_text(text, encoding="utf-8")


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")
    if "BACKEND_SETTINGS_V019" in text:
        return

    text = text.replace(
        "import androidx.compose.runtime.mutableStateOf\n",
        "import androidx.compose.runtime.mutableStateOf\nimport androidx.compose.runtime.mutableIntStateOf\n",
        1,
    )
    text = text.replace(
        "import com.ikegami99.jinkaku.ai.InferenceTelemetry\n",
        "import com.ikegami99.jinkaku.ai.BackendPreferences\n"
        "import com.ikegami99.jinkaku.ai.GPU_LAYERS_MAX\n"
        "import com.ikegami99.jinkaku.ai.InferenceBackend\n"
        "import com.ikegami99.jinkaku.ai.InferenceTelemetry\n",
        1,
    )

    state_anchor = "    var personaDraft by remember { mutableStateOf(vm.currentPersona()) }\n"
    state_block = '''    var personaDraft by remember { mutableStateOf(vm.currentPersona()) }\n\n    // BACKEND_SETTINGS_V019\n    val backendContext = LocalContext.current\n    val backendPrefs = remember(backendContext) { BackendPreferences(backendContext) }\n    val backendInitial = remember { backendPrefs.get() }\n    var backendMode by remember { mutableStateOf(backendInitial.mode) }\n    var gpuLayers by remember { mutableIntStateOf(backendInitial.gpuLayers) }\n    val telemetry by InferenceTelemetry.state.collectAsStateWithLifecycle()\n'''
    if state_anchor not in text:
        raise RuntimeError("ModernSettingsScreen state anchor not found")
    text = text.replace(state_anchor, state_block, 1)

    infer_anchor = '''                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {\n                    Text("Context window", fontWeight = FontWeight.SemiBold)\n'''
    infer_block = '''                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {\n                    Text("Backend", fontWeight = FontWeight.SemiBold)\n                    Text(\n                        "Vulkanは使用しません。GPUはAdreno OpenCLを使用し、利用できない場合はCPUへ戻ります。",\n                        style = MaterialTheme.typography.bodySmall,\n                        color = MaterialTheme.colorScheme.onSurfaceVariant\n                    )\n                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {\n                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                            listOf(InferenceBackend.AUTO, InferenceBackend.CPU).forEach { mode ->\n                                FilterChip(\n                                    selected = backendMode == mode,\n                                    onClick = {\n                                        backendMode = mode\n                                        backendPrefs.setMode(mode)\n                                    },\n                                    label = { Text(if (mode == InferenceBackend.AUTO) "Auto" else "CPU") }\n                                )\n                            }\n                        }\n                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                            listOf(InferenceBackend.GPU, InferenceBackend.HYBRID).forEach { mode ->\n                                FilterChip(\n                                    selected = backendMode == mode,\n                                    onClick = {\n                                        backendMode = mode\n                                        backendPrefs.setMode(mode)\n                                        if (mode == InferenceBackend.GPU) {\n                                            gpuLayers = GPU_LAYERS_MAX\n                                            backendPrefs.setGpuLayers(GPU_LAYERS_MAX)\n                                        }\n                                    },\n                                    label = { Text(if (mode == InferenceBackend.GPU) "GPU · OpenCL" else "CPU + GPU") }\n                                )\n                            }\n                        }\n                    }\n                    if (backendMode == InferenceBackend.AUTO || backendMode == InferenceBackend.HYBRID) {\n                        Text("GPU offload layers", fontWeight = FontWeight.SemiBold)\n                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {\n                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                                listOf(8, 12, 16).forEach { layers ->\n                                    FilterChip(\n                                        selected = gpuLayers == layers,\n                                        onClick = { gpuLayers = layers; backendPrefs.setGpuLayers(layers) },\n                                        label = { Text(layers.toString()) }\n                                    )\n                                }\n                            }\n                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                                listOf(20, GPU_LAYERS_MAX).forEach { layers ->\n                                    FilterChip(\n                                        selected = gpuLayers == layers,\n                                        onClick = { gpuLayers = layers; backendPrefs.setGpuLayers(layers) },\n                                        label = { Text(if (layers == GPU_LAYERS_MAX) "MAX" else layers.toString()) }\n                                    )\n                                }\n                            }\n                        }\n                        Text(\n                            "8 / 12 / 16 / 20で速度比較できます。MAXは可能な全レイヤーをOpenCLへoffloadします。",\n                            style = MaterialTheme.typography.bodySmall,\n                            color = MaterialTheme.colorScheme.onSurfaceVariant\n                        )\n                    }\n                    Text(\n                        when (backendMode) {\n                            InferenceBackend.AUTO -> "Auto: OpenCLが使えれば選択したlayersをGPUへoffloadします。"\n                            InferenceBackend.CPU -> "CPU: GPUを使いません。"\n                            InferenceBackend.GPU -> "GPU: MAX offload。可能な全レイヤーをOpenCLへ載せます。"\n                            InferenceBackend.HYBRID -> "CPU + GPU: 選択したlayersだけAdrenoへoffloadします。"\n                        },\n                        style = MaterialTheme.typography.bodySmall,\n                        color = MaterialTheme.colorScheme.onSurfaceVariant\n                    )\n                    Text(\n                        "現在の実行Backend: ${telemetry.backend}",\n                        style = MaterialTheme.typography.labelMedium,\n                        color = MaterialTheme.colorScheme.secondary\n                    )\n                    HorizontalDivider()\n                    Text("Context window", fontWeight = FontWeight.SemiBold)\n'''
    if infer_anchor not in text:
        raise RuntimeError("Inference settings anchor not found")
    text = text.replace(infer_anchor, infer_block, 1)
    path.write_text(text, encoding="utf-8")


def patch_backend_overlay() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/BackendControlOverlay.kt")
    text = path.read_text(encoding="utf-8")
    if "GPU_LAYER_CHOICES_V019" in text:
        return

    text = text.replace(
        "import com.ikegami99.jinkaku.ai.BackendPreferences\n",
        "import com.ikegami99.jinkaku.ai.BackendPreferences\nimport com.ikegami99.jinkaku.ai.GPU_LAYERS_MAX\n",
        1,
    )
    text = text.replace(
        "                            listOf(8, 16, 20, 24, 32, 42).forEach { layers ->\n",
        "                            // GPU_LAYER_CHOICES_V019\n                            listOf(8, 12, 16, 20, GPU_LAYERS_MAX).forEach { layers ->\n",
        1,
    )
    text = text.replace(
        "                                    label = { Text(layers.toString()) }\n",
        "                                    label = { Text(if (layers == GPU_LAYERS_MAX) \"MAX\" else layers.toString()) }\n",
        1,
    )
    text = text.replace(
        "                                    selected = selected == mode,\n                                    onClick = {\n                                        selected = mode\n                                        prefs.setMode(mode)\n                                    },\n",
        "                                    selected = selected == mode,\n                                    onClick = {\n                                        selected = mode\n                                        prefs.setMode(mode)\n                                        if (mode == InferenceBackend.GPU) {\n                                            gpuLayers = GPU_LAYERS_MAX\n                                            prefs.setGpuLayers(GPU_LAYERS_MAX)\n                                        }\n                                    },\n",
        1,
    )
    path.write_text(text, encoding="utf-8")


def patch_native_gpu_layers() -> None:
    path = Path("app/src/main/cpp/upstream_llama_jni.cpp")
    text = path.read_text(encoding="utf-8")
    if "GPU_LAYERS_MAX_V019" in text:
        return

    old = "std::clamp(static_cast<int32_t>(gpuLayers), 1, 64)"
    new = "((gpuLayers >= 999) ? 999 : std::clamp(static_cast<int32_t>(gpuLayers), 1, 64))"
    if text.count(old) < 2:
        raise RuntimeError("native gpu layer clamp anchors not found")
    text = text.replace(old, new, 2)
    marker = "        int32_t requestedGpuLayers = 0;\n"
    text = text.replace(
        marker,
        marker + "        // GPU_LAYERS_MAX_V019: 999 means offload every model layer llama.cpp can place on OpenCL.\n",
        1,
    )
    path.write_text(text, encoding="utf-8")


def patch_gpu_fallback() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E4BEngine.kt")
    text = path.read_text(encoding="utf-8")
    if "OPENCL_FAST_FALLBACK_V018" in text:
        return
    anchor = '''            } catch (t: Throwable) {\n                last = t\n                logger.e("E4B", "Backend ${desired.mode.name} load failed ctx=$ctx", t)\n            }\n'''
    replacement = '''            } catch (t: Throwable) {\n                last = t\n                logger.e("E4B", "Backend ${desired.mode.name} load failed ctx=$ctx", t)\n                // OPENCL_FAST_FALLBACK_V018: when device discovery failed, changing\n                // context size cannot fix it. Do not repeat the same GPU probe for\n                // 8K/4K/2K/1K; fall back to CPU immediately.\n                val openClUnavailable = t.message?.contains("OpenCL/Adreno GPU backend is not available") == true ||\n                    t.cause?.message?.contains("OpenCL/Adreno GPU backend is not available") == true\n                if (desired.mode != InferenceBackend.CPU && openClUnavailable) {\n                    logger.w("E4B", "OpenCL device unavailable; skipping remaining GPU context retries")\n                    break\n                }\n            }\n'''
    if anchor not in text:
        raise RuntimeError("E4B fallback anchor not found")
    path.write_text(text.replace(anchor, replacement, 1), encoding="utf-8")


if __name__ == "__main__":
    patch_backend_config()
    patch_ui()
    patch_backend_overlay()
    patch_native_gpu_layers()
    patch_gpu_fallback()
    print("Applied Jinkaku v0.1.19 GPU offload tuning patch")
