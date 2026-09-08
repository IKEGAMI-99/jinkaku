package com.ikegami99.jinkaku.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import java.nio.ByteBuffer
import java.nio.ByteOrder

const val ROLE_USER = "USER"
const val ROLE_ASSISTANT = "ASSISTANT"

data class ChatMessage(val id: Long, val role: String, val content: String, val createdAt: Long, val status: String)
data class ChatSession(val id: Long, val title: String, val createdAt: Long, val updatedAt: Long)
data class MemoryRecord(val id: Long, val content: String, val type: String, val importance: Int, val confidence: Int, val origin: String, val status: String, val embedding: FloatArray, val createdAt: Long, val lastAccessed: Long, val accessCount: Int, val tags: String)

class JinkakuDatabase(context: Context) : SQLiteOpenHelper(context, "jinkaku.db", null, 2) {
    private val appContext = context.applicationContext

    override fun onConfigure(db: SQLiteDatabase) {
        super.onConfigure(db)
        db.setForeignKeyConstraintsEnabled(true)
        db.enableWriteAheadLogging()
    }

    override fun onCreate(db: SQLiteDatabase) {
        val now = System.currentTimeMillis()
        db.execSQL("CREATE TABLE chats(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)")
        db.execSQL("INSERT INTO chats(id,title,created_at,updated_at) VALUES(1,'New chat',?,?)", arrayOf<Any?>(now, now))
        db.execSQL("CREATE TABLE messages(id INTEGER PRIMARY KEY AUTOINCREMENT,chat_id INTEGER NOT NULL DEFAULT 1,role TEXT NOT NULL,content TEXT NOT NULL,created_at INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'COMPLETE',FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE)")
        db.execSQL("CREATE INDEX idx_messages_chat_id ON messages(chat_id,id)")
        db.execSQL("CREATE TABLE memories(id INTEGER PRIMARY KEY AUTOINCREMENT,content TEXT NOT NULL,type TEXT NOT NULL,importance INTEGER NOT NULL,confidence INTEGER NOT NULL,origin TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'ACTIVE',embedding BLOB NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL,last_accessed INTEGER NOT NULL,access_count INTEGER NOT NULL DEFAULT 0,supersedes_id INTEGER,source_message_id INTEGER,tags TEXT NOT NULL DEFAULT '')")
        db.execSQL("CREATE TABLE pending_memory(message_id INTEGER PRIMARY KEY,created_at INTEGER NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,FOREIGN KEY(message_id) REFERENCES messages(id) ON DELETE CASCADE)")
        db.execSQL("CREATE TABLE persona_revisions(id INTEGER PRIMARY KEY AUTOINCREMENT,persona_json TEXT NOT NULL,created_at INTEGER NOT NULL,note TEXT NOT NULL DEFAULT '')")
        val initialPersona = """{"name":"Jinkaku","traits":{"curiosity":0.90,"independence":0.80,"sarcasm":0.35,"empathy":0.70}}"""
        db.execSQL("INSERT INTO persona_revisions(persona_json,created_at,note) VALUES(?,?,?)", arrayOf<Any?>(initialPersona, now, "Initial persona"))
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        if (oldVersion < 2) {
            val now = System.currentTimeMillis()
            db.execSQL("CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL)")
            db.execSQL("INSERT OR IGNORE INTO chats(id,title,created_at,updated_at) VALUES(1,'以前のチャット',?,?)", arrayOf<Any?>(now, now))
            runCatching { db.execSQL("ALTER TABLE messages ADD COLUMN chat_id INTEGER NOT NULL DEFAULT 1") }
            db.execSQL("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id,id)")
        }
    }

    fun ensureInitialChat(): Long {
        readableDatabase.rawQuery("SELECT id FROM chats ORDER BY id LIMIT 1", null).use { c ->
            if (c.moveToFirst()) return c.getLong(0)
        }
        return createChat()
    }

    fun chatExists(chatId: Long): Boolean = readableDatabase.rawQuery(
        "SELECT 1 FROM chats WHERE id=? LIMIT 1",
        arrayOf(chatId.toString())
    ).use { it.moveToFirst() }

