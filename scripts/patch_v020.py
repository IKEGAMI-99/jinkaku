from pathlib import Path

from patch_v018 import (
    patch_backend_config,
    patch_ui,
    patch_backend_overlay,
    patch_native_gpu_layers,
    patch_gpu_fallback,
)


def apply_v019() -> None:
    patch_backend_config()
    patch_ui()
    patch_backend_overlay()
    patch_native_gpu_layers()
    patch_gpu_fallback()


def patch_backend_config_vulkan() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ai/BackendConfig.kt")
    text = path.read_text(encoding="utf-8")
    if "VULKAN_HYBRID(5" in text:
        return
    old = '    GPU(2, "GPU · OpenCL"),\n    HYBRID(3, "CPU + GPU");'
    new = '    GPU(2, "GPU · OpenCL"),\n    HYBRID(3, "CPU + GPU · OpenCL"),\n    VULKAN(4, "GPU · Vulkan"),\n    VULKAN_HYBRID(5, "CPU + GPU · Vulkan");'
    if old not in text:
        raise RuntimeError("BackendConfig enum anchor not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_modern_ui_vulkan() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")
    if "VULKAN_SETTINGS_V020" in text:
        return

    text = text.replace(
        '"Vulkanは使用しません。GPUはAdreno OpenCLを使用し、利用できない場合はCPUへ戻ります。"',
        '"OpenCLとVulkanを比較できます。Vulkanは以前DeviceLostが出たため実験用です。失敗時はCPUへ戻ります。"',
        1,
    )

    anchor = '''                    if (backendMode == InferenceBackend.AUTO || backendMode == InferenceBackend.HYBRID) {\n'''
    vulkan_row = '''                    // VULKAN_SETTINGS_V020\n                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                        listOf(InferenceBackend.VULKAN, InferenceBackend.VULKAN_HYBRID).forEach { mode ->\n                            FilterChip(\n                                selected = backendMode == mode,\n                                onClick = {\n                                    backendMode = mode\n                                    backendPrefs.setMode(mode)\n                                    if (mode == InferenceBackend.VULKAN) {\n                                        gpuLayers = GPU_LAYERS_MAX\n                                        backendPrefs.setGpuLayers(GPU_LAYERS_MAX)\n                                    }\n                                },\n                                label = { Text(if (mode == InferenceBackend.VULKAN) "GPU · Vulkan" else "CPU + GPU · Vulkan") }\n                            )\n                        }\n                    }\n                    if (backendMode == InferenceBackend.AUTO || backendMode == InferenceBackend.HYBRID || backendMode == InferenceBackend.VULKAN_HYBRID) {\n'''
    if anchor not in text:
        raise RuntimeError("Modern UI backend layer anchor not found")
    text = text.replace(anchor, vulkan_row, 1)

    text = text.replace(
        '"8 / 12 / 16 / 20で速度比較できます。MAXは可能な全レイヤーをOpenCLへoffloadします。"',
        '"8 / 12 / 16 / 20で速度比較できます。MAXは選択中のGPU backendへ可能な全レイヤーをoffloadします。"',
        1,
    )
    old_when = '                            InferenceBackend.HYBRID -> "CPU + GPU: 選択したlayersだけAdrenoへoffloadします。"\n'
    new_when = (
        '                            InferenceBackend.HYBRID -> "CPU + GPU · OpenCL: 選択したlayersだけAdrenoへoffloadします。"\n'
        '                            InferenceBackend.VULKAN -> "GPU · Vulkan: MAX offload。Vulkanで可能な全レイヤーをGPUへ載せます。"\n'
        '                            InferenceBackend.VULKAN_HYBRID -> "CPU + GPU · Vulkan: 選択したlayersだけVulkanへoffloadします。"\n'
    )
    if old_when not in text:
        raise RuntimeError("Modern UI backend description anchor not found")
    text = text.replace(old_when, new_when, 1)
    path.write_text(text, encoding="utf-8")


