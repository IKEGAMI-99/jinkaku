package com.ikegami99.jinkaku.ai

import android.content.Context

enum class InferenceBackend(val id: Int, val label: String) {
    AUTO(0, "Auto"),
    CPU(1, "CPU"),
    GPU(2, "GPU · OpenCL"),
    HYBRID(3, "CPU + GPU");

    companion object {
        fun fromName(value: String?): InferenceBackend = entries.firstOrNull { it.name == value } ?: AUTO
    }
}

data class BackendConfig(
    val mode: InferenceBackend = InferenceBackend.AUTO,
    val gpuLayers: Int = 20
) {
    val signature: String get() = "${mode.name}:$gpuLayers"
}

class BackendPreferences(context: Context) {
    private val prefs = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    fun get(): BackendConfig = BackendConfig(
        mode = InferenceBackend.fromName(prefs.getString(KEY_MODE, InferenceBackend.AUTO.name)),
        gpuLayers = prefs.getInt(KEY_GPU_LAYERS, 20).coerceIn(1, 64)
    )

    fun setMode(mode: InferenceBackend) {
        prefs.edit().putString(KEY_MODE, mode.name).apply()
    }

    fun setGpuLayers(value: Int) {
        prefs.edit().putInt(KEY_GPU_LAYERS, value.coerceIn(1, 64)).apply()
    }

    companion object {
        private const val KEY_MODE = "inference_backend"
        private const val KEY_GPU_LAYERS = "gpu_layers"
    }
}
