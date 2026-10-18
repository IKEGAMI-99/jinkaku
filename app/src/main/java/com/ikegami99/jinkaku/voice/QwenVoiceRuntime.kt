package com.ikegami99.jinkaku.voice

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.net.Uri
import com.qwen.tts.studio.engine.QwenEngine
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * QWEN_TTS_V086: Qwen3 native engine is isolated from Gemma 4 LiteRT-LM.
 * Models are optional downloads stored in app-private storage, never in the APK.
 */
class QwenVoiceRuntime(context: Context) {
    private val app = context.applicationContext
    val modelDir = File(app.filesDir, "qwen3-tts-models")
    private val tokenizer = "qwen-tokenizer-12hz-Q4_K_M.gguf"
    private val talker = "qwen-talker-0.6b-base-Q4_K_M.gguf"
    private val requirements = listOf(
        tokenizer to 254_974_752L,
        talker to 628_905_056L
    )
    private val baseUrl = "https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF/resolve/main/"
    @Volatile private var track: AudioTrack? = null

    val ready: Boolean get() = requirements.all { (name, size) ->
        File(modelDir, name).length() == size
    }

    fun referenceFor(persona: String): File =
        File(app.filesDir, "qwen_voice_" + persona.hashCode().toUInt().toString(16) + ".wav")

    suspend fun importReference(uri: Uri, persona: String): Unit = withContext(Dispatchers.IO) {
        val target = referenceFor(persona)
        val temp = File(target.parentFile, target.name + ".part")
        try {
            app.contentResolver.openInputStream(uri)?.use { input ->
                temp.outputStream().use { output -> input.copyTo(output) }
            } ?: error("音声ファイルを読み込めません")
            require(temp.length() in 100L..30_000_000L) { "音声ファイルのサイズが不正です" }
            temp.inputStream().use { input ->
                val header = ByteArray(12)
                require(input.read(header) == 12 &&
                    String(header.copyOfRange(0, 4), Charsets.US_ASCII) == "RIFF" &&
                    String(header.copyOfRange(8, 12), Charsets.US_ASCII) == "WAVE") {
                    "PCM WAV形式の音声ファイルを選択してください"
                }
            }
            if (!temp.renameTo(target)) {
                temp.copyTo(target, overwrite = true)
                temp.delete()
            }
        } finally { temp.delete() }
    }

    suspend fun download(onProgress: (String) -> Unit) = withContext(Dispatchers.IO) {
        modelDir.mkdirs()
        requirements.forEachIndexed { index, (name, expected) ->
            val dest = File(modelDir, name)
            if (dest.length() == expected) return@forEachIndexed
            val part = File(modelDir, name + ".part")
            val conn = (URL(baseUrl + name + "?download=true").openConnection() as HttpURLConnection)
            conn.connectTimeout = 30_000
            conn.readTimeout = 60_000
            conn.instanceFollowRedirects = true
            conn.setRequestProperty("User-Agent", "JINKAKU/0.1.83")
            try {
                require(conn.responseCode in 200..299) { "HTTP " + conn.responseCode }
                conn.inputStream.use { input ->
                    part.outputStream().use { output ->
                        val bytes = ByteArray(256 * 1024)
                        var copied = 0L
                        var lastReported = 0L
                        while (true) {
                            val read = input.read(bytes)
                            if (read < 0) break
                            output.write(bytes, 0, read)
                            copied += read
                            if (copied - lastReported > 8_000_000L) {
                                onProgress("モデル " + (index + 1) + "/2: " + (copied / 1_000_000) + " MB")
                                lastReported = copied
                            }
                        }
                        output.flush()
                    }
                }
                require(part.length() == expected) {
                    "サイズ不一致: " + name + " (" + part.length() + "/" + expected + ")"
                }
                if (!part.renameTo(dest)) {
                    part.copyTo(dest, overwrite = true)
                    part.delete()
                }
            } finally {
                conn.disconnect()
                if (part.exists()) part.delete()
            }
        }
        check(ready) { "モデルファイルが不足しています" }
    }

    suspend fun speak(text: String, persona: String) = withContext(Dispatchers.IO) {
        check(ready) { "Qwen3-TTSのモデルを先に取得してください" }
        val cleaned = text.replace(Regex("[\u0000-\u001f]"), " ").trim().take(240)
        require(cleaned.isNotBlank()) { "読み上げる文章がありません" }
        stop()
        val native = QwenEngine()
        try {
            native.setBackendPreference(QwenEngine.BACKEND_CPU)
            native.setCpuThreads(4)
            check(native.loadModels(modelDir.absolutePath, talker)) {
                native.getLastError() ?: "Qwen3-TTSの読み込みに失敗しました"
            }
            val voice = referenceFor(persona).takeIf { it.exists() }?.absolutePath
            val result = native.synthesize(
                cleaned, referenceWav = voice,
                params = QwenEngine.NativeParams(languageId = 2058, maxAudioTokens = 512)
            )
            check(result.success && !result.audio.isNullOrEmpty()) {
                result.errorMsg ?: "音声生成に失敗しました"
            }
            val audio = result.audio!!
            val rate = result.sampleRate.takeIf { it > 0 } ?: 24_000
            val player = AudioTrack.Builder()
                .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                .setAudioFormat(AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_FLOAT)
                    .setSampleRate(rate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                .setTransferMode(AudioTrack.MODE_STATIC)
                .setBufferSizeInBytes(audio.size * 4)
                .build()
            track = player
            check(player.write(audio, 0, audio.size, AudioTrack.WRITE_BLOCKING) > 0) {
                "音声の再生に失敗しました"
            }
            player.play()
            delay(audio.size.toLong() * 1000L / rate + 300L)
        } finally {
            stop()
            native.close()
        }
    }

    fun stop() {
        val player = track
        track = null
        if (player != null) runCatching {
            if (player.playState == AudioTrack.PLAYSTATE_PLAYING) player.stop()
            player.release()
        }
    }
}
