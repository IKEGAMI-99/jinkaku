package com.ikegami99.jinkaku.logging

import android.content.Context
import android.os.Build
import com.ikegami99.jinkaku.BuildConfig
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class AppLogger(private val context: Context) {
    private val lock = Any()
    private val logDir = File(context.filesDir, "logs").apply { mkdirs() }
    private val current = File(logDir, "app-current.log")
    private val formatter = SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS", Locale.US)

    init {
        synchronized(lock) {
            rotateIfNeeded()
            if (!current.exists() || current.length() == 0L) {
                appendRaw("Jinkaku Log\nApp Version: ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})\nAndroid: ${Build.VERSION.RELEASE} API ${Build.VERSION.SDK_INT}\nDevice: ${Build.MANUFACTURER} ${Build.MODEL}\nStarted: ${formatter.format(Date())}\n----------------------------------------\n", true)
            }
        }
    }
    fun i(tag: String, message: String) = write("I", tag, message, false)
    fun w(tag: String, message: String) = write("W", tag, message, false)
    fun e(tag: String, message: String, error: Throwable? = null) = write("E", tag, message + (error?.let { " | ${it::class.java.simpleName}: ${it.message}" } ?: ""), true)
    private fun write(level: String, tag: String, message: String, sync: Boolean) = synchronized(lock) {
        rotateIfNeeded(); appendRaw("${formatter.format(Date())} $level/$tag ${message.replace('\n', ' ')}\n", sync)
    }
    private fun appendRaw(text: String, sync: Boolean) {
        FileOutputStream(current, true).use { out -> out.write(text.toByteArray(Charsets.UTF_8)); out.flush(); if (sync) out.fd.sync() }
    }
    private fun rotateIfNeeded() {
        if (!current.exists() || current.length() < 5L * 1024 * 1024) return
        for (i in 4 downTo 1) {
            val src = File(logDir, "app-$i.log"); val dst = File(logDir, "app-${i + 1}.log")
            if (i == 4 && dst.exists()) dst.delete(); if (src.exists()) src.renameTo(dst)
        }
        current.renameTo(File(logDir, "app-1.log"))
    }
    fun exportFile(): File = synchronized(lock) {
        appendRaw("${formatter.format(Date())} I/LOG Export requested\n", true)
        val exportDir = File(context.cacheDir, "exports").apply { mkdirs() }
        val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
        val out = File(exportDir, "Jinkaku_$stamp.log.txt")
        current.copyTo(out, overwrite = true)
        if (out.length() == 0L) out.writeText("Jinkaku Log\nExport fallback header\n", Charsets.UTF_8)
        require(out.length() > 0L) { "Log export is empty" }; out
    }
}
