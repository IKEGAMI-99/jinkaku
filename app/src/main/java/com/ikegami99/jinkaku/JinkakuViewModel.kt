package com.ikegami99.jinkaku

import android.app.Application
import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.ikegami99.jinkaku.ai.E2BMemoryEngine
import com.ikegami99.jinkaku.ai.E4BEngine
import com.ikegami99.jinkaku.ai.GenerationEvent
import com.ikegami99.jinkaku.ai.MemoryEngine
import com.ikegami99.jinkaku.backup.BackupManager
import com.ikegami99.jinkaku.data.JinkakuDatabase
import com.ikegami99.jinkaku.data.MessageRow
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


data class UiState(
    val messages: List<MessageRow> = emptyList(),
    val memories: Int = 0,
    val runtimeStatus: String = "IDLE",
    val busy: Boolean = false,
    val thinking: Boolean = false,
    val generatingText: String = "",
    val e4bInstalled: Boolean = false,
    val e2bInstalled: Boolean = false,
    val e4bDownload: DownloadStatus? = null,
    val e2bDownload: DownloadStatus? = null,
    val e4bImporting: Boolean = false,
    val e2bImporting: Boolean = false,
    val e4bImportProgress: Float? = null,
    val e2bImportProgress: Float? = null,
    val contextSize: Long = 4096,
    val error: String? = null,
    val notice: String? = null,
    val updateInfo: UpdateInfo? = null
)

class JinkakuViewModel(app: Application) : AndroidViewModel(app) {
    private val logger: AppLogger = (app as JinkakuApplication).logger
    private val db = JinkakuDatabase(app, logger)
    private val memory = MemoryEngine(db)
    private val models = ModelManager(app, logger)
    private val e4b = E4BEngine(app, viewModelScope, logger)
    private val e2b = E2BMemoryEngine(app, db, logger)
    private val updater = AppUpdater(app, logger)
    private val backup = BackupManager(app, db, logger)
    private val runtimeMutex = Mutex()
    private var generationJob: Job? = null
    private var memoryIdleJob: Job? = null
    private val prefs = app.getSharedPreferences("settings", Context.MODE_PRIVATE)
    private val previousInferenceInterrupted = prefs.getBoolean(KEY_E4B_ACTIVE, false)
    private val initialContext: Long = migrateRuntimeProfile()
    private val _ui = MutableStateFlow(UiState(contextSize = initialContext))
    val ui: StateFlow<UiState> = _ui.asStateFlow()

    init {
        if (previousInferenceInterrupted) {
            logger.w("E4B", "Previous process ended while E4B inference was active; safe mode enabled")
            _ui.value = _ui.value.copy(
                notice = "前回E4B推論中にアプリが終了しました。安全のためContextを2Kへ下げました。"
            )
        }
        refresh()
        viewModelScope.launch {
            while (true) {
                delay(1500)
                refreshDownloadState()
            }
        }
    }

    private fun migrateRuntimeProfile(): Long {
        var context = prefs.getLong("context", 4096L)
        val profile = prefs.getInt(KEY_RUNTIME_PROFILE_VERSION, 0)
        if (profile < RUNTIME_PROFILE_VERSION) {
            context = 4096L
            prefs.edit()
                .putLong("context", context)
                .putInt(KEY_RUNTIME_PROFILE_VERSION, RUNTIME_PROFILE_VERSION)
                .apply()
            logger.i("E4B", "Runtime profile migrated to conservative defaults ctx=$context")
        }
        if (previousInferenceInterrupted) {
            context = 2048L
            prefs.edit()
                .putLong("context", context)
                .putBoolean(KEY_E4B_ACTIVE, false)
                .commit()
        }
        return context
    }

    fun refresh() {
        _ui.value = _ui.value.copy(
            messages = db.recentMessages(100),
            memories = db.memoryCount(),
            e4bInstalled = models.isE4BInstalled(),
            e2bInstalled = models.isE2BInstalled()
        )
        refreshDownloadState()
    }

    private fun refreshDownloadState() {
        _ui.value = _ui.value.copy(
            e4bDownload = models.status("e4b"),
            e2bDownload = models.status("e2b")
        )
    }

    fun setContext(value: Long) {
        prefs.edit().putLong("context", value).apply()
        _ui.value = _ui.value.copy(contextSize = value)
        e4b.unload()
    }

    fun clearMessage() {
        _ui.value = _ui.value.copy(error = null, notice = null)
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
                    val history = db.recentMessages(18).dropLast(1)
                    val system = buildSystemPrompt(relevant.map { it.content })
                    val prompt = buildPrompt(history, clean)
                    var finalText = ""
                    e4b.generate(models.getE4BFile(), prompt, system, _ui.value.contextSize).collect { event ->
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
                    if (finalText.isNotBlank()) db.insertMessage(ROLE_ASSISTANT, finalText)
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
            delay(180_000)
            runMemoryMaintenance()
        }
    }

