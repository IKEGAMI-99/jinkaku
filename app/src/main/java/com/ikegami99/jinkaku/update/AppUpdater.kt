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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

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
            connectTimeout = 15_000
            readTimeout = 20_000
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

    fun download(info: UpdateInfo): Long {
        val relativePath = "updates/jinkaku-${info.versionName}-b${info.versionCode}.apk"
        val file = File(context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), relativePath).also {
            it.parentFile?.mkdirs()
            if (it.exists()) it.delete()
        }
        val request = DownloadManager.Request(Uri.parse(info.apkUrl))
            .setTitle("Jinkaku ${info.versionName} build ${info.versionCode}")
            .setDescription("Application update")
            .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            .setDestinationInExternalFilesDir(context, Environment.DIRECTORY_DOWNLOADS, relativePath)
        val id = (context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager).enqueue(request)
        context.getSharedPreferences("update", Context.MODE_PRIVATE).edit()
            .putLong("id", id)
            .putString("path", file.absolutePath)
            .putInt("versionCode", info.versionCode)
            .apply()
        logger.i("UPDATE", "APK download queued id=$id code=${info.versionCode} path=${file.absolutePath}")
        return id
    }

    fun installDownloaded(): Boolean {
        val prefs = context.getSharedPreferences("update", Context.MODE_PRIVATE)
        val path = prefs.getString("path", null) ?: return false
        val file = File(path)
        if (!file.exists() || file.length() == 0L) {
            logger.w("UPDATE", "Install requested before APK was ready path=$path")
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
}
