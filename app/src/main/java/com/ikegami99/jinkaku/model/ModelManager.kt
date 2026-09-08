package com.ikegami99.jinkaku.model

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Environment
import android.provider.OpenableColumns
import com.ikegami99.jinkaku.logging.AppLogger
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.security.MessageDigest

class ModelManager(private val context: Context, private val logger: AppLogger) {
    private val prefs = context.getSharedPreferences("model_downloads", Context.MODE_PRIVATE)
    private val root = File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS) ?: context.filesDir, "models").apply { mkdirs() }
    val e4bFile = File(root, E4B_FILE)
    val e2bFile = File(root, E2B_FILE)

    init {
        listOf(File(root, "$E4B_FILE.importing"), File(root, "$E2B_FILE.importing")).forEach { stale ->
            if (stale.exists() && stale.delete()) logger.w("MODEL", "Removed stale import file ${stale.name}")
        }
    }

    fun isE4BInstalled() = e4bFile.exists() && e4bFile.length() > 4L && runCatching {
        FileInputStream(e4bFile).use { String(it.readNBytes(4), Charsets.US_ASCII) == "GGUF" }
    }.getOrDefault(false)

    fun isE2BInstalled() = e2bFile.exists() && e2bFile.length() > 1_000_000_000L
    fun downloadE4B(): Long = enqueue(E4B_URL, E4B_FILE, "e4b")
    fun downloadE2B(): Long = enqueue(E2B_URL, E2B_FILE, "e2b")

    private fun enqueue(url: String, filename: String, key: String): Long {
        cancelActiveDownload(key)
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

    fun importE4B(uri: Uri, onProgress: (Float?) -> Unit = {}): ImportResult {
        cancelActiveDownload("e4b")
        return importFromUri(uri, e4bFile, ModelType.E4B_GGUF, onProgress)
    }

    fun importE2B(uri: Uri, onProgress: (Float?) -> Unit = {}): ImportResult {
        cancelActiveDownload("e2b")
        return importFromUri(uri, e2bFile, ModelType.E2B_LITERT, onProgress)
    }

    private fun cancelActiveDownload(key: String) {
        val id = prefs.getLong(key, -1L)
        if (id < 0) return
        val dm = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        val current = status(key)
        if (current == null) {
            prefs.edit().remove(key).apply()
            return
        }
        if (current.status == DownloadManager.STATUS_PENDING || current.status == DownloadManager.STATUS_RUNNING || current.status == DownloadManager.STATUS_PAUSED) {
            dm.remove(id)
            prefs.edit().remove(key).apply()
            logger.w("MODEL", "Cancelled active download key=$key id=$id before replacement")
        }
    }

    private fun importFromUri(uri: Uri, target: File, type: ModelType, onProgress: (Float?) -> Unit): ImportResult {
        val resolver = context.contentResolver
        val sourceName = queryDisplayName(uri) ?: "selected model"
        val sourceSize = querySize(uri)
        val required = if (sourceSize > 0) sourceSize + IMPORT_HEADROOM_BYTES else IMPORT_HEADROOM_BYTES
        if (root.usableSpace < required) {
            throw IllegalStateException("空き容量不足です。取り込みには約${formatBytes(required)}の空きが必要です。既存モデルを残したまま安全にコピーするため、一時的に追加容量を使います。")
        }

        val temp = File(root, target.name + ".importing")
        if (temp.exists()) temp.delete()
        logger.i("MODEL", "Local import start type=$type source=$sourceName size=$sourceSize")

        var copied = 0L
        var lastReport = 0L
        try {
            val input = resolver.openInputStream(uri) ?: throw IllegalArgumentException("選択したファイルを開けません")
            input.use { src ->
                FileOutputStream(temp).use { out ->
                    val buffer = ByteArray(COPY_BUFFER_BYTES)
                    while (true) {
                        val count = src.read(buffer)
                        if (count < 0) break
                        if (count == 0) continue
                        out.write(buffer, 0, count)
                        copied += count
                        if (copied - lastReport >= PROGRESS_REPORT_BYTES) {
                            onProgress(if (sourceSize > 0) (copied.toDouble() / sourceSize).toFloat().coerceIn(0f, 1f) else null)
                            lastReport = copied
                        }
                    }
                    out.flush()
                    out.fd.sync()
                }
            }
            if (sourceSize > 0 && copied != sourceSize) {
                throw IllegalStateException("コピーサイズが一致しません: expected=$sourceSize actual=$copied")
            }
            validateImported(temp, type)

            if (target.exists() && !target.delete()) throw IllegalStateException("既存モデルを置き換えられません")
            if (!temp.renameTo(target)) throw IllegalStateException("モデルファイルを確定できません")
            onProgress(1f)
            logger.i("MODEL", "Local import complete type=$type source=$sourceName bytes=$copied target=${target.absolutePath}")
            return ImportResult(sourceName, copied)
        } catch (t: Throwable) {
            temp.delete()
            logger.e("MODEL", "Local import failed type=$type source=$sourceName copied=$copied", t)
            throw t
        }
    }

    private fun validateImported(file: File, type: ModelType) {
        if (!file.exists() || file.length() <= 0L) throw IllegalArgumentException("選択したファイルが空です")
        when (type) {
            ModelType.E4B_GGUF -> {
                if (file.length() < 100L * 1024L * 1024L) throw IllegalArgumentException("GGUFとして小さすぎるファイルです")
                val magic = FileInputStream(file).use { String(it.readNBytes(4), Charsets.US_ASCII) }
                if (magic != "GGUF") throw IllegalArgumentException("GGUFファイルではありません (header=$magic)")
            }
            ModelType.E2B_LITERT -> {
                if (file.length() < 1_000_000_000L) throw IllegalArgumentException("Gemma 4 E2B LiteRT-LMとして小さすぎるファイルです")
            }
        }
    }

    private fun queryDisplayName(uri: Uri): String? = runCatching {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
            if (!cursor.moveToFirst()) return@use null
            val index = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (index >= 0) cursor.getString(index) else null
        }
    }.getOrNull()

    private fun querySize(uri: Uri): Long = runCatching {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { cursor ->
            if (!cursor.moveToFirst()) return@use -1L
            val index = cursor.getColumnIndex(OpenableColumns.SIZE)
            if (index >= 0 && !cursor.isNull(index)) cursor.getLong(index) else -1L
        } ?: -1L
    }.getOrDefault(-1L)

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

    fun deleteE4B() { e4bFile.delete(); File(root, e4bFile.name + ".importing").delete(); logger.i("MODEL", "E4B deleted") }
    fun deleteE2B() { e2bFile.delete(); File(root, e2bFile.name + ".importing").delete(); logger.i("MODEL", "E2B deleted") }

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

    private fun formatBytes(bytes: Long): String = when {
        bytes >= 1024L * 1024L * 1024L -> "%.1f GB".format(bytes.toDouble() / (1024L * 1024L * 1024L))
        bytes >= 1024L * 1024L -> "%.1f MB".format(bytes.toDouble() / (1024L * 1024L))
        else -> "$bytes bytes"
    }

    companion object {
        private const val COPY_BUFFER_BYTES = 4 * 1024 * 1024
        private const val PROGRESS_REPORT_BYTES = 32L * 1024L * 1024L
        private const val IMPORT_HEADROOM_BYTES = 256L * 1024L * 1024L
        const val E4B_FILE = "Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf"
        const val E2B_FILE = "gemma-4-E2B-it.litertlm"
        const val E4B_URL = "https://huggingface.co/HauhauCS/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive/resolve/main/Gemma-4-E4B-Uncensored-HauhauCS-Aggressive-Q4_K_M.gguf?download=true"
        const val E2B_URL = "https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it.litertlm?download=true"
        const val E2B_SHA256 = "181938105e0eefd105961417e8da75903eacda102c4fce9ce90f50b97139a63c"
    }
}

private enum class ModelType { E4B_GGUF, E2B_LITERT }
data class ImportResult(val sourceName: String, val bytes: Long)
data class DownloadStatus(val status: Int, val downloaded: Long, val total: Long, val reason: Int) {
    val progress: Float get() = if (total > 0) (downloaded.toDouble() / total).toFloat().coerceIn(0f, 1f) else 0f
}