def patch_overlay_vulkan() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/BackendControlOverlay.kt")
    text = path.read_text(encoding="utf-8")
    if "VULKAN_OVERLAY_V020" in text:
        return
    text = text.replace(
        '"Vulkanは使用しません。GPUはAdreno OpenCLを使い、失敗した場合は自動でCPUへ戻ります。"',
        '"OpenCLとVulkanを選択できます。Vulkanは実験用で、失敗した場合はCPUへ戻ります。"',
        1,
    )
    text = text.replace(
        'if (mode == InferenceBackend.GPU) {\n',
        'if (mode == InferenceBackend.GPU || mode == InferenceBackend.VULKAN) {\n',
        1,
    )
    text = text.replace(
        'if (selected == InferenceBackend.AUTO || selected == InferenceBackend.HYBRID) {',
        '// VULKAN_OVERLAY_V020\n                    if (selected == InferenceBackend.AUTO || selected == InferenceBackend.HYBRID || selected == InferenceBackend.VULKAN_HYBRID) {',
        1,
    )
    old_when = '                            InferenceBackend.HYBRID -> "CPU + GPU: 指定したレイヤーだけAdrenoへoffloadします。"\n'
    new_when = (
        '                            InferenceBackend.HYBRID -> "CPU + GPU · OpenCL: 指定したレイヤーだけAdrenoへoffloadします。"\n'
        '                            InferenceBackend.VULKAN -> "GPU · Vulkan: 全レイヤーをVulkanへoffloadします。DeviceLost時はCPUへfallbackします。"\n'
        '                            InferenceBackend.VULKAN_HYBRID -> "CPU + GPU · Vulkan: 指定したレイヤーだけVulkanへoffloadします。"\n'
    )
    if old_when not in text:
        raise RuntimeError("Overlay backend description anchor not found")
    text = text.replace(old_when, new_when, 1)
    path.write_text(text, encoding="utf-8")


def patch_native_vulkan() -> None:
    path = Path("app/src/main/cpp/upstream_llama_jni.cpp")
    text = path.read_text(encoding="utf-8")
    if "VULKAN_BACKEND_V020" in text:
        return

    start = text.index("std::string find_opencl_device() {")
    end = text.index("\n}\n\nvoid append_utf8", start) + 2
    replacement = r'''struct BackendDeviceMatch {
    ggml_backend_dev_t dev = nullptr;
    std::string label;
};

BackendDeviceMatch find_backend_device(const std::string & wantedBackend) {
    std::string wanted = wantedBackend;
    std::transform(wanted.begin(), wanted.end(), wanted.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    for (size_t i = 0; i < ggml_backend_dev_count(); ++i) {
        ggml_backend_dev_t dev = ggml_backend_dev_get(i);
        if (!dev) continue;
        const char * nameRaw = ggml_backend_dev_name(dev);
        const char * descRaw = ggml_backend_dev_description(dev);
        ggml_backend_reg_t reg = ggml_backend_dev_backend_reg(dev);
        const char * regRaw = reg ? ggml_backend_reg_name(reg) : nullptr;
        const std::string name = nameRaw ? nameRaw : "";
        const std::string desc = descRaw ? descRaw : "";
        const std::string regName = regRaw ? regRaw : "";
        std::string probe = regName + " " + name;
        std::transform(probe.begin(), probe.end(), probe.begin(), [](unsigned char c) {
            return static_cast<char>(std::tolower(c));
        });
        LOGI("backend device[%zu] reg=%s name=%s desc=%s", i, regName.c_str(), name.c_str(), desc.c_str());
        if (probe.find(wanted) != std::string::npos) {
            return {dev, desc.empty() ? name : desc};
        }
    }
    return {};
}'''
    text = text[:start] + replacement + text[end:]

    old_probe = '''        const std::string openclDevice = find_opencl_device();\n        const bool hasOpenCl = !openclDevice.empty();\n'''
    new_probe = '''        // VULKAN_BACKEND_V020: resolve OpenCL and Vulkan by backend registry name,\n        // not by the shared Adreno device description.\n        const BackendDeviceMatch opencl = find_backend_device("opencl");\n        const BackendDeviceMatch vulkan = find_backend_device("vulkan");\n        const bool hasOpenCl = opencl.dev != nullptr;\n        const bool hasVulkan = vulkan.dev != nullptr;\n'''
    if old_probe not in text:
        raise RuntimeError("native OpenCL probe anchor not found")
    text = text.replace(old_probe, new_probe, 1)

    switch_start = text.index("        int32_t requestedGpuLayers = 0;\n", text.index("Java_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeLoad"))
    switch_end = text.index("        llama_model_params mparams = llama_model_default_params();", switch_start)
    new_switch = '''        int32_t requestedGpuLayers = 0;\n        ggml_backend_dev_t selectedDevices[2] = {nullptr, nullptr};\n        const auto requestedLayers = ((gpuLayers >= 999) ? 999 : std::clamp(static_cast<int32_t>(gpuLayers), 1, 64));\n        switch (backendMode) {\n            case 0: // AUTO: keep the known-stable OpenCL path as the default GPU backend\n                if (hasOpenCl) {\n                    requestedGpuLayers = requestedLayers;\n                    selectedDevices[0] = opencl.dev;\n                }\n                break;\n            case 1: // CPU\n                requestedGpuLayers = 0;\n                break;\n            case 2: // GPU OpenCL MAX\n                if (!hasOpenCl) return error_string(env, "OpenCL/Adreno GPU backend is not available");\n                requestedGpuLayers = 999;\n                selectedDevices[0] = opencl.dev;\n                break;\n            case 3: // HYBRID OpenCL\n                if (!hasOpenCl) return error_string(env, "OpenCL/Adreno GPU backend is not available");\n                requestedGpuLayers = requestedLayers;\n                selectedDevices[0] = opencl.dev;\n                break;\n            case 4: // GPU Vulkan MAX\n                if (!hasVulkan) return error_string(env, "Vulkan/Adreno GPU backend is not available");\n                requestedGpuLayers = 999;\n                selectedDevices[0] = vulkan.dev;\n                break;\n            case 5: // HYBRID Vulkan\n                if (!hasVulkan) return error_string(env, "Vulkan/Adreno GPU backend is not available");\n                requestedGpuLayers = requestedLayers;\n                selectedDevices[0] = vulkan.dev;\n                break;\n            default:\n                return error_string(env, "unknown backend mode");\n        }\n\n'''
    text = text[:switch_start] + new_switch + text[switch_end:]

    text = text.replace(
        '        mparams.n_gpu_layers = requestedGpuLayers;\n',
        '        mparams.n_gpu_layers = requestedGpuLayers;\n        mparams.devices = selectedDevices[0] ? selectedDevices : nullptr;\n',
        1,
    )

    log_start = text.index('        LOGI(\n            "loading model backendMode=%d opencl=%s gpuLayers=%d",')
    log_end = text.index('        );', log_start) + len('        );')
    new_log = '''        const char * selectedApi = (backendMode == 4 || backendMode == 5) ? "Vulkan" :\n                                   ((backendMode == 0 || backendMode == 2 || backendMode == 3) && selectedDevices[0]) ? "OpenCL" : "CPU";\n        const std::string selectedLabel = selectedDevices[0] == vulkan.dev ? vulkan.label :\n                                          selectedDevices[0] == opencl.dev ? opencl.label : "CPU";\n        LOGI(\n            "loading model backendMode=%d api=%s device=%s gpuLayers=%d",\n            static_cast<int>(backendMode),\n            selectedApi,\n            selectedLabel.c_str(),\n            requestedGpuLayers\n        );'''
    text = text[:log_start] + new_log + text[log_end:]

    old_label = '''        if (requestedGpuLayers <= 0) {\n            g_backend_label = "CPU";\n        } else if (backendMode == 2) {\n            g_backend_label = "GPU · OpenCL";\n        } else {\n            g_backend_label = "CPU+GPU · OpenCL";\n        }\n'''
    new_label = '''        if (requestedGpuLayers <= 0) {\n            g_backend_label = "CPU";\n        } else if (backendMode == 2) {\n            g_backend_label = "GPU · OpenCL";\n        } else if (backendMode == 3 || backendMode == 0) {\n            g_backend_label = "CPU+GPU · OpenCL";\n        } else if (backendMode == 4) {\n            g_backend_label = "GPU · Vulkan";\n        } else {\n            g_backend_label = "CPU+GPU · Vulkan";\n        }\n'''
    if old_label not in text:
        raise RuntimeError("native backend label anchor not found")
    text = text.replace(old_label, new_label, 1)
    path.write_text(text, encoding="utf-8")


