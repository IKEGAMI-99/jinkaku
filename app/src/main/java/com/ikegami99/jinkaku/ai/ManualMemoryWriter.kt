package com.ikegami99.jinkaku.ai

import android.content.Context
import com.ikegami99.jinkaku.data.JinkakuDatabase
import com.ikegami99.jinkaku.logging.AppLogger

object ManualMemoryWriter {
    fun add(
        context: Context,
        logger: AppLogger,
        text: String,
        type: String,
        importance: Int,
        tags: String = ""
    ): Int {
        val clean = text.trim()
        require(clean.isNotBlank()) { "Memory本文が空です" }

        val chunks = chunkMemory(clean)
        val db = JinkakuDatabase(context.applicationContext)
        val embedder = HashingEmbeddingEngine()
        var added = 0
        try {
            val existing = db.activeMemories(100_000).map { it.content.trim() }.toHashSet()
            chunks.forEachIndexed { index, chunk ->
                if (chunk in existing) return@forEachIndexed
                val vector = embedder.embedDocument(chunk)
                val tagSet = linkedSetOf("manual", type.lowercase())
                tags.split(',').map { it.trim() }.filter { it.isNotBlank() }.forEach(tagSet::add)
                if (chunks.size > 1) tagSet += "chunk-${index + 1}-of-${chunks.size}"
                db.insertMemory(
                    content = chunk,
                    type = type,
                    importance = importance.coerceIn(1, 3),
                    confidence = 2,
                    origin = "MANUAL",
                    embedding = vector,
                    sourceId = null,
                    tags = tagSet.joinToString(",")
                )
                existing += chunk
                added++
            }
            logger.i("MEMORY", "Manual memory added count=$added type=$type chunks=${chunks.size}")
            return added
        } finally {
            db.close()
        }
    }

    private fun chunkMemory(text: String, maxChars: Int = 700): List<String> {
        if (text.length <= maxChars) return listOf(text)
        val parts = text.split(Regex("\\n{2,}"))
            .map { it.trim() }
            .filter { it.isNotBlank() }
        val out = mutableListOf<String>()
        val buffer = StringBuilder()

        fun flush() {
            if (buffer.isNotEmpty()) {
                out += buffer.toString().trim()
                buffer.clear()
            }
        }

        parts.forEach { part ->
            if (part.length > maxChars) {
                flush()
                var start = 0
                while (start < part.length) {
                    val end = (start + maxChars).coerceAtMost(part.length)
                    out += part.substring(start, end).trim()
                    start = end
                }
            } else if (buffer.isEmpty()) {
                buffer.append(part)
            } else if (buffer.length + 2 + part.length <= maxChars) {
                buffer.append("\n\n").append(part)
            } else {
                flush()
                buffer.append(part)
            }
        }
        flush()
        return out.filter { it.isNotBlank() }
    }
}
