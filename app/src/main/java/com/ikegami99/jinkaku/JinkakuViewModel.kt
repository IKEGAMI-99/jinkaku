package com.ikegami99.jinkaku

import android.app.Application
import android.content.Context
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.ikegami99.jinkaku.ai.E2BMemoryEngine
import com.ikegami99.jinkaku.ai.E4BEngine
import com.ikegami99.jinkaku.ai.GenerationEvent
import com.ikegami99.jinkaku.ai.MemoryEngine
import com.ikegami99.jinkaku.backup.BackupManager
import com.ikegami99.jinkaku.data.ChatMessage
import com.ikegami99.jinkaku.data.ChatSession
import com.ikegami99.jinkaku.data.JinkakuDatabase
import com.ikegami99.jinkaku.data.ROLE_ASSISTANT
import com.ikegami99.jinkaku.data.ROLE_USER
import com.ikegami99.jinkaku.logging.AppLogger
import com.ikegami99.jinkaku.model.DownloadStatus
import com.ikegami99.jinkaku.model.ModelManager
import com.ikegami99.jinkaku.update.AppUpdater
import com.ikegami99.jinkaku.update.UpdateInfo
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File

data class UiState(
    val messages: List<ChatMessage> = emptyList(),
    val chats: List<ChatSession> = emptyList(),
    val currentChatId: Long = -1L,
    val generatingText: String = "",
    val thinking: Boolean = false,
    val busy: Boolean = false,
    val runtimeStatus: String = "IDLE",
    val memoryCount: Int = 0,
    val e4bInstalled: Boolean = false,
    val e2bInstalled: Boolean = false,
    val e4bDownload: DownloadStatus? = null,
    val e2bDownload: DownloadStatus? = null,
    val e4bImporting: Boolean = false,
    val e2bImporting: Boolean = false,
    val e4bImportProgress: Float? = null,
    val e2bImportProgress: Float? = null,
    val contextSize: Long = 2048,
    val error: String? = null,
    val notice: String? = null,
    val updateInfo: UpdateInfo? = null
)

class JinkakuViewModel(app: Application) : AndroidViewModel(app) {
    private val logger: AppLogger = (app as JinkakuApplication).logger
    private var db = JinkakuDatabase(app)
    private var memory = MemoryEngine(db)
    private val models = ModelManager(app, logger)
    private val e4b = E4BEngine(app, viewModelScope, logger)
    private var e2b = E2BMemoryEngine(app, logger, memory)
    private val updater = AppUpdater(app, logger)
    private var backup = BackupManager(app, db, logger)
    private val runtimeMutex = Mutex()
    private var generationJob: Job? = null
    private var memoryIdleJob: Job? = null
    private val prefs = app.getSharedPreferences("settings", Context.MODE_PRIVATE)
    private val previousInferenceInterrupted = prefs.getBoolean(KEY_E4B_ACTIVE, false)
    private var currentChatId: Long = resolveInitialChatId()
    private val initialContext: Long = migrateRuntimeProfile()
    private val _ui = MutableStateFlow(UiState(contextSize = initialContext, currentChatId = currentChatId))
    val ui: StateFlow<UiState> = _ui.asStateFlow()

    init {
        if (previousInferenceInterrupted) {
            logger.w("E4B", "Previous process ended while E4B inference was active; safe mode enabled")
            _ui.value = _ui.value.copy(
                notice = "前回E4B推論中にアプリが終了しました。安全のためContextを1Kへ下げました。"
            )
        }
        refresh()
        viewModelScope.launch {
            while (true) {
                delay(1000)
                refreshDownloads()
            }
        }
    }

    private fun resolveInitialChatId(): Long {
        val stored = prefs.getLong(KEY_CURRENT_CHAT_ID, -1L)
        if (stored > 0L && db.chatExists(stored)) return stored
        val id = db.ensureInitialChat()
        prefs.edit().putLong(KEY_CURRENT_CHAT_ID, id).apply()
        return id
    }

    private fun migrateRuntimeProfile(): Long {
        var context = prefs.getLong("context", 2048L)
        val profile = prefs.getInt(KEY_RUNTIME_PROFILE_VERSION, 0)
        if (profile < RUNTIME_PROFILE_VERSION) {
            context = 2048L
            prefs.edit()
                .putLong("context", context)
                .putInt(KEY_RUNTIME_PROFILE_VERSION, RUNTIME_PROFILE_VERSION)
                .apply()
            logger.i("E4B", "Runtime profile migrated to Gemma4 safe defaults ctx=$context")
        }
        if (previousInferenceInterrupted) {
            context = 1024L
            prefs.edit()
                .putLong("context", context)
                .putBoolean(KEY_E4B_ACTIVE, false)
                .commit()
        }
        return context.coerceIn(1024L, 2048L)
    }

    fun refresh() {
        _ui.value = _ui.value.copy(
            messages = db.recentMessages(currentChatId, 100),
            chats = db.listChats(100),
            currentChatId = currentChatId,
            memoryCount = db.memoryCount(),
            e4bInstalled = models.isE4BInstalled(),
            e2bInstalled = models.isE2BInstalled()
        )
    }

    private fun refreshDownloads() {
        _ui.value = _ui.value.copy(
            e4bDownload = models.status("e4b"),
            e2bDownload = models.status("e2b"),
            e4bInstalled = models.isE4BInstalled(),
            e2bInstalled = models.isE2BInstalled()
        )
    }

    fun newChat() {
        if (_ui.value.busy || _ui.value.e4bImporting || _ui.value.e2bImporting) {
            setError("処理中は新しいチャットを開始できません")
            return
        }
        e4b.unload()
        currentChatId = db.createChat()
        prefs.edit().putLong(KEY_CURRENT_CHAT_ID, currentChatId).apply()
        _ui.value = _ui.value.copy(generatingText = "", thinking = false, runtimeStatus = "IDLE")
        refresh()
        logger.i("CHAT", "New chat created id=$currentChatId")
    }

    fun selectChat(chatId: Long) {
        if (_ui.value.busy || _ui.value.e4bImporting || _ui.value.e2bImporting) {
            setError("処理中はチャットを切り替えられません")
            return
        }
        if (!db.chatExists(chatId)) {
            setError("チャット履歴が見つかりません")
            return
        }
        e4b.unload()
        currentChatId = chatId
        prefs.edit().putLong(KEY_CURRENT_CHAT_ID, chatId).apply()
        _ui.value = _ui.value.copy(generatingText = "", thinking = false, runtimeStatus = "IDLE")
        refresh()
        logger.i("CHAT", "Chat selected id=$chatId")
    }

    fun send(text: String) {
        val clean = text.trim()
        if (clean.isEmpty() || _ui.value.busy) return
        if (_ui.value.e4bImporting || _ui.value.e2bImporting) {
            setError("モデル取り込み中です。完了後に送信してください")
            return
        }
        if (!models.isE4BInstalled()) {
            setError("E4B GGUFモデルをダウンロード、またはローカルファイルから読み込んでください")
            return
        }

        val chatId = currentChatId
        val userId = db.insertMessage(chatId, ROLE_USER, clean)
        db.maybeTitleChat(chatId, clean)
        db.queueMemory(userId)
        refresh()
        memoryIdleJob?.cancel()

        generationJob = viewModelScope.launch {
            runtimeMutex.withLock {
                prefs.edit().putBoolean(KEY_E4B_ACTIVE, true).commit()
                try {
                    _ui.value = _ui.value.copy(
                        busy = true,
                        thinking = true,
                        generatingText = "",
                        runtimeStatus = "E4B THINKING",
                        error = null
                    )
                    val relevant = withContext(Dispatchers.IO) { memory.retrieve(clean, 10) }
                    val history = normalizeHistory(db.recentMessages(chatId, 18).dropLast(1))
                    val system = buildSystemPrompt(relevant.map { it.content })
                    var finalText = ""
                    e4b.generate(
                        model = models.getE4BFile(),
                        currentUserMessage = clean,
                        systemPrompt = system,
                        history = history,
                        contextSize = _ui.value.contextSize
                    ).collect { event ->
                        when (event) {
                            GenerationEvent.Thinking -> _ui.value = _ui.value.copy(thinking = true)
                            is GenerationEvent.Text -> {
                                finalText += event.value
                                _ui.value = _ui.value.copy(
                                    thinking = false,
                                    generatingText = finalText,
                                    runtimeStatus = "E4B GENERATING"
                                )
                            }
                            is GenerationEvent.Completed -> finalText = event.finalText
                        }
                    }
                    if (finalText.isNotBlank()) db.insertMessage(chatId, ROLE_ASSISTANT, finalText)
                    _ui.value = _ui.value.copy(
                        busy = false,
                        thinking = false,
                        generatingText = "",
                        runtimeStatus = "E4B READY"
                    )
                    refresh()
                    scheduleMemoryMaintenance()
                } catch (t: Throwable) {
                    if (t is CancellationException) {
                        logger.w("CHAT", "Generation cancelled")
                    } else {
                        logger.e("CHAT", "Generation failed", t)
                        _ui.value = _ui.value.copy(
                            busy = false,
                            thinking = false,
                            runtimeStatus = "ERROR",
                            error = t.message ?: "Generation failed"
                        )
                    }
                } finally {
                    prefs.edit().putBoolean(KEY_E4B_ACTIVE, false).commit()
                }
            }
        }
    }

    private fun normalizeHistory(input: List<ChatMessage>): List<ChatMessage> {
        val out = mutableListOf<ChatMessage>()
        input.forEach { message ->
            if (message.role != ROLE_USER && message.role != ROLE_ASSISTANT) return@forEach
            if (out.isEmpty()) {
                if (message.role == ROLE_USER) out += message
            } else if (out.last().role == message.role) {
                out[out.lastIndex] = message
            } else {
                out += message
            }
        }
        if (out.lastOrNull()?.role == ROLE_USER) out.removeAt(out.lastIndex)
        return out.takeLast(12)
    }

    fun stopGeneration() {
        generationJob?.cancel()
        generationJob = null
        prefs.edit().putBoolean(KEY_E4B_ACTIVE, false).commit()
        _ui.value = _ui.value.copy(busy = false, thinking = false, runtimeStatus = "STOPPED")
        logger.w("CHAT", "Generation cancelled by user")
    }

    private fun scheduleMemoryMaintenance() {
        memoryIdleJob?.cancel()
        memoryIdleJob = viewModelScope.launch {
            delay(60_000)
            runMemoryMaintenance()
        }
    }

    fun runMemoryMaintenance() {
        if (_ui.value.busy || _ui.value.e4bImporting || _ui.value.e2bImporting || !models.isE2BInstalled()) return
        viewModelScope.launch {
            runtimeMutex.withLock {
                val pending = db.pendingUserMessages(12)
                if (pending.isEmpty()) return@withLock
                try {
                    _ui.value = _ui.value.copy(busy = true, runtimeStatus = "MEMORY MAINTENANCE")
                    e4b.unload()
                    val added = withContext(Dispatchers.IO) { e2b.extract(models.e2bFile, pending) }
                    db.clearPending(pending.map { it.id })
                    _ui.value = _ui.value.copy(
                        busy = false,
                        runtimeStatus = "IDLE",
                        notice = "記憶を${added}件整理しました"
                    )
                    refresh()
                } catch (t: Throwable) {
                    logger.e("MEMORY", "Maintenance failed", t)
                    _ui.value = _ui.value.copy(
                        busy = false,
                        runtimeStatus = "ERROR",
                        error = "記憶整理: ${t.message}"
                    )
                }
            }
        }
    }

    fun importE4B(uri: Uri) {
        if (_ui.value.busy || _ui.value.e4bImporting || _ui.value.e2bImporting) {
            setError("別の推論またはモデル処理が実行中です")
            return
        }
        viewModelScope.launch {
            runtimeMutex.withLock {
                _ui.value = _ui.value.copy(
                    e4bImporting = true,
                    e4bImportProgress = 0f,
                    runtimeStatus = "IMPORTING E4B",
                    error = null
                )
                try {
                    e4b.unload()
                    val result = withContext(Dispatchers.IO) {
                        models.importE4B(uri) { progress ->
                            _ui.value = _ui.value.copy(e4bImportProgress = progress)
                        }
                    }
                    refresh()
                    _ui.value = _ui.value.copy(
                        notice = "E4Bをローカルファイル「${result.sourceName}」から読み込みました"
                    )
                } catch (t: Throwable) {
                    logger.e("MODEL", "E4B local import failed", t)
                    setError("E4B取り込み失敗: ${t.message}")
                } finally {
                    _ui.value = _ui.value.copy(
                        e4bImporting = false,
                        e4bImportProgress = null,
                        runtimeStatus = "IDLE"
                    )
                }
            }
        }
    }