    fun createChat(title: String = "New chat"): Long {
        val now = System.currentTimeMillis()
        val v = ContentValues().apply {
            put("title", title)
            put("created_at", now)
            put("updated_at", now)
        }
        return writableDatabase.insertOrThrow("chats", null, v)
    }

    fun listChats(limit: Int = 100): List<ChatSession> {
        val out = mutableListOf<ChatSession>()
        readableDatabase.rawQuery(
            "SELECT id,title,created_at,updated_at FROM chats ORDER BY updated_at DESC,id DESC LIMIT ?",
            arrayOf(limit.toString())
        ).use { c ->
            while (c.moveToNext()) out += ChatSession(c.getLong(0), c.getString(1), c.getLong(2), c.getLong(3))
        }
        return out
    }

    fun maybeTitleChat(chatId: Long, firstUserText: String) {
        val current = readableDatabase.rawQuery("SELECT title FROM chats WHERE id=?", arrayOf(chatId.toString())).use { c ->
            if (c.moveToFirst()) c.getString(0) else return
        }
        if (current != "New chat") return
        val title = firstUserText.replace(Regex("\\s+"), " ").trim().take(32).ifBlank { "New chat" }
        val v = ContentValues().apply {
            put("title", title)
            put("updated_at", System.currentTimeMillis())
        }
        writableDatabase.update("chats", v, "id=?", arrayOf(chatId.toString()))
    }

    private fun touchChat(chatId: Long) {
        val v = ContentValues().apply { put("updated_at", System.currentTimeMillis()) }
        writableDatabase.update("chats", v, "id=?", arrayOf(chatId.toString()))
    }

    fun insertMessage(chatId: Long, role: String, content: String, status: String = "COMPLETE"): Long {
        val v = ContentValues().apply {
            put("chat_id", chatId)
            put("role", role)
            put("content", content)
            put("created_at", System.currentTimeMillis())
            put("status", status)
        }
        val id = writableDatabase.insertOrThrow("messages", null, v)
        touchChat(chatId)
        return id
    }

    fun insertMessage(role: String, content: String, status: String = "COMPLETE"): Long =
        insertMessage(ensureInitialChat(), role, content, status)

    fun recentMessages(chatId: Long, limit: Int = 24): List<ChatMessage> {
        val out = mutableListOf<ChatMessage>()
        readableDatabase.rawQuery(
            "SELECT id,role,content,created_at,status FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            arrayOf(chatId.toString(), limit.toString())
        ).use { c ->
            while (c.moveToNext()) out += ChatMessage(c.getLong(0), c.getString(1), c.getString(2), c.getLong(3), c.getString(4))
        }
        return out.reversed()
    }

    fun recentMessages(limit: Int = 24): List<ChatMessage> = recentMessages(ensureInitialChat(), limit)

    fun queueMemory(messageId: Long) {
        val v = ContentValues().apply {
            put("message_id", messageId)
            put("created_at", System.currentTimeMillis())
        }
        writableDatabase.insertWithOnConflict("pending_memory", null, v, SQLiteDatabase.CONFLICT_IGNORE)
    }

    fun pendingUserMessages(limit: Int = 12): List<ChatMessage> {
        val out = mutableListOf<ChatMessage>()
        readableDatabase.rawQuery(
            "SELECT m.id,m.role,m.content,m.created_at,m.status FROM messages m JOIN pending_memory p ON p.message_id=m.id ORDER BY p.created_at LIMIT ?",
            arrayOf(limit.toString())
        ).use { c ->
            while (c.moveToNext()) out += ChatMessage(c.getLong(0), c.getString(1), c.getString(2), c.getLong(3), c.getString(4))
        }
        return out
    }

    fun clearPending(ids: List<Long>) {
        if (ids.isEmpty()) return
        writableDatabase.beginTransaction()
        try {
            ids.forEach { writableDatabase.delete("pending_memory", "message_id=?", arrayOf(it.toString())) }
            writableDatabase.setTransactionSuccessful()
        } finally {
            writableDatabase.endTransaction()
        }
    }