    fun runMemoryMaintenance() {
        if (_ui.value.busy || !models.isE2BInstalled()) return
        viewModelScope.launch {
            runtimeMutex.withLock {
                try {
                    _ui.value = _ui.value.copy(busy = true, runtimeStatus = "MEMORY MAINTENANCE", error = null)
                    val pending = db.pendingMessages(24)
                    if (pending.isEmpty()) {
                        _ui.value = _ui.value.copy(busy = false, runtimeStatus = "IDLE", notice = "整理する記憶はありません")
                        return@withLock
                    }
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
        if (_ui.value.busy) {
            setError("推論中はモデルを変更できません")
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
                        models.importE4B(uri) { p -> _ui.value = _ui.value.copy(e4bImportProgress = p) }
                    }
                    refresh()
                    _ui.value = _ui.value.copy(
                        notice = "E4Bをローカルファイル「${result.sourceName}」から読み込みました"
                    )
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
        if (_ui.value.busy) {
            setError("推論中はモデルを変更できません")
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
                    e4b.unload()
                    e2b.close()
                    val result = withContext(Dispatchers.IO) {
                        models.importE2B(uri) { p -> _ui.value = _ui.value.copy(e2bImportProgress = p) }
                    }
                    refresh()
                    _ui.value = _ui.value.copy(
                        notice = "E2Bをローカルファイル「${result.sourceName}」から読み込みました"
                    )
                } catch (t: Throwable) {
                    logger.e("MODEL", "E2B local import failed", t)
                    setError("E2B取り込み失敗: ${t.message}")
                } finally {
                    _ui.value = _ui.value.copy(e2bImporting = false, e2bImportProgress = null, runtimeStatus = "IDLE")
                }
            }
        }
    }

    fun downloadE4B() {
        e4b.unload()
        val id = models.downloadE4B()
        _ui.value = _ui.value.copy(notice = "E4B Q2_K_P（軽量版）のダウンロードを開始しました: $id")
    }

    fun downloadE2B() {
        val id = models.downloadE2B()
        _ui.value = _ui.value.copy(notice = "E2Bのダウンロードを開始しました: $id")
    }

    fun deleteE4B() {
        if (_ui.value.busy) return
        e4b.unload()
        models.deleteE4B()
        refresh()
    }

    fun deleteE2B() {
        if (_ui.value.busy) return
        e2b.close()
        models.deleteE2B()
        refresh()
    }

    fun checkUpdate() {
        viewModelScope.launch {
            runCatching { updater.check() }
                .onSuccess { info -> _ui.value = _ui.value.copy(updateInfo = info, notice = if (info != null) "更新があります: ${info.versionName}" else "最新版です") }
                .onFailure { setError("更新確認失敗: ${it.message}") }
        }
    }

    fun downloadUpdate(info: UpdateInfo) {
        runCatching { updater.download(info) }
            .onSuccess { _ui.value = _ui.value.copy(notice = "更新APKのダウンロードを開始しました") }
            .onFailure { setError("更新ダウンロード失敗: ${it.message}") }
    }

    fun exportLog(): Uri = logger.export()
    fun createBackup(): Uri = backup.create()

    private fun setError(text: String) {
        _ui.value = _ui.value.copy(error = text, busy = false, thinking = false)
    }

    private fun buildSystemPrompt(memories: List<String>): String = buildString {
        appendLine("あなたはSolというローカル人格AIです。落ち着いて知的に話し、盲目的に同意せず、自分の判断を持ってください。")
        appendLine("内部のthought/reasoningはユーザーに表示せず、最終回答だけを自然な日本語で返してください。")
        if (memories.isNotEmpty()) {
            appendLine("関連する長期記憶:")
            memories.forEach { appendLine("- $it") }
        }
    }

    private fun buildPrompt(history: List<MessageRow>, current: String): String = buildString {
        history.takeLast(12).forEach { row ->
            append(if (row.role == ROLE_USER) "User: " else "Assistant: ")
            appendLine(row.content)
        }
        append("User: ")
        append(current)
    }

    override fun onCleared() {
        generationJob?.cancel()
        memoryIdleJob?.cancel()
        e4b.close()
        e2b.close()
        db.close()
        super.onCleared()
    }

    companion object {
        private const val KEY_E4B_ACTIVE = "e4b_inference_active"
        private const val KEY_RUNTIME_PROFILE_VERSION = "runtime_profile_version"
        private const val RUNTIME_PROFILE_VERSION = 1
    }
}
