package com.ikegami99.jinkaku.ai

import android.app.ActivityManager
import android.content.Context
import android.system.Os
import com.ikegami99.jinkaku.logging.AppLogger
import io.aatricks.llmedge.text.runtime.SmolLM
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import java.io.File

sealed interface GenerationEvent {
    data object Thinking : GenerationEvent
    data class Text(val value: String) : GenerationEvent
    data class Completed(val finalText: String, val elapsedMs: Long) : GenerationEvent
}

class E4BEngine(
    private val context: Context,
    @Suppress("unused") private val scope: CoroutineScope,
    private val logger: AppLogger
) : AutoCloseable {
    private var runtime: SmolLM? = null
    private var loadedPath: String? = null
    private var loadedContext: Long = -1L

    private suspend fun ensureLoaded(model: File, contextSize: Long): SmolLM {
        val existing = runtime
        if (existing != null && loadedPath == model.absolutePath && loadedContext == contextSize) {
            return existing
        }

        unload()
        runCatching { Os.setenv("GGML_DISABLE_VULKAN", "1", true) }
        runCatching { Os.setenv("GGML_DISABLE_OPENCL", "1", true) }
        logger.i(
            "E4B",
            "Creating direct SmolLM CPU runtime; Vulkan/OpenCL env gates=${System.getenv("GGML_DISABLE_VULKAN")}/${System.getenv("GGML_DISABLE_OPENCL")}"
        )
        val smol = SmolLM(useVulkan = false)
        try {
            smol.load(
                model.absolutePath,
                SmolLM.InferenceParams(
                    temperature = 1.0f,
                    storeChats = false,
                    contextSize = contextSize,
                    numThreads = 4,
                    generationThreads = 2,
                    useMmap = true,
                    useMlock = false,
                    useFlashAttn = false,
                    thinkingMode = SmolLM.ThinkingMode.DEFAULT,
                    reasoningBudget = -1,
                    kvCacheTypeK = SmolLM.KvCacheType.Q8_KV,
                    kvCacheTypeV = SmolLM.KvCacheType.Q8_0,
                    nGpuLayers = 0,
                    nUbatch = 64
                )
            )
            logger.i(
                "E4B",
                "CPU model loaded vulkanEnabled=${smol.isVulkanEnabled()} estimatedNative=${smol.getEstimatedNativeMemoryBytes()} estimatedState=${smol.getEstimatedStateMemoryBytes()}"
            )
            runtime = smol
            loadedPath = model.absolutePath
            loadedContext = contextSize
            return smol
        } catch (t: Throwable) {
            runCatching { smol.close() }
            logger.e("E4B", "Direct CPU model load failed", t)
            throw t
        }
    }

    fun generate(
        model: File,
        prompt: String,
        systemPrompt: String,
        contextSize: Long
    ): Flow<GenerationEvent> = flow {
        require(model.exists() && model.length() > 0L) { "E4B GGUF model is not installed" }

        val safeContext = contextSize.coerceIn(2048L, 4096L)
        val memoryInfo = ActivityManager.MemoryInfo()
        (context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).getMemoryInfo(memoryInfo)
        logger.i(
            "E4B",
            "Generation start CPU_ONLY model=${model.name} size=${model.length()} ctx=$safeContext availMem=${memoryInfo.availMem} lowMemory=${memoryInfo.lowMemory}"
        )

        if (memoryInfo.lowMemory || memoryInfo.availMem < 3_500_000_000L) {
            throw IllegalStateException("E4B用の空きRAMが不足しています。バックグラウンドアプリを閉じて再試行してください")
        }

        val smol = ensureLoaded(model, safeContext)
        smol.clearMessages()
        smol.clearKvCache()
        smol.addSystemPrompt(systemPrompt)

        val started = System.currentTimeMillis()
        val filter = ThinkingFilter()
        var final = ""
        var thinkingSent = false

        emit(GenerationEvent.Thinking)
        thinkingSent = true

        smol.getResponseAsFlow(prompt, Dispatchers.Default, 1).collect { chunk ->
            if (chunk == "[EOG]") return@collect
            val visible = filter.accept(chunk)
            if (visible.isNotEmpty()) {
                if (!thinkingSent) {
                    emit(GenerationEvent.Thinking)
                    thinkingSent = true
                }
                final += visible
                emit(GenerationEvent.Text(visible))
            }
        }

        val tail = filter.finish()
        if (tail.isNotEmpty()) {
            final += tail
            emit(GenerationEvent.Text(tail))
        }

        val elapsed = System.currentTimeMillis() - started
        val metrics = runCatching { smol.getLastGenerationMetrics() }.getOrNull()
        logger.i(
            "E4B",
            "Generation complete elapsedMs=$elapsed chars=${final.length} tokens=${metrics?.tokenCount ?: -1} tokS=${metrics?.tokensPerSecond ?: -1f}"
        )
        emit(GenerationEvent.Completed(final.trim(), elapsed))
    }

    fun unload() {
        val old = runtime
        runtime = null
        loadedPath = null
        loadedContext = -1L
        if (old != null) {
            runCatching { old.close() }.onFailure { logger.e("E4B", "CPU runtime close failed", it) }
        }
        logger.i("E4B", "Runtime unloaded")
    }

    override fun close() = unload()
}

private class ThinkingFilter {
    private var inThinking = false
    private var pending = ""
    private val startMarkers = listOf("<|channel>thought", "<|channel>analysis", "<think>")
    private val endMarkers = listOf("<|channel>final", "</think>", "<channel|>")
    private val maxMarker = (startMarkers + endMarkers).maxOf { it.length }

    fun accept(chunk: String): String {
        pending += chunk
        val out = StringBuilder()
        while (pending.isNotEmpty()) {
            if (!inThinking) {
                val start = startMarkers.map { pending.indexOf(it) }.filter { it >= 0 }.minOrNull()
                if (start != null) {
                    out.append(pending.substring(0, start))
                    val marker = startMarkers.first { pending.startsWith(it, start) }
                    pending = pending.substring(start + marker.length)
                    inThinking = true
                    continue
                }
                val keep = (maxMarker - 1).coerceAtMost(pending.length)
                val safe = pending.length - keep
                if (safe <= 0) break
                out.append(pending.substring(0, safe))
                pending = pending.substring(safe)
            } else {
                val end = endMarkers.map { pending.indexOf(it) }.filter { it >= 0 }.minOrNull()
                if (end != null) {
                    val marker = endMarkers.first { pending.startsWith(it, end) }
                    pending = pending.substring(end + marker.length)
                    inThinking = false
                    continue
                }
                if (pending.length > maxMarker) pending = pending.takeLast(maxMarker) else break
            }
        }
        return out.toString()
    }

    fun finish(): String {
        val tail = if (inThinking) "" else pending
        pending = ""
        return tail
    }
}
