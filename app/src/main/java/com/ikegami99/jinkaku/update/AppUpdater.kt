package com.ikegami99.jinkaku.update

import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.provider.Settings
import androidx.core.content.FileProvider
import com.ikegami99.jinkaku.BuildConfig
import com.ikegami99.jinkaku.logging.AppLogger
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.ZipFile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class UpdateInfo(val versionName: String, val versionCode: Int, val apkUrl: String)

class AppUpdater(private val context: Context, private val logger: AppLogger) {
    suspend fun check(): UpdateInfo? = withContext(Dispatchers.IO) {
        runCatching {
            val release = getJson("https://api.github.com/repos/IKEGAMI-99/jinkaku/releases/latest")
            val assets = release.getJSONArray("assets")
            var manifestUrl: String? = null
            var apkUrl: String? = null
            for (i in 0 until assets.length()) {
                val a = assets.getJSONObject(i)
                val name = a.getString("name")
                if (name == "version.json") manifestUrl = a.getString("browser_download_url")
                if (name.endsWith(".apk")) apkUrl = a.getString("browser_download_url")
            }
            if (manifestUrl == null || apkUrl == null) return@runCatching null
            val manifest = getJson(manifestUrl)
            val info = UpdateInfo(
                versionName = manifest.getString("versionName"),
                versionCode = manifest.getInt("versionCode"),
                apkUrl = apkUrl
            )
            logger.i(
                "UPDATE",
                "Latest release version=${info.versionName} code=${info.versionCode}; installed=${BuildConfig.VERSION_NAME} code=${BuildConfig.VERSION_CODE}"
            )
            if (info.versionCode > BuildConfig.VERSION_CODE) info else null
        }.onFailure { logger.e("UPDATE", "Update check failed", it) }.getOrNull()
    }

