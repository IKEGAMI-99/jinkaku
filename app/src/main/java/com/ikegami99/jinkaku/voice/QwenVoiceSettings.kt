package com.ikegami99.jinkaku.voice

import android.content.Context
import android.content.SharedPreferences
import com.qwen.tts.studio.engine.QwenEngine

/**
 * Voice preferences are isolated from the chat/Memory settings.
 * CPU is the safe default. GPU is opt-in and must really initialize.
 */
internal object QwenVoiceSettings {
    const val AUTO_READ = "voice_auto_read_v088"
    const val BACKEND = "voice_backend_v088"
    const val CPU = "CPU"
    const val GPU = "GPU"

    fun prefs(context: Context): SharedPreferences =
        context.applicationContext.getSharedPreferences("qwen3_voice_settings", Context.MODE_PRIVATE)

    fun autoRead(context: Context): Boolean = prefs(context).getBoolean(AUTO_READ, true)

    fun backend(context: Context): String =
        prefs(context).getString(BACKEND, CPU).takeIf { it == GPU } ?: CPU

    fun setAutoRead(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean(AUTO_READ, enabled).apply()
    }

    fun setBackend(context: Context, selected: String) {
        require(selected == CPU || selected == GPU)
        prefs(context).edit().putString(BACKEND, selected).apply()
    }

    fun configure(native: QwenEngine, context: Context) {
        val selected = backend(context)
        val preference = if (selected == GPU) QwenEngine.BACKEND_GPU else QwenEngine.BACKEND_CPU
        check(native.setBackendPreference(preference)) {
            "音声バックエンドを切り替えられません。ほかの音声生成が終了してから再試行してください"
        }
        native.setCpuThreads(4)
    }

    fun verifyActive(native: QwenEngine, context: Context): String {
        val active = native.getActiveBackendName().orEmpty()
        if (backend(context) == GPU) {
            check(active.isNotBlank() && !active.contains("CPU", ignoreCase = true)) {
                "GPU (Vulkan) を初期化できませんでした。CPUに切り替えてください"
            }
        }
        return active.ifBlank { "不明" }
    }
}
