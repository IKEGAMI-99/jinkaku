package com.ikegami99.jinkaku.ai

import android.app.ActivityManager
import android.content.Context
import com.ikegami99.jinkaku.data.ChatMessage
import com.ikegami99.jinkaku.data.ROLE_ASSISTANT
import com.ikegami99.jinkaku.data.ROLE_USER
import com.ikegami99.jinkaku.logging.AppLogger
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
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
    private val bridge = UpstreamLlamaBridge()
    private var loadedPath: String? = null
    private var loadedContext: Long = -1L

    private fun tryLoad(model: File, contextSize: Long) {
        unload()
        logger.i(
            "E4B",
            "Loading with upstream llama.cpp CPU runtime ctx=$contextSize jinja=true thinking=true"
        )
        bridge.load(model.absolutePath, contextSize.toInt())
        loadedPath = model.absolutePath
        loadedContext = contextSize
        logger.i("E4B", "Upstream llama.cpp model loaded ctx=$contextSize")
    }

    private fun ensureLoaded(model: File, requestedContext: Long) {
        if (loadedPath == model.absolutePath && loadedContext in 1024L..2048L) return

        val attempts = linkedSetOf(
            requestedContext.coerceIn(1024L, 2048L),
            2048L,
            1024L
        )
        var last: Throwable? = null
        for (ctx in attempts) {
            try {
                tryLoad(model, ctx)
                return
            } catch (t: Throwable) {
                last = t
                logger.e("E4B", "Upstream llama.cpp load failed ctx=$ctx", t)
                logger.w("E4B", "Context creation failed at $ctx; trying smaller profile")
            }
        }
        throw IllegalStateException(
            "E4Bをupstream llama.cppで読み込めませんでした。Q4_K_Mでメモリ不足の場合はQ2_K_Pを試してください。",
            last
        )
    }

    fun generate(
        model: File,
        currentUserMessage: String,
        systemPrompt: String,
        history: List<ChatMessage>,
        contextSize: Long
    ): Flow<GenerationEvent> = flow {
        require(model.exists() && model.length() > 0L) { "E4B GGUF model is not installed" }

        val memoryInfo = ActivityManager.MemoryInfo()
        (context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).getMemoryInfo(memoryInfo)
        logger.i(
            "E4B",
            "Generation start UPSTREAM_LLAMA_CPP model=${model.name} size=${model.length()} requestedCtx=$contextSize history=${history.size} availMem=${memoryInfo.availMem} lowMemory=${memoryInfo.lowMemory}"
        )

        if (memoryInfo.lowMemory || memoryInfo.availMem < 3_500_000_000L) {
            throw IllegalStateException("E4B用の空きRAMが不足しています。バックグラウンドアプリを閉じて再試行してください")
        }
        if (model.length() > memoryInfo.availMem) {
            logger.w("E4B", "Model file is larger than current available RAM; Q2_K_P is recommended")
        }

        ensureLoaded(model, contextSize)

        val roles = ArrayList<String>()
        val contents = ArrayList<String>()
        roles += "system"
        contents += systemPrompt
        history.takeLast(MAX_HISTORY_MESSAGES).forEach { message ->
            when (message.role) {
                ROLE_USER -> {
                    roles += "user"
                    contents += message.content
                }
                ROLE_ASSISTANT -> {
                    roles += "assistant"
                    contents += message.content
                }
            }
        }
        roles += "user"
        contents += currentUserMessage

        val started = System.currentTimeMillis()
        val filter = ThinkingFilter()
        var final = ""
        var rawChars = 0
        var emittedPieces = 0

        bridge.begin(roles.toTypedArray(), contents.toTypedArray(), MAX_GENERATION_TOKENS)
        logger.i("E4B", "Upstream Jinja prompt accepted messages=${roles.size} enableThinking=true")
        emit(GenerationEvent.Thinking)

        try {
            while (true) {
                currentCoroutineContext().ensureActive()
                val bytes = bridge.nextTokenBytes() ?: break
                val chunk = bytes.toString(Charsets.UTF_8)
                rawChars += chunk.length
                emittedPieces++
                if (rawChars > MAX_RAW_OUTPUT_CHARS) {
                    logger.w("E4B", "Generation safety cap reached rawChars=$rawChars; stopping")
                    bridge.stop()
                    break
                }
                val visible = filter.accept(chunk)
                if (visible.isNotEmpty()) {
                    final += visible
                    emit(GenerationEvent.Text(visible))
                }
            }
        } finally {
            bridge.stop()
        }

        val tail = filter.finish()
        if (tail.isNotEmpty()) {
            final += tail
            emit(GenerationEvent.Text(tail))
        }

        val cleaned = cleanControlTokens(final).trim()
        val elapsed = System.currentTimeMillis() - started
        logger.i(
            "E4B",
            "Generation complete UPSTREAM_LLAMA_CPP elapsedMs=$elapsed visibleChars=${cleaned.length} rawChars=$rawChars thoughtMarker=${filter.sawThinkingMarker} pieces=$emittedPieces"
        )
        emit(GenerationEvent.Completed(cleaned, elapsed))
    }.flowOn(Dispatchers.Default)

    private fun cleanControlTokens(value: String): String = value
        .replace("<|channel>final", "")
        .replace("<|turn>model", "")
        .replace("<turn|>", "")
        .replace("<|eot_id|>", "")
        .replace("<|end_of_text|>", "")

    fun stop() {
        runCatching { bridge.stop() }
    }

    fun unload() {
        loadedPath = null
        loadedContext = -1L
        runCatching { bridge.unload() }
            .onFailure { logger.e("E4B", "upstream llama.cpp runtime close failed", it) }
        logger.i("E4B", "Runtime unloaded")
    }

    override fun close() = unload()

    companion object {
        private const val MAX_RAW_OUTPUT_CHARS = 16_000
        private const val MAX_GENERATION_TOKENS = 512
        private const val MAX_HISTORY_MESSAGES = 6
    }
}

private class ThinkingFilter {
    private var inThinking = false
    private var pending = ""
    var sawThinkingMarker: Boolean = false
        private set

    private val startMarkers = listOf(
        "<|channel>thought",
        "<|channel>analysis",
        "<think>",
        "<|think|>"
    )
    private val endMarkers = listOf(
        "<channel|>",
        "</think>",
        "<|channel>final"
    )
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
                    sawThinkingMarker = true
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
