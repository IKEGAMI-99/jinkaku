package com.ikegami99.jinkaku.ai

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

    fun stop() = nativeStop()

    fun unload() = nativeUnload()

    private external fun nativeInit(): String?
    private external fun nativeLoad(modelPath: String, contextSize: Int): String?
    private external fun nativeBegin(roles: Array<String>, contents: Array<String>, maxTokens: Int): String?
    private external fun nativeNext(): ByteArray?
    private external fun nativeStop()
    private external fun nativeUnload()

    companion object {
        init {
            System.loadLibrary("jinkaku_llama")
        }
    }
}