    private fun getJson(url: String): JSONObject {
        val c = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            instanceFollowRedirects = true
            setRequestProperty("Accept", "application/vnd.github+json")
            setRequestProperty("User-Agent", "Jinkaku/${BuildConfig.VERSION_NAME}")
        }
        return try {
            val code = c.responseCode
            if (code !in 200..299) error("HTTP $code while fetching $url")
            c.inputStream.bufferedReader().use { JSONObject(it.readText()) }
        } finally {
            c.disconnect()
        }
    }

    /**
     * Downloads the update without Android DownloadManager.
     *
     * GitHub release assets may redirect to short-lived object URLs. DownloadManager can
     * occasionally remain paused part-way through those transfers without giving Jinkaku a
     * useful recovery path. This downloader owns the transfer, resumes a .part file with Range,
     * retries fresh redirects, reports progress to the UI, fsyncs the result, and verifies that
     * the finished file is actually an APK ZIP before exposing it to the package installer.
     */
    suspend fun download(info: UpdateInfo, onProgress: (Float?) -> Unit = {}): File = withContext(Dispatchers.IO) {
        cancelLegacyDownloadManagerJob()

        val root = File(
            context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS) ?: context.filesDir,
            "updates"
        ).apply { mkdirs() }
        val target = File(root, "jinkaku-${info.versionName}-b${info.versionCode}.apk")
        val partial = File(root, target.name + ".part")
        if (target.exists()) target.delete()

        var lastFailure: Throwable? = null
        repeat(MAX_ATTEMPTS) { attempt ->
            try {
                logger.i(
                    "UPDATE",
                    "APK download attempt=${attempt + 1}/$MAX_ATTEMPTS resumeBytes=${partial.length()} url=${info.apkUrl}"
                )
                downloadAttempt(info.apkUrl, partial, onProgress)
                validateApk(partial)
                if (target.exists() && !target.delete()) {
                    throw IOException("既存の更新APKを置き換えられません")
                }
                if (!partial.renameTo(target)) {
                    partial.copyTo(target, overwrite = true)
                    if (!partial.delete()) logger.w("UPDATE", "Could not delete partial after copy: ${partial.absolutePath}")
                }
                validateApk(target)
                context.getSharedPreferences("update", Context.MODE_PRIVATE).edit()
                    .remove("id")
                    .putString("path", target.absolutePath)
                    .putInt("versionCode", info.versionCode)
                    .apply()
                onProgress(1f)
                logger.i("UPDATE", "APK download complete bytes=${target.length()} path=${target.absolutePath}")
                return@withContext target
            } catch (t: Throwable) {
                lastFailure = t
                logger.e(
                    "UPDATE",
                    "APK download attempt ${attempt + 1}/$MAX_ATTEMPTS failed at ${partial.length()} bytes",
                    t
                )
                if (attempt + 1 < MAX_ATTEMPTS) {
                    Thread.sleep(RETRY_DELAY_MS * (attempt + 1L))
                }
            }
        }
        throw IOException("更新APKのダウンロードに失敗しました", lastFailure)
    }

    private fun downloadAttempt(url: String, partial: File, onProgress: (Float?) -> Unit) {
        partial.parentFile?.mkdirs()
        val requestedOffset = partial.takeIf { it.exists() }?.length() ?: 0L
        val connection = openDownloadConnection(url, requestedOffset)
        try {
            val code = connection.responseCode
            if (code == 416 && requestedOffset > 0L) {
                logger.w("UPDATE", "Server rejected resume offset=$requestedOffset; restarting from zero")
                if (!partial.delete()) logger.w("UPDATE", "Could not clear rejected partial file")
                connection.disconnect()
                downloadAttempt(url, partial, onProgress)
                return
            }
            if (code != HttpURLConnection.HTTP_OK && code != HttpURLConnection.HTTP_PARTIAL) {
                throw IOException("更新APK取得でHTTP $code")
            }

            val append = code == HttpURLConnection.HTTP_PARTIAL && requestedOffset > 0L
            if (!append && requestedOffset > 0L) {
                if (!partial.delete()) throw IOException("古い途中ファイルを削除できません")
            }
            val initialBytes = if (append) requestedOffset else 0L
            val totalBytes = resolveTotalBytes(connection, initialBytes)
            var downloaded = initialBytes
            var lastReportAt = 0L
            var lastReportBytes = downloaded

            if (totalBytes > 0L) {
                onProgress((downloaded.toDouble() / totalBytes).toFloat().coerceIn(0f, 0.999f))
            } else {
                onProgress(null)
            }

            connection.inputStream.use { input ->
                FileOutputStream(partial, append).use { output ->
                    val buffer = ByteArray(COPY_BUFFER_BYTES)
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        if (count == 0) continue
                        output.write(buffer, 0, count)
                        downloaded += count

                        val now = System.currentTimeMillis()
                        if (
                            now - lastReportAt >= PROGRESS_INTERVAL_MS ||
                            downloaded - lastReportBytes >= PROGRESS_BYTES
                        ) {
                            onProgress(
                                if (totalBytes > 0L) {
                                    (downloaded.toDouble() / totalBytes).toFloat().coerceIn(0f, 0.999f)
                                } else null
                            )
                            lastReportAt = now
                            lastReportBytes = downloaded
                        }
                    }
                    output.flush()
                    output.fd.sync()
                }
            }

            if (totalBytes > 0L && downloaded < totalBytes) {
                throw IOException("更新APKが途中で終了しました: $downloaded / $totalBytes bytes")
            }
            logger.i("UPDATE", "APK transfer finished code=$code bytes=$downloaded total=$totalBytes")
        } finally {
            connection.disconnect()
        }
    }

    private fun openDownloadConnection(url: String, resumeOffset: Long): HttpURLConnection {
        var current = URL(url)
        repeat(MAX_REDIRECTS) {
            val connection = (current.openConnection() as HttpURLConnection).apply {
                connectTimeout = CONNECT_TIMEOUT_MS
                readTimeout = READ_TIMEOUT_MS
                instanceFollowRedirects = false
                setRequestProperty("Accept", "application/octet-stream")
                setRequestProperty("User-Agent", "Jinkaku/${BuildConfig.VERSION_NAME}")
                setRequestProperty("Accept-Encoding", "identity")
                if (resumeOffset > 0L) setRequestProperty("Range", "bytes=$resumeOffset-")
            }
            when (val code = connection.responseCode) {
                301, 302, 303, 307, 308 -> {
                    val location = connection.getHeaderField("Location")
                        ?: throw IOException("更新APKのリダイレクト先がありません (HTTP $code)")
                    current = URL(current, location)
                    connection.disconnect()
                }
                else -> return connection
            }
        }
        throw IOException("更新APKのリダイレクト回数が多すぎます")
    }

    private fun resolveTotalBytes(connection: HttpURLConnection, initialBytes: Long): Long {
        val contentRange = connection.getHeaderField("Content-Range")
        val rangedTotal = contentRange
            ?.substringAfterLast('/', "")
            ?.takeIf { it.isNotBlank() && it != "*" }
            ?.toLongOrNull()
        if (rangedTotal != null && rangedTotal > 0L) return rangedTotal

        val length = connection.contentLengthLong
        if (length <= 0L) return -1L
        return if (connection.responseCode == HttpURLConnection.HTTP_PARTIAL) initialBytes + length else length
    }

    private fun validateApk(file: File) {
        if (!file.exists() || file.length() < MIN_APK_BYTES) {
            throw IOException("更新APKが小さすぎるか空です (${file.length()} bytes)")
        }
        val valid = runCatching {
            ZipFile(file).use { zip ->
                zip.getEntry("AndroidManifest.xml") != null && zip.getEntry("resources.arsc") != null
            }
        }.getOrDefault(false)
        if (!valid) throw IOException("ダウンロードしたファイルをAPKとして検証できません")
    }

    private fun cancelLegacyDownloadManagerJob() {
        val prefs = context.getSharedPreferences("update", Context.MODE_PRIVATE)
        val id = prefs.getLong("id", -1L)
        if (id >= 0L) {
            runCatching {
                (context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).remove(id)
            }.onFailure { logger.w("UPDATE", "Could not cancel legacy DownloadManager id=$id: ${it.message}") }
        }
        prefs.edit().remove("id").apply()
    }

    fun installDownloaded(): Boolean {
        val prefs = context.getSharedPreferences("update", Context.MODE_PRIVATE)
        val path = prefs.getString("path", null) ?: return false
        val file = File(path)
        if (!file.exists() || file.length() == 0L) {
            logger.w("UPDATE", "Install requested before APK was ready path=$path")
            return false
        }
        if (runCatching { validateApk(file) }.isFailure) {
            logger.w("UPDATE", "Install requested for invalid APK path=$path")
            return false
        }

        if (!context.packageManager.canRequestPackageInstalls()) {
            logger.w("UPDATE", "Unknown-app install permission is disabled; opening settings")
            return runCatching {
                context.startActivity(
                    Intent(
                        Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:${context.packageName}")
                    ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
                true
            }.onFailure { logger.e("UPDATE", "Failed to open install permission settings", it) }
                .getOrDefault(false)
        }

        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        return runCatching {
            context.startActivity(intent)
            logger.i("UPDATE", "Package installer opened path=$path")
            true
        }.onFailure { logger.e("UPDATE", "Failed to open package installer", it) }
            .getOrDefault(false)
    }

    companion object {
        private const val CONNECT_TIMEOUT_MS = 15_000
        private const val READ_TIMEOUT_MS = 30_000
        private const val MAX_ATTEMPTS = 4
        private const val MAX_REDIRECTS = 8
        private const val RETRY_DELAY_MS = 900L
        private const val COPY_BUFFER_BYTES = 256 * 1024
        private const val PROGRESS_INTERVAL_MS = 250L
        private const val PROGRESS_BYTES = 512L * 1024L
        private const val MIN_APK_BYTES = 1L * 1024L * 1024L
    }
}
