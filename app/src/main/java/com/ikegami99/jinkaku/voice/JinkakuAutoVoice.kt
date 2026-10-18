package com.ikegami99.jinkaku.voice

import android.content.SharedPreferences
import android.widget.Toast
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ikegami99.jinkaku.JinkakuViewModel
import com.ikegami99.jinkaku.data.ROLE_ASSISTANT
import com.ikegami99.jinkaku.data.ROLE_USER
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

/**
 * Only newly completed replies to a user message are spoken.
 * Opening an existing chat NEVER replays old messages. A new user turn or
 * chat change cancels obsolete playback, and failed TTS cannot affect chat.
 */
@Composable
fun JinkakuAutoVoice(vm: JinkakuViewModel, chatVisible: Boolean) {
    val context = LocalContext.current
    val runtime = remember(context) { QwenVoiceRuntime(context) }
    val preferences = remember(context) { QwenVoiceSettings.prefs(context) }
    val scope = rememberCoroutineScope()
    val ui by vm.ui.collectAsStateWithLifecycle()
    var enabled by remember { mutableStateOf(QwenVoiceSettings.autoRead(context)) }
    var trackedChat by remember { mutableLongStateOf(Long.MIN_VALUE) }
    var lastUserId by remember { mutableLongStateOf(Long.MIN_VALUE) }
    var lastSpokenId by remember { mutableLongStateOf(Long.MIN_VALUE) }
    var awaitingReply by remember { mutableStateOf(false) }
    var speakJob by remember { mutableStateOf<Job?>(null) }

    DisposableEffect(preferences) {
        val listener = SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
            if (key == QwenVoiceSettings.AUTO_READ) {
                enabled = QwenVoiceSettings.autoRead(context)
            }
        }
        preferences.registerOnSharedPreferenceChangeListener(listener)
        onDispose {
            preferences.unregisterOnSharedPreferenceChangeListener(listener)
            speakJob?.cancel()
            runtime.stop()
        }
    }

    val last = ui.messages.lastOrNull()
    LaunchedEffect(
        ui.currentChatId,
        last?.id,
        last?.role,
        ui.busy,
        enabled,
        chatVisible,
    ) {
        if (trackedChat != ui.currentChatId) {
            trackedChat = ui.currentChatId
            lastUserId = last?.id ?: Long.MIN_VALUE
            lastSpokenId = last?.id ?: Long.MIN_VALUE
            awaitingReply = false
            speakJob?.cancel()
            runtime.stop()
            return@LaunchedEffect
        }
        if (!chatVisible || !enabled) {
            awaitingReply = false
            speakJob?.cancel()
            runtime.stop()
            return@LaunchedEffect
        }
        if (last?.role == ROLE_USER && last.id != lastUserId) {
            lastUserId = last.id
            awaitingReply = true
            speakJob?.cancel()
            runtime.stop()
            return@LaunchedEffect
        }
        if (!ui.busy && last?.role == ROLE_ASSISTANT &&
            awaitingReply && last.id != lastSpokenId
        ) {
            awaitingReply = false
            lastSpokenId = last.id
            if (!runtime.ready) return@LaunchedEffect
            val persona = vm.currentPersona()
            val text = last.content
            speakJob?.cancel()
            speakJob = scope.launch {
                try {
                    runtime.speak(text, persona)
                } catch (error: kotlinx.coroutines.CancellationException) {
                    throw error
                } catch (error: Exception) {
                    Toast.makeText(
                        context,
                        "Qwen3-TTS: " + (error.message ?: "自動読み上げに失敗しました"),
                        Toast.LENGTH_LONG
                    ).show()
                }
            }
        }
    }
}
