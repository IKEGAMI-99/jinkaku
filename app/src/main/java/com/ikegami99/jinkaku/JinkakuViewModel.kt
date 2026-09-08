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
import com.ikegami99.jinkaku.data.JinkakuDatabase
import com.ikegami99.jinkaku.data.ROLE_ASSISTANT
import com.ikegami99.jinkaku.data.ROLE_USER
import com.ikegami99.jinkaku.logging.AppLogger
import com.ikegami99.jinkaku.model.DownloadStatus
import com.ikegami99.jinkaku.model.ModelManager
import com.ikegami99.jinkaku.update.AppUpdater
import com.ikegami99.jinkaku.update.UpdateInfo
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
    val contextSize: Long = 8192,
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
    private val _ui = MutableStateFlow(UiState(contextSize = prefs.getLong("context", 8192)))
    val ui: StateFlow<UiState> = _ui.asStateFlow()

    init {
        refresh()
        viewModelScope.launch {
            while (true) {
                delay(1000)
                refreshDownloads()
            }
        }
    }

    fun refresh() {
        _ui.value = _ui.value.copy(
            messages = db.recentMessages(100),
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
        val userId = db.insertMessage(ROLE_USER, clean)
        db.queueMemory(userId)
        refresh()
        memoryIdleJob?.cancel()
        generationJob = viewModelScope.launch {
            runtimeMutex.withLock {
                try {
                    _ui.value = _ui.value.copy(busy = true, thinking = true, generatingText = "", runtimeStatus = "E4B THINKING", error = null)
                    val relevant = withContext(Dispatchers.IO) { memory.retrieve(clean, 10) }
                    val history = db.recentMessages(18).dropLast(1)
                    val system = buildSystemPrompt(relevant.map { it.content })
                    val prompt = buildPrompt(history, clean)
                    var finalText = ""
                    e4b.generate(models.e4bFile, prompt, system, _ui.value.contextSize).collect { event ->
                        when (event) {
                            GenerationEvent.Thinking -> _ui.value = _ui.value.copy(thinking = true)
                            is GenerationEvent.Text -> {
                                finalText += event.value
                                _ui.value = _ui.value.copy(thinking = false, generatingText = finalText, runtimeStatus = "E4B GENERATING")
                            }
                            is GenerationEvent.Completed -> finalText = event.finalText
                        }
                    }
                    if (finalText.isNotBlank()) db.insertMessage(ROLE_ASSISTANT, finalText)
                    _ui.value = _ui.value.copy(busy = false, thinking = false, generatingText = "", runtimeStatus = "E4B READY")
                    refresh()
                    scheduleMemoryMaintenance()
                } catch (t: Throwable) {
                    logger.e("CHAT", "Generation failed", t)
                    _ui.value = _ui.value.copy(busy = false, thinking = false, runtimeStatus = "ERROR", error = t.message ?: "Generation failed")
                }
            }
        }
    }

    fun stopGeneration() {
        generationJob?.cancel()
        generationJob = null
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
                    _ui.value = _ui.value.copy(busy = false, runtimeStatus = "IDLE", notice = "記憶を${added}件整理しました")
                    refresh()
                } catch (t: Throwable) {
                    logger.e("MEMORY", "Maintenance failed", t)
                    _ui.value = _ui.value.copy(busy = false, runtimeStatus = "ERROR", error = "記憶整理: ${t.message}")
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
                _ui.value = _ui.value.copy(e4bImporting = true, e4bImportProgress = 0f, runtimeStatus = "IMPORTING E4B", error = null)
                try {
                    e4b.unload()
                    val result = withContext(Dispatchers.IO) {
                        models.importE4B(uri) { progress ->
                            _ui.value = _ui.value.copy(e4bImportProgress = progress)
                        }
                    }
                    refresh()
                    _ui.value = _ui.value.copy(notice = "E4Bをローカルファイル「${result.sourceName}」から読み込みました")
                } catch (t: Throwable) {
                    logger.e("MODEL", "E4B local import failed", t)
                    setError("E4B取り込み失敗: ${t.message}")
                } finally {
                    _ui.value = _ui.value.copy(e4bImporting = false, e4bImportProgress = null, runtimeStatus = "IDLE")
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
                _ui.value = _ui.value.copy(e2bImporting = true, e2bImportProgress = 0f, runtimeStatus = "IMPORTING E2B", error = null)
                try {
                    val result = withContext(Dispatchers.IO) {
                        models.importE2B(uri) { progress ->
                            _ui.value = _ui.value.copy(e2bImportProgress = progress)
                        }
                    }
                    refresh()
                    _ui.value = _ui.value.copy(notice = "E2Bをローカルファイル「${result.sourceName}」から読み込みました")
                } catch (t: Throwable) {
                    logger.e("MODEL", "E2B local import failed", t)
                    setError("E2B取り込み失敗: ${t.message}")
                } finally {
                    _ui.value = _ui.value.copy(e2bImporting = false, e2bImportProgress = null, runtimeStatus = "IDLE")
                }
            }
        }
    }

    private fun buildSystemPrompt(memories: List<String>): String {
        val persona = db.currentPersona()
        val memoryBlock = if (memories.isEmpty()) "(none)" else memories.joinToString("\n") { "- $it" }
        return """You are Jinkaku, a persistent local AI with an evolving but coherent personality. Think carefully before answering. Your hidden reasoning must never be quoted or exposed; output only the final answer to the user. Do not blindly agree. Be consistent with durable memories, while treating them as fallible context. Persona state: $persona
Relevant long-term memories:
$memoryBlock
Current response should be natural and directly answer the user's latest message.""".trimIndent()
    }

    private fun buildPrompt(history: List<ChatMessage>, current: String): String {
        val transcript = history.joinToString("\n") { if (it.role == ROLE_USER) "User: ${it.content}" else "Assistant: ${it.content}" }
        return if (transcript.isBlank()) current else "Recent conversation:\n$transcript\n\nLatest user message:\n$current"
    }

    fun downloadE4B() { runCatching { models.downloadE4B() }.onFailure { setError(it.message ?: "Download failed") } }
    fun downloadE2B() { runCatching { models.downloadE2B() }.onFailure { setError(it.message ?: "Download failed") } }
    fun deleteE4B() {
        if (_ui.value.e4bImporting) { setError("E4B取り込み中は削除できません"); return }
        e4b.unload(); models.deleteE4B(); refresh()
    }
    fun deleteE2B() {
        if (_ui.value.e2bImporting) { setError("E2B取り込み中は削除できません"); return }
        models.deleteE2B(); refresh()
    }

    fun setContext(value: Long) { prefs.edit().putLong("context", value).apply(); _ui.value = _ui.value.copy(contextSize = value) }
    fun clearMessagesNotice() { _ui.value = _ui.value.copy(error = null, notice = null) }
    private fun setError(value: String) { _ui.value = _ui.value.copy(error = value) }
    fun checkUpdate() { viewModelScope.launch { val info = updater.check(); _ui.value = _ui.value.copy(updateInfo = info, notice = if (info == null) "最新版です" else "更新 ${info.versionName} があります") } }
    fun downloadUpdate() { _ui.value.updateInfo?.let { updater.download(it); _ui.value = _ui.value.copy(notice = "APKをダウンロードしています。完了後に「インストール」を押してください") } }
    fun installUpdate() { if (!updater.installDownloaded()) setError("更新APKがまだ見つかりません") }
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
        fun factory(app: Application): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = JinkakuViewModel(app) as T
        }
    }
}