    fun insertMemory(content: String,type: String,importance: Int,confidence: Int,origin: String,embedding: FloatArray,sourceId: Long?,tags: String): Long {
        val now = System.currentTimeMillis()
        val v = ContentValues().apply {
            put("content", content)
            put("type", type)
            put("importance", importance)
            put("confidence", confidence)
            put("origin", origin)
            put("status", "ACTIVE")
            put("embedding", floatsToBlob(embedding))
            put("created_at", now)
            put("updated_at", now)
            put("last_accessed", now)
            put("access_count", 0)
            if (sourceId != null) put("source_message_id", sourceId)
            put("tags", tags)
        }
        return writableDatabase.insertOrThrow("memories", null, v)
    }

    fun activeMemories(limit: Int = 2000): List<MemoryRecord> {
        val out = mutableListOf<MemoryRecord>()
        readableDatabase.rawQuery("SELECT id,content,type,importance,confidence,origin,status,embedding,created_at,last_accessed,access_count,tags FROM memories WHERE status='ACTIVE' ORDER BY updated_at DESC LIMIT ?", arrayOf(limit.toString())).use { c ->
            while(c.moveToNext()) out += MemoryRecord(c.getLong(0),c.getString(1),c.getString(2),c.getInt(3),c.getInt(4),c.getString(5),c.getString(6),blobToFloats(c.getBlob(7)),c.getLong(8),c.getLong(9),c.getInt(10),c.getString(11))
        }
        return out
    }

    fun updateMemoryEmbedding(id: Long, embedding: FloatArray) {
        val v = ContentValues().apply {
            put("embedding", floatsToBlob(embedding))
            put("updated_at", System.currentTimeMillis())
        }
        writableDatabase.update("memories", v, "id=?", arrayOf(id.toString()))
    }

    fun touchMemories(ids: List<Long>) {
        val now = System.currentTimeMillis()
        ids.forEach { writableDatabase.execSQL("UPDATE memories SET last_accessed=?,access_count=access_count+1 WHERE id=?", arrayOf<Any?>(now,it)) }
    }

    fun clearAllMemories(): Int {
        writableDatabase.beginTransaction()
        return try {
            writableDatabase.delete("pending_memory", null, null)
            val deleted = writableDatabase.delete("memories", null, null)
            writableDatabase.setTransactionSuccessful()
            deleted
        } finally {
            writableDatabase.endTransaction()
        }
    }

    fun memoryCount(): Int = readableDatabase.rawQuery("SELECT COUNT(*) FROM memories WHERE status='ACTIVE'",null).use { c -> c.moveToFirst(); c.getInt(0) }

    fun currentPersona(): String = readableDatabase.rawQuery(
        "SELECT persona_json FROM persona_revisions ORDER BY id DESC LIMIT 1", null
    ).use { c -> if(c.moveToFirst()) c.getString(0) else "{}" }

    fun savePersonaRevision(persona: String, note: String = "User edit"): Long {
        val clean = persona.trim()
        require(clean.isNotEmpty()) { "Personaを空にはできません" }
        val v = ContentValues().apply {
            put("persona_json", clean)
            put("created_at", System.currentTimeMillis())
            put("note", note)
        }
        return writableDatabase.insertOrThrow("persona_revisions", null, v)
    }

    fun checkpoint() { writableDatabase.rawQuery("PRAGMA wal_checkpoint(FULL)",null).use { while(it.moveToNext()) Unit } }
    fun dbFile() = appContext.getDatabasePath("jinkaku.db")

    companion object {
        private fun floatsToBlob(values: FloatArray): ByteArray = ByteBuffer.allocate(values.size*4).order(ByteOrder.LITTLE_ENDIAN).also { b -> values.forEach { b.putFloat(it) } }.array()
        private fun blobToFloats(bytes: ByteArray): FloatArray {
            val b = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
            return FloatArray(bytes.size/4) { b.float }
        }
    }
}