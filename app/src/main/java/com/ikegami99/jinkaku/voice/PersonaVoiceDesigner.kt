package com.ikegami99.jinkaku.voice

import android.content.Context
import android.media.MediaPlayer
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.qwen.tts.studio.engine.QwenEngine
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * PERSONA_VOICE_V087
 * Free-form Qwen3-TTS 1.7B VoiceDesign creates a WAV reference for the
 * existing 0.6B Base voice clone. Nothing is injected into chat or Memory.
 */
internal object PersonaVoicePrompt {
    fun fromPersona(persona: String): String {
        val p = persona.lowercase()
        val parts = mutableListOf("A natural-sounding adult Japanese-speaking voice")
        if (listOf("女性", "女の子", "少女", "彼女", "お姉さん", "女子").any { it in p }) parts += "with a feminine timbre"
        else if (listOf("男性", "男の子", "少年", "彼氏", "お兄さん", "男子").any { it in p }) parts += "with a masculine timbre"
        if (listOf("明る", "元気", "陽気", "活発", "ポジティブ").any { it in p }) parts += "bright and energetic"
        if (listOf("優し", "柔らか", "穏やか", "癒", "親切").any { it in p }) parts += "warm, gentle and soft"
        if (listOf("生意気", "いたずら", "小悪魔", "ツンデレ", "皮肉", "強気").any { it in p }) parts += "playful, mischievous and expressive"
        if (listOf("甘え", "照れ", "恥ずかし", "かわいい", "可愛い").any { it in p }) parts += "affectionate with a slightly shy intonation"
        if (listOf("冷静", "落ち着", "知的", "クール", "無口").any { it in p }) parts += "composed, articulate and restrained"
        if (listOf("低い声", "低音", "ハスキー").any { it in p }) parts += "with a lower pitch"
        if (listOf("高い声", "高音", "澄んだ", "透明感").any { it in p }) parts += "with a clear, light upper register"
        if (listOf("早口", "テンポが速", "話すのが速").any { it in p }) parts += "with a lively quick speaking rhythm"
        if (listOf("ゆっくり", "ゆったり", "のんびり").any { it in p }) parts += "with an unhurried speaking rhythm"
        if (parts.size == 1) parts += "friendly, expressive and conversational"
        return parts.joinToString(", ") + ". Natural Japanese pronunciation, consistent timbre, clean studio audio."
    }

    fun variant(base: String, index: Int): String = base + when (index) {
        0 -> " Speak naturally and warmly with subtle, expressive intonation."
        1 -> " Speak with brighter, more animated intonation and a playful rhythm."
        else -> " Speak with a calmer, softer cadence and a slightly intimate tone."
    }
}

internal class PersonaVoiceDesigner(context: Context) {
    private val app = context.applicationContext
    private val voice = QwenVoiceRuntime(app)
    private val talker = "qwen-talker-1.7b-voicedesign-Q4_K_M.gguf"
    private val model = File(voice.modelDir, talker)
    private val endpoint = "https://huggingface.co/Serveurperso/Qwen3-TTS-GGUF/resolve/main/"
    private val prefs = app.getSharedPreferences("persona_voice_design_v087", Context.MODE_PRIVATE)
    private var mediaPlayer: MediaPlayer? = null

    val baseReady: Boolean get() = voice.ready
    val designReady: Boolean get() = validModel(model)

    private fun validModel(file: File): Boolean {
        if (file.length() < 1_000_000_000L) return false
        return runCatching {
            file.inputStream().use { stream ->
                val header = ByteArray(4)
                stream.read(header) == 4 && String(header, Charsets.US_ASCII) == "GGUF"
            }
        }.getOrDefault(false)
    }

    fun promptFor(persona: String): String =
        prefs.getString("prompt_" + key(persona), null) ?: PersonaVoicePrompt.fromPersona(persona)

    private fun key(persona: String) = persona.hashCode().toUInt().toString(16)

    fun savePrompt(persona: String, description: String) {
        prefs.edit().putString("prompt_" + key(persona), description).apply()
    }

