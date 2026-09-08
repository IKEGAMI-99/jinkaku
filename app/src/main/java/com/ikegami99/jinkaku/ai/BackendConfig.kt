package com.ikegami99.jinkaku.ai

import android.content.Context

/**
 * Jinkaku is intentionally CPU-only.
 *
 * GPU/OpenCL/Vulkan backends were removed after repeated instability and worse
 * decode performance on the target Android device. Keep the native API shape
 * for now, but never expose or persist a selectable backend.
 */
enum class InferenceBackend(val id: Int, val label: String) {
    CPU(1, "CPU")
}

data class BackendConfig(
    val mode: InferenceBackend = InferenceBackend.CPU,
    val gpuLayers: Int = 0
) {
    val signature: String get() = "CPU"
}

class BackendPreferences(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    init {
        // Remove values left behind by older builds so a stale GPU selection can
        // never be resurrected accidentally.
        prefs.edit()
            .remove(KEY_MODE)
            .remove(KEY_GPU_LAYERS)
            .apply()
    }

    fun get(): BackendConfig = BackendConfig()

    companion object {
        private const val KEY_MODE = "inference_backend"
        private const val KEY_GPU_LAYERS = "gpu_layers"
    }
}