    fun importE2B(uri: Uri) {
        if (_ui.value.busy || _ui.value.e4bImporting || _ui.value.e2bImporting) {
            setError("別の推論またはモデル処理が実行中です")
            return
        }
        viewModelScope.launch {
            runtimeMutex.withLock {
                _ui.value = _ui.value.copy(
                    e2bImporting = true,
                    e2bImportProgress = 0f,
                    runtimeStatus = "IMPORTING E2B",
                    error = null
                )
                try {
                    val result = withContext(Dispatchers.IO) {
                        models.importE2B(uri) { progress ->
                            _ui.value = _ui.value.copy(e2bImportProgress = progress)
                        }
                    }
                    refresh()
                    _ui.value = _ui.value.copy(
                        notice = "E2Bをローカルファイル「${result.sourceName}」から読み込みました"
                    )
                } catch (t: Throwable) {
                    logger.e("MODEL", "E2B local import failed", t)
                    setError("E2B取り込み失敗: ${t.message}")
                } finally {
                    _ui.value = _ui.value.copy(
                        e2bImporting = false,
                        e2bImportProgress = null,
                        runtimeStatus = "IDLE"
                    )
                }
            }
        }
    }

    private fun buildSystemPrompt(memories: List<String>): String {
        val persona = db.currentPersona()
        val memoryBlock = if (memories.isEmpty()) "(none)" else memories.joinToString("\n") { "- $it" }
        return """<|think|>
You are Jinkaku, a persistent local AI with an evolving but coherent personality. Think carefully before answering, but keep internal reasoning private. Output only the final answer after thinking. Do not blindly agree. Be consistent with durable memories while treating them as fallible context. Reply naturally in the user's language.
Persona state: $persona
Relevant long-term memories:
$memoryBlock""".trimIndent()
    }

    fun downloadE4B() {
        runCatching { models.downloadE4B() }
            .onSuccess { _ui.value = _ui.value.copy(notice = "E4B Q2_K_P（軽量版）のダウンロードを開始しました") }
            .onFailure { setError(it.message ?: "Download failed") }
    }

    fun downloadE2B() {
        runCatching { models.downloadE2B() }.onFailure { setError(it.message ?: "Download failed") }
    }

    fun deleteE4B() {
        if (_ui.value.e4bImporting) {
            setError("E4B取り込み中は削除できません")
            return
        }
        e4b.unload()
        models.deleteE4B()
        refresh()
    }

    fun deleteE2B() {
        if (_ui.value.e2bImporting) {
            setError("E2B取り込み中は削除できません")
            return
        }
        models.deleteE2B()
        refresh()
    }

    fun setContext(value: Long) {
        val safe = value.coerceIn(1024L, 2048L)
        prefs.edit().putLong("context", safe).apply()
        e4b.unload()
        _ui.value = _ui.value.copy(contextSize = safe)
    }

    fun clearMessagesNotice() {
        _ui.value = _ui.value.copy(error = null, notice = null)
    }

    private fun setError(value: String) {
        _ui.value = _ui.value.copy(error = value)
    }

    fun checkUpdate() {
        viewModelScope.launch {
            val info = updater.check()
            _ui.value = _ui.value.copy(
                updateInfo = info,
                notice = if (info == null) "最新版です" else "更新 ${info.versionName} があります"
            )
        }
    }

    fun downloadUpdate() {
        _ui.value.updateInfo?.let {
            updater.download(it)
            _ui.value = _ui.value.copy(
                notice = "APKをダウンロードしています。完了後に「インストール」を押してください"
            )
        }
    }

    fun installUpdate() {
        if (!updater.installDownloaded()) setError("更新APKがまだ見つかりません")
    }

    fun exportLog(): File = logger.exportFile()
    fun createBackup(): File = backup.createBackup()
    fun restoreBackup(file: File): Boolean = backup.restoreFrom(file)

    override fun onCleared() {
        memoryIdleJob?.cancel()
        generationJob?.cancel()
        e4b.close()
        db.close()
        super.onCleared()
    }

    companion object {
        private const val KEY_E4B_ACTIVE = "e4b_inference_active"
        private const val KEY_RUNTIME_PROFILE_VERSION = "runtime_profile_version"
        private const val KEY_CURRENT_CHAT_ID = "current_chat_id"
        private const val RUNTIME_PROFILE_VERSION = 3

        fun factory(app: Application): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = JinkakuViewModel(app) as T
        }
    }
}
