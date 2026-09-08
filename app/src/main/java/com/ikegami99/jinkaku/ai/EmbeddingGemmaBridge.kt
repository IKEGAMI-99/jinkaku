package com.ikegami99.jinkaku.ai

import com.ikegami99.jinkaku.logging.AppLogger
import java.io.File

/**
 * Thin JNI wrapper around the same pinned upstream llama.cpp used by E4B.
 * The embedding model is kept in a separate native model/context so it can
 * remain warm between memory lookups without touching the chat context.
 */
class EmbeddingGemmaBridge(
    private val model: File,
    private val logger: AppLogger
) : AutoCloseable {
    @Volatile private var loaded = false

    @Synchronized
    private fun ensureLoaded() {
        if (loaded) return
        require(model.exists() && model.length() > 0L) { "EmbeddingGemma GGUFが見つかりません" }
        val error = nativeEmbeddingLoad(model.absolutePath)
        check(error == null) { "EmbeddingGemma読込失敗: $error" }
        loaded = true
        logger.i("EMBEDDING", "EmbeddingGemma loaded file=${model.name} size=${model.length()} backend=CPU")
    }

    fun embed(text: String): FloatArray {
        ensureLoaded()
        val result = nativeEmbeddingEncode(text)
            ?: throw IllegalStateException("EmbeddingGemmaがEmbeddingを返しませんでした")
        if (result.isEmpty()) throw IllegalStateException("EmbeddingGemmaが空のEmbeddingを返しました")
        return result
    }

    @Synchronized
    override fun close() {
        if (!loaded) return
        nativeEmbeddingUnload()
        loaded = false
        logger.i("EMBEDDING", "EmbeddingGemma unloaded")
    }

    private external fun nativeEmbeddingLoad(modelPath: String): String?
    private external fun nativeEmbeddingEncode(text: String): FloatArray?
    private external fun nativeEmbeddingUnload()

    companion object {
        init { System.loadLibrary("jinkaku_llama") }
    }
}
