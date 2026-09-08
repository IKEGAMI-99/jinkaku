package com.ikegami99.jinkaku.model

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import com.ikegami99.jinkaku.logging.AppLogger
import java.io.File
import java.io.FileInputStream
import java.security.MessageDigest

class ModelManager(private val context: Context, private val logger: AppLogger) {
    private val prefs = context.getSharedPreferences("model_downloads", Context.MODE_PRIVATE)
    private val root = File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), "models").apply { mkdirs() }
    val e4bFile = File(root, E4B_FILE)
    val e2bFile = File(root, E2B_FILE)

    fun isE4BInstalled() = e4bFile.exists() && e4bFile.length() > 4L && runCatching {
        FileInputStream(e4bFile).use { String(it.readNBytes(4), Charsets.US_ASCII) == "GGUF" }
    }.getOrDefault(false)

    fun isE2BInstalled() = e2bFile.exists() && e2bFile.length() > 1_000_000_000L
    fun downloadE4B(): Long = enqueue(E4B_URL, E4B_FILE, "e4b")
    fun downloadE2B(): Long = enqueue(E2B_URL, E2B_FILE, "e2b")

    private fun enqueue(url: String, filename: String, key: String): Long {
        val target = File(root, filename)
        if (target.exists()) target.delete()
        val request = DownloadManager.Request(Uri.parse(url))
            .setTitle("Jinkaku model: $filename")
            .setDescription("Large local model download")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setAllowedOverMetered(true)
            .setAllowedOverRoaming(false)
            .setDestinationInExternalFilesDir(context, Environment.DIRECTORY_DOWNLOADS, "models/$filename")
        val id = (context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(request)
        prefs.edit().putLong(key, id).apply()
        logger.i("MODEL", "Download queued key=$key id=$id")
        return id
    }

    fun status(key: String): DownloadStatus? {
        val id = prefs.getLong(key, -1L)
        if (id < 0) return null
        val dm = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        dm.query(DownloadManager.Query().setFilterById(id)).use { c ->
            if (!c.moveToFirst()) return null
            return DownloadStatus(
                c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS)),
                c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR)),
                c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES)),
                c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_REASON))
            )
        }
    }

    fun deleteE4B() { e4bFile.delete(); logger.i("MODEL", "E4B deleted") }
    fun deleteE2B() { e2bFile.delete(); logger.i("MODEL", "E2B deleted") }

    fun verifyE2BSha256(): Boolean {
        if (!isE2BInstalled()) return false
        val md = MessageDigest.getInstance("SHA-256")
        FileInputStream(e2bFile).use { input ->
            val buf = ByteArray(1024 * 1024)
            while (true) {
                val n = input.read(buf)
                if (n <= 0) break
                md.update(buf, 0, n)
            }
        }
        val hex = md.digest().joinToString("") { "%02x".format(it) }
        logger.i("MODEL", "E2B sha256=$hex")
        return hex.equals(E2B_SHA256, true)
    }

    companion object {
        const val E4B_FILE = "Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf"
        const val E2B_FILE = "gemma-4-E2B-it.litertlm"
        const val E4B_URL = "https://huggingface.co/HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive/resolve/main/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf?download=true"
        const val E2B_URL = "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm?download=true"
        const val E2B_SHA256 = "181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c"
    }
}

data class DownloadStatus(val status: Int, val downloaded: Long, val total: Long, val reason: Int) {
    val progress: Float get() = if (total > 0) (downloaded.toDouble() / total).toFloat().coerceIn(0f, 1f) else 0f
}
