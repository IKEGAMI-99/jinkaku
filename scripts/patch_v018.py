from pathlib import Path


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")
    if "BACKEND_SETTINGS_V018" in text:
        return

    text = text.replace(
        "import androidx.compose.runtime.mutableStateOf\n",
        "import androidx.compose.runtime.mutableStateOf\nimport androidx.compose.runtime.mutableIntStateOf\n",
        1,
    )
    text = text.replace(
        "import com.ikegami99.jinkaku.ai.InferenceTelemetry\n",
        "import com.ikegami99.jinkaku.ai.BackendPreferences\n"
        "import com.ikegami99.jinkaku.ai.InferenceBackend\n"
        "import com.ikegami99.jinkaku.ai.InferenceTelemetry\n",
        1,
    )

    state_anchor = "    var personaDraft by remember { mutableStateOf(vm.currentPersona()) }\n"
    state_block = '''    var personaDraft by remember { mutableStateOf(vm.currentPersona()) }\n\n    // BACKEND_SETTINGS_V018\n    val backendContext = LocalContext.current\n    val backendPrefs = remember(backendContext) { BackendPreferences(backendContext) }\n    val backendInitial = remember { backendPrefs.get() }\n    var backendMode by remember { mutableStateOf(backendInitial.mode) }\n    var gpuLayers by remember { mutableIntStateOf(backendInitial.gpuLayers) }\n    val telemetry by InferenceTelemetry.state.collectAsStateWithLifecycle()\n'''
    if state_anchor not in text:
        raise RuntimeError("ModernSettingsScreen state anchor not found")
    text = text.replace(state_anchor, state_block, 1)

    infer_anchor = '''                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {\n                    Text("Context window", fontWeight = FontWeight.SemiBold)\n'''
    infer_block = '''                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {\n                    Text("Backend", fontWeight = FontWeight.SemiBold)\n                    Text(\n                        "Vulkanは使用しません。GPUはAdreno OpenCLを使用し、利用できない場合は即座にCPUへ戻ります。",\n                        style = MaterialTheme.typography.bodySmall,\n                        color = MaterialTheme.colorScheme.onSurfaceVariant\n                    )\n                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {\n                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                            listOf(InferenceBackend.AUTO, InferenceBackend.CPU).forEach { mode ->\n                                FilterChip(\n                                    selected = backendMode == mode,\n                                    onClick = { backendMode = mode; backendPrefs.setMode(mode) },\n                                    label = { Text(if (mode == InferenceBackend.AUTO) "Auto" else "CPU") }\n                                )\n                            }\n                        }\n                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                            listOf(InferenceBackend.GPU, InferenceBackend.HYBRID).forEach { mode ->\n                                FilterChip(\n                                    selected = backendMode == mode,\n                                    onClick = { backendMode = mode; backendPrefs.setMode(mode) },\n                                    label = { Text(if (mode == InferenceBackend.GPU) "GPU · OpenCL" else "CPU + GPU") }\n                                )\n                            }\n                        }\n                    }\n                    if (backendMode == InferenceBackend.AUTO || backendMode == InferenceBackend.HYBRID) {\n                        Text("GPU offload layers", fontWeight = FontWeight.SemiBold)\n                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {\n                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                                listOf(8, 16, 24).forEach { layers ->\n                                    FilterChip(\n                                        selected = gpuLayers == layers,\n                                        onClick = { gpuLayers = layers; backendPrefs.setGpuLayers(layers) },\n                                        label = { Text(layers.toString()) }\n                                    )\n                                }\n                            }\n                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                                listOf(32, 42).forEach { layers ->\n                                    FilterChip(\n                                        selected = gpuLayers == layers,\n                                        onClick = { gpuLayers = layers; backendPrefs.setGpuLayers(layers) },\n                                        label = { Text(layers.toString()) }\n                                    )\n                                }\n                            }\n                        }\n                    }\n                    Text(\n                        "現在の実行Backend: ${telemetry.backend}",\n                        style = MaterialTheme.typography.labelMedium,\n                        color = MaterialTheme.colorScheme.secondary\n                    )\n                    HorizontalDivider()\n                    Text("Context window", fontWeight = FontWeight.SemiBold)\n'''
    if infer_anchor not in text:
        raise RuntimeError("Inference settings anchor not found")
    text = text.replace(infer_anchor, infer_block, 1)
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
    patch_ui()
    patch_gpu_fallback()
    print("Applied Jinkaku v0.1.18 build patch")
