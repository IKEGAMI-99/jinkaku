package com.ikegami99.jinkaku.ai

data class NativeInferenceStats(
    val promptTokens: Int,
    val generatedTokens: Int,
    val contextSize: Int,
    val contextUsed: Int,
    val prefillMicros: Long,
    val decodeMicros: Long,
    val maxGenerationTokens: Int,
    val backend: String
)

internal class UpstreamLlamaBridge {
    init {
        val error = nativeInit()
        check(error == null) { "llama.cpp初期化失敗: $error" }
    }

    fun load(modelPath: String, contextSize: Int) {
        val error = nativeLoad(modelPath, contextSize)
        check(error == null) { "llama.cppモデル読込失敗: $error" }
    }

    fun begin(roles: Array<String>, contents: Array<String>, maxTokens: Int) {
        val error = nativeBegin(roles, contents, maxTokens)
        check(error == null) { "llama.cpp推論開始失敗: $error" }
    }

    fun nextTokenBytes(): ByteArray? = nativeNext()

    fun stats(): NativeInferenceStats {
        val raw = nativeStats()
        check(raw.size >= 7) { "llama.cpp統計取得失敗" }
        return NativeInferenceStats(
            promptTokens = raw[0].toInt(),
            generatedTokens = raw[1].toInt(),
            contextSize = raw[2].toInt(),
            contextUsed = raw[3].toInt(),
            prefillMicros = raw[4],
            decodeMicros = raw[5],
            maxGenerationTokens = raw[6].toInt(),
            backend = "CPU"
        )
    }

    fun stop() = nativeStop()

    fun unload() = nativeUnload()

    private external fun nativeInit(): String?
    private external fun nativeLoad(modelPath: String, contextSize: Int): String?
    private external fun nativeBegin(roles: Array<String>, contents: Array<String>, maxTokens: Int): String?
    private external fun nativeNext(): ByteArray?
    private external fun nativeStats(): LongArray
    private external fun nativeStop()
    private external fun nativeUnload()

    companion object {
        init {
            System.loadLibrary("jinkaku_llama")
        }
    }
}