def patch_accel_fallback() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E4BEngine.kt")
    text = path.read_text(encoding="utf-8")
    if "ACCEL_FAST_FALLBACK_V020" in text:
        return
    text = text.replace(
        '                val openClUnavailable = t.message?.contains("OpenCL/Adreno GPU backend is not available") == true ||\n                    t.cause?.message?.contains("OpenCL/Adreno GPU backend is not available") == true\n                if (desired.mode != InferenceBackend.CPU && openClUnavailable) {\n                    logger.w("E4B", "OpenCL device unavailable; skipping remaining GPU context retries")\n',
        '                // ACCEL_FAST_FALLBACK_V020\n                val accelUnavailable = t.message?.contains("GPU backend is not available") == true ||\n                    t.cause?.message?.contains("GPU backend is not available") == true\n                if (desired.mode != InferenceBackend.CPU && accelUnavailable) {\n                    logger.w("E4B", "Requested GPU backend unavailable; skipping remaining context retries")\n',
        1,
    )
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    apply_v019()
    patch_backend_config_vulkan()
    patch_modern_ui_vulkan()
    patch_overlay_vulkan()
    patch_native_vulkan()
    patch_accel_fallback()
    print("Applied Jinkaku v0.1.20 Vulkan/OpenCL backend patch")