    suspend fun download(onProgress: (String) -> Unit) = withContext(Dispatchers.IO) {
        if (designReady) return@withContext
        voice.modelDir.mkdirs()
        val part = File(voice.modelDir, talker + ".part")
        // Retain partial downloads across interrupted connections.
        val previous = part.length()
        val connection = URL(endpoint + talker + "?download=true")
            .openConnection() as HttpURLConnection
        connection.connectTimeout = 30_000
        connection.readTimeout = 90_000
        connection.instanceFollowRedirects = true
        connection.setRequestProperty("User-Agent", "JINKAKU/0.1.84")
        if (previous > 0L) connection.setRequestProperty("Range", "bytes=" + previous + "-")
        try {
            val response = connection.responseCode
            check(response == 200 || response == 206) { "モデル取得 HTTP " + response }
            val append = response == 206 && previous > 0L
            val total = connection.contentLengthLong.takeIf { it > 0L }
                ?.let { it + if (append) previous else 0L }
            connection.inputStream.use { input ->
                FileOutputStream(part, append).use { output ->
                    val buffer = ByteArray(256 * 1024)
                    var copied = if (append) previous else 0L
                    var lastReported = 0L
                    while (true) {
                        val count = input.read(buffer)
                        if (count < 0) break
                        output.write(buffer, 0, count)
                        copied += count
                        if (copied - lastReported >= 12_000_000L) {
                            onProgress("VoiceDesignモデル取得: " + copied / 1_000_000L + " MB")
                            lastReported = copied
                        }
                    }
                    output.fd.sync()
                    if (total != null) check(copied == total) { "ダウンロード未完了。もう一度実行すると再開します" }
                }
            }
            check(validModel(part)) { "モデルファイルが不完全か形式が不正です" }
            if (!part.renameTo(model)) {
                part.copyTo(model, overwrite = true)
                part.delete()
            }
            check(designReady) { "モデルの保存に失敗しました" }
        } finally {
            connection.disconnect()
        }
    }

    suspend fun generate(persona: String, description: String, variant: Int): File =
        withContext(Dispatchers.Default) {
            check(baseReady) { "先に0.6B Baseモデルを導入してください" }
            check(designReady) { "VoiceDesign 1.7Bモデルを導入してください" }
            val instruction = PersonaVoicePrompt.variant(description.trim(), variant)
            require(description.isNotBlank() && description.length <= 1200) {
                "声の説明を1〜1200文字で入力してください"
            }
            val native = QwenEngine()
            try {
                native.setBackendPreference(QwenEngine.BACKEND_CPU)
                native.setCpuThreads(4)
                check(native.loadModels(voice.modelDir.absolutePath, talker)) {
                    native.getLastError() ?: "VoiceDesignモデルを読み込めません"
                }
                check(native.getModelCapabilities()?.supportsInstruction == true) {
                    "この音声エンジンはVoiceDesignの指示生成に対応していません"
                }
                val result = native.synthesize(
                    text = "こんにちは。今日もあなたとお話しできて嬉しいです。よろしくね。",
                    params = QwenEngine.NativeParams(
                        languageId = 2058,
                        instruction = instruction,
                        maxAudioTokens = 480
                    )
                )
                check(result.success && !result.audio.isNullOrEmpty()) {
                    result.errorMsg ?: "VoiceDesignの生成に失敗しました"
                }
                val output = File(app.cacheDir, "persona_voice_" + key(persona) + "_" + variant + ".wav")
                writePcm16Wav(output, result.audio!!, result.sampleRate.takeIf { it > 0 } ?: 24_000)
                output
            } finally {
                native.close()
            }
        }

    fun saveAsPersonaVoice(persona: String, generated: File) {
        require(generated.exists() && generated.length() > 44L) { "プレビュー音声がありません" }
        val target = voice.referenceFor(persona)
        val temp = File(target.parentFile, target.name + ".design-part")
        try {
            generated.copyTo(temp, overwrite = true)
            if (!temp.renameTo(target)) {
                temp.copyTo(target, overwrite = true)
                temp.delete()
            }
        } finally { temp.delete() }
    }

    fun play(file: File) {
        stop()
        val player = MediaPlayer()
        try {
            player.setDataSource(file.absolutePath)
            player.setOnCompletionListener { finished ->
                if (mediaPlayer === finished) mediaPlayer = null
                finished.release()
            }
            player.prepare()
            mediaPlayer = player
            player.start()
        } catch (e: Exception) {
            player.release()
            throw e
        }
    }

    fun stop() {
        mediaPlayer?.let { player ->
            mediaPlayer = null
            runCatching { if (player.isPlaying) player.stop() }
            player.release()
        }
    }

    private fun writePcm16Wav(file: File, samples: FloatArray, sampleRate: Int) {
        val dataBytes = samples.size.toLong() * 2L
        require(dataBytes in 2L..100_000_000L) { "音声が長すぎます" }
        val header = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        header.put("RIFF".toByteArray(Charsets.US_ASCII))
        header.putInt((36L + dataBytes).toInt())
        header.put("WAVEfmt ".toByteArray(Charsets.US_ASCII))
        header.putInt(16)
        header.putShort(1) // PCM
        header.putShort(1) // Mono
        header.putInt(sampleRate)
        header.putInt(sampleRate * 2)
        header.putShort(2)
        header.putShort(16)
        header.put("data".toByteArray(Charsets.US_ASCII))
        header.putInt(dataBytes.toInt())
        FileOutputStream(file).use { output ->
            output.write(header.array())
            val buffer = ByteArray(8192)
            var i = 0
            while (i < samples.size) {
                val amount = minOf(samples.size - i, buffer.size / 2)
                for (j in 0 until amount) {
                    val value = (samples[i + j].coerceIn(-1f, 1f) * 32767f).toInt()
                    buffer[j * 2] = (value and 0xff).toByte()
                    buffer[j * 2 + 1] = ((value shr 8) and 0xff).toByte()
                }
                output.write(buffer, 0, amount * 2)
                i += amount
            }
        }
    }
}

