package com.ikegami99.jinkaku.voice

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.ikegami99.jinkaku.JinkakuViewModel
import com.ikegami99.jinkaku.data.ROLE_ASSISTANT
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/**
 * QWEN_TTS_V086: optional, local voice generation for the last assistant message.
 * TTS output is never written to Chat/Memory or supplied as a user turn.
 */
@Composable
fun JinkakuVoiceDialog(vm: JinkakuViewModel, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val runtime = remember(context) { QwenVoiceRuntime(context) }
    val scope = rememberCoroutineScope()
    val ui by vm.ui.collectAsState()
    val persona = remember(vm) { vm.currentPersona() }
    val lastAssistant = ui.messages.lastOrNull { it.role == ROLE_ASSISTANT }?.content.orEmpty()
    var status by remember { mutableStateOf("音声エンジンは端末内で実行します") }
    var downloading by remember { mutableStateOf(false) }
    var speaking by remember { mutableStateOf(false) }
    var referenceReady by remember { mutableStateOf(runtime.referenceFor(persona).exists()) }
    var showDesigner by remember { mutableStateOf(false) }
    var autoRead by remember { mutableStateOf(QwenVoiceSettings.autoRead(context)) }
    var backend by remember { mutableStateOf(QwenVoiceSettings.backend(context)) }
    var currentJob by remember { mutableStateOf<Job?>(null) }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            currentJob = scope.launch {
                try {
                    status = "参照音声を読み込み中"
                    runtime.importReference(uri, persona)
                    referenceReady = true
                    status = "このPersonaの声として保存しました"
                } catch (e: Exception) {
                    status = e.message ?: "読み込みに失敗しました"
                }
            }
        }
    }

    fun close() {
        currentJob?.cancel()
        runtime.stop()
        onDismiss()
    }

    DisposableEffect(runtime) {
        onDispose { runtime.stop() }
    }

    if (showDesigner) {
        PersonaVoiceDesignerDialog(
            persona = persona,
            onDismiss = { showDesigner = false },
            onVoiceSaved = {
                referenceReady = true
                status = "Personaから生成した声を保存しました"
                showDesigner = false
            },
        )
        return
    }

    AlertDialog(
        onDismissRequest = { if (!downloading && !speaking) close() },
        title = { Text("Qwen3-TTS · Voice") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("日本語 / 0.6B Q4_K_M / CPU・Vulkan GPU / 完全ローカル", style = MaterialTheme.typography.bodySmall)
                Text("モデル: " + if (runtime.ready) "導入済み" else "未導入（約884MB）")
                if (!runtime.ready) {
                    Button(onClick = {
                        downloading = true
                        currentJob = scope.launch {
                            try {
                                runtime.download { progress -> status = progress }
                                status = "Qwen3-TTSモデルを導入しました"
                            } catch (e: Exception) { status = e.message ?: "ダウンロード失敗" }
                            finally { downloading = false }
                        }
                    }, enabled = !downloading && !speaking) {
                        Text(if (downloading) "取得中…" else "モデルをダウンロード")
                    }
                }
                HorizontalDivider()
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    Text("返信を自動読み上げ", modifier = Modifier.weight(1f))
                    Switch(
                        checked = autoRead,
                        onCheckedChange = { value ->
                            autoRead = value
                            QwenVoiceSettings.setAutoRead(context, value)
                        }
                    )
                }
                Text("音声生成の処理方式", style = MaterialTheme.typography.titleSmall)
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    FilterChip(
                        selected = backend == QwenVoiceSettings.CPU,
                        onClick = {
                            backend = QwenVoiceSettings.CPU
                            QwenVoiceSettings.setBackend(context, backend)
                        },
                        enabled = !speaking && !downloading,
                        label = { Text("CPU") }
                    )
                    FilterChip(
                        selected = backend == QwenVoiceSettings.GPU,
                        onClick = {
                            backend = QwenVoiceSettings.GPU
                            QwenVoiceSettings.setBackend(context, backend)
                        },
                        enabled = !speaking && !downloading,
                        label = { Text("GPU (Vulkan)") }
                    )
                }
                Text("GPUは実験的機能です。端末で使用できない場合はCPUに戻してください。", style = MaterialTheme.typography.bodySmall)
                HorizontalDivider()
                Text("Personaの声: " + if (referenceReady) "設定済み" else "未設定")
                OutlinedButton(
                    onClick = { picker.launch(arrayOf("audio/wav", "audio/x-wav", "audio/*")) },
                    enabled = !downloading && !speaking
                ) { Text("参照音声を選ぶ（WAV）") }
                OutlinedButton(
                    onClick = { showDesigner = true },
                    enabled = !downloading && !speaking
                ) { Text("Personaから声を自動生成（1.7B）") }
                Text("短いPCM WAV音声を登録すると、そのPersonaに声を固定できます。本人の許可がある音声だけを使用してください。",
                    style = MaterialTheme.typography.bodySmall)
                HorizontalDivider()
                Text("読み上げ対象（最新のAI返信）", style = MaterialTheme.typography.titleSmall)
                Text(lastAssistant.take(240).ifBlank { "読み上げ可能なAI返信がありません" },
                    style = MaterialTheme.typography.bodyMedium)
                Text(status, color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.bodySmall)
            }
        },
        confirmButton = {
            Button(onClick = {
                speaking = true
                status = "音声を生成中（" + backend + "処理）"
                currentJob = scope.launch {
                    try {
                        runtime.speak(lastAssistant, persona)
                        status = "再生完了"
                    } catch (e: Exception) { status = e.message ?: "音声生成に失敗しました" }
                    finally { speaking = false }
                }
            }, enabled = runtime.ready && lastAssistant.isNotBlank() && !ui.busy &&
                    !downloading && !speaking) {
                Text(if (speaking) "生成・再生中" else "▶ 読み上げ")
            }
        },
        dismissButton = {
            TextButton(onClick = { close() }) { Text("閉じる / 停止") }
        }
    )
}
