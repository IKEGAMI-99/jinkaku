package com.ikegami99.jinkaku.ai

import android.content.Context
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.ExperimentalApi
import com.google.ai.edge.litertlm.ExperimentalFlags
import com.google.ai.edge.litertlm.LogSeverity
import com.google.ai.edge.litertlm.SamplerConfig
import com.google.ai.edge.litertlm.ThinkingConfig
import com.ikegami99.jinkaku.data.ChatMessage
import com.ikegami99.jinkaku.logging.AppLogger
import org.json.JSONObject
import java.io.File

/**
 * Gemma 4 E2B LiteRT-LM memory worker.
 *
 * Runtime profile intentionally mirrors E2B-SpeedLab's fast path:
 * LiteRT-LM -> GPU -> speculative decoding (MTP), greedy decode and thinking off.
 */
@OptIn(ExperimentalApi::class)
class E2BMemoryEngine(
    private val context: Context,
    private val logger: AppLogger,
    private val memory: MemoryEngine
) {
    suspend fun extract(model: File, messages: List<ChatMessage>): Int {
        if (messages.isEmpty()) return 0
        require(model.exists() && model.length() > 0) { "E2B LiteRT model is not installed" }

        logger.i(
            "E2B",
            "Memory extraction start count=${messages.size} runtime=LiteRT-LM backend=GPU mtp=ON ctx=$MAX_CONTEXT_TOKENS"
        )

        ExperimentalFlags.enableBenchmark = true
        ExperimentalFlags.enableSpeculativeDecoding = true
        Engine.setNativeMinLogSeverity(LogSeverity.ERROR)

        val config = EngineConfig(
            modelPath = model.absolutePath,
            backend = Backend.GPU(),
            visionBackend = null,
            audioBackend = null,
            maxNumTokens = MAX_CONTEXT_TOKENS,
            cacheDir = context.cacheDir.absolutePath
        )

        var inserted = 0
        Engine(config).use { engine ->
            engine.initialize()

            // Keep each memory item in a fresh conversation so prompt history cannot silently
            // consume the small fast-profile context window during maintenance batches.
            messages.forEach { msg ->
                engine.createConversation(memoryConversationConfig()).use { conversation ->
                    val response = conversation.sendMessage(
                        "User message id=${msg.id}:\n${msg.content}\nReturn JSON only."
                    )
                    inserted += parseAndStore(response.toString(), msg.id)
                }
            }
        }

        logger.i("E2B", "Memory extraction complete inserted=$inserted backend=GPU mtp=ON")
        return inserted
    }

    private fun memoryConversationConfig() = ConversationConfig(
        systemInstruction = Contents.of(MEMORY_SYSTEM),
        tools = emptyList(),
        automaticToolCalling = false,
        channels = emptyList(),
        samplerConfig = SamplerConfig(
            topK = 1,
            topP = 1.0,
            temperature = 0.0,
            seed = 0
        ),
        prefillPrefaceOnInit = false,
        maxOutputToken = MAX_OUTPUT_TOKENS,
        thinkingConfig = ThinkingConfig(
            enableThinking = false,
            thinkingTokenBudget = 0
        ),
        enableResponseFormat = false
    )

    private fun parseAndStore(raw: String, sourceId: Long): Int {
        val jsonText = raw.substringAfter('{', "").let {
            if (it.isEmpty()) "" else "{" + it.substringBeforeLast('}', "") + "}"
        }
        if (jsonText.isBlank()) return 0

        return runCatching {
            val root = JSONObject(jsonText)
            val arr = root.optJSONArray("memories") ?: return@runCatching 0
            var n = 0
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                val content = o.optString("content").trim()
                val type = o.optString("type", "EPISODIC").uppercase()
                    .takeIf { it in ALLOWED_TYPES } ?: "EPISODIC"
                val importance = when (o.optString("importance").uppercase()) {
                    "CORE" -> 3
                    "HIGH" -> 2
                    "NORMAL" -> 1
                    else -> 0
                }
                val confidence = when (o.optString("confidence").uppercase()) {
                    "EXPLICIT" -> 2
                    "STRONG_INFERENCE" -> 1
                    else -> 0
                }
                val origin = o.optString("origin", "USER_EXPLICIT").uppercase()
                    .takeIf { it in ALLOWED_ORIGINS } ?: "USER_EXPLICIT"
                val tagsArray = o.optJSONArray("tags")
                val tags = buildList {
                    if (tagsArray != null) {
                        for (j in 0 until tagsArray.length()) add(tagsArray.optString(j))
                    }
                }.filter { it.isNotBlank() }.take(8)

                if (
                    importance >= 1 &&
                    memory.addCandidate(content, type, importance, confidence, origin, sourceId, tags)
                ) n++
            }
            n
        }.onFailure {
            logger.w("E2B", "Memory JSON rejected: ${it.message}")
        }.getOrDefault(0)
    }

    companion object {
        private const val MAX_CONTEXT_TOKENS = 2048
        private const val MAX_OUTPUT_TOKENS = 256

        private val ALLOWED_TYPES = setOf(
            "USER",
            "SELF",
            "RELATIONSHIP",
            "EPISODIC",
            "PREFERENCE",
            "PROJECT"
        )
        private val ALLOWED_ORIGINS = setOf(
            "USER_EXPLICIT",
            "USER_INFERRED",
            "AI_SELF",
            "SYSTEM",
            "PROJECT"
        )

        private const val MEMORY_SYSTEM = """You are a local memory extraction worker. Do not chat and do not reveal reasoning. Extract only durable facts, preferences, project state, relationship facts, or episodes worth remembering. Ignore transient small talk. Return exactly one JSON object: {"memories":[{"content":"concise memory","type":"USER|SELF|RELATIONSHIP|EPISODIC|PREFERENCE|PROJECT","importance":"CORE|HIGH|NORMAL|LOW","confidence":"EXPLICIT|STRONG_INFERENCE|WEAK_INFERENCE","origin":"USER_EXPLICIT|USER_INFERRED|AI_SELF|SYSTEM|PROJECT","tags":["tag"]}]}. Use an empty memories array when nothing is worth storing."""
    }
}