@Composable
internal fun PersonaVoiceDesignerDialog(
    persona: String,
    onDismiss: () -> Unit,
    onVoiceSaved: () -> Unit,
) {
    val context = LocalContext.current
    val designer = remember(context) { PersonaVoiceDesigner(context) }
    val scope = rememberCoroutineScope()
    var description by remember(persona) { mutableStateOf(designer.promptFor(persona)) }
    var downloaded by remember { mutableStateOf(designer.designReady) }
    var busy by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf("Personaから声の特徴を抽出しました。編集して生成できます。") }
    var samples by remember(persona) { mutableStateOf<Map<Int, File>>(emptyMap()) }
    var job by remember { mutableStateOf<Job?>(null) }
    val names = listOf("自然", "明るい", "落ち着いた")

    DisposableEffect(designer) {
        onDispose { designer.stop() }
    }

    fun dismiss() {
        if (!busy) {
            designer.stop()
            onDismiss()
        }
    }

    AlertDialog(
        onDismissRequest = { dismiss() },
        title = { Text("Persona → VoiceDesign") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("人格の特徴から声を設計し、サンプルを保存して通常会話の声として使います。",
                    style = MaterialTheme.typography.bodySmall)
                Text("1.7B VoiceDesign Q4_K_M / CPU / オフライン推論",
                    style = MaterialTheme.typography.bodySmall)
                Text("VoiceDesignモデル: " + if (downloaded) "導入済み" else "未導入（約1.2GB）")
                if (!downloaded) {
                    Button(
                        onClick = {
                            busy = true
                            job = scope.launch {
                                try {
                                    designer.download { status = it }
                                    downloaded = true
                                    status = "VoiceDesignモデルを導入しました"
                                } catch (e: Exception) {
                                    status = e.message ?: "取得失敗"
                                } finally { busy = false }
                            }
                        },
                        enabled = !busy
                    ) { Text("1.7Bモデルをダウンロード") }
                }
                if (!designer.baseReady) {
                    Text("通常の読み上げに使う0.6B Baseモデルも必要です。先にVoice画面で導入してください。",
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall)
                }
                HorizontalDivider()
                Text("声の特徴（Personaから自動生成・編集可能）", style = MaterialTheme.typography.titleSmall)
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it.take(1200) },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 3,
                    maxLines = 6,
                    enabled = !busy,
                    label = { Text("Voice prompt") }
                )
                TextButton(onClick = { description = PersonaVoicePrompt.fromPersona(persona) }, enabled = !busy) {
                    Text("現在のPersonaから再生成")
                }
                HorizontalDivider()
                Text("3種類の音声サンプル", style = MaterialTheme.typography.titleSmall)
                names.forEachIndexed { index, label ->
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Button(
                            onClick = {
                                busy = true
                                designer.stop()
                                designer.savePrompt(persona, description)
                                status = label + " の音声を生成中。CPU処理には時間がかかります。"
                                job = scope.launch {
                                    try {
                                        val file = designer.generate(persona, description, index)
                                        samples = samples + (index to file)
                                        status = label + " の音声が完成しました"
                                        designer.play(file)
                                    } catch (e: Exception) {
                                        status = e.message ?: "生成失敗"
                                    } finally { busy = false }
                                }
                            },
                            enabled = downloaded && designer.baseReady && !busy && description.isNotBlank(),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 8.dp)
                        ) { Text(label + "を生成") }
                        if (samples[index]?.exists() == true) {
                            TextButton(onClick = { designer.play(samples.getValue(index)) }, enabled = !busy) {
                                Text("▶ 再生")
                            }
                            TextButton(
                                onClick = {
                                    try {
                                        designer.savePrompt(persona, description)
                                        designer.saveAsPersonaVoice(persona, samples.getValue(index))
                                        status = "このPersonaの声として保存しました"
                                        designer.stop()
                                        onVoiceSaved()
                                    } catch (e: Exception) { status = e.message ?: "保存失敗" }
                                },
                                enabled = !busy
                            ) { Text("採用") }
                        }
                    }
                }
                Text(status, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
                Text("選んだWAVは端末内のPersona音声として保存します。声の再現度は元のサンプルに左右されます。",
                    style = MaterialTheme.typography.bodySmall)
            }
        },
        confirmButton = {
            TextButton(onClick = { dismiss() }, enabled = !busy) { Text("戻る") }
        }
    )
}
