package com.ikegami99.jinkaku.ui

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ikegami99.jinkaku.JinkakuViewModel
import com.ikegami99.jinkaku.ai.InferenceTelemetry
import com.ikegami99.jinkaku.ai.InferenceTelemetryState
import com.ikegami99.jinkaku.data.MemoryRecord
import com.ikegami99.jinkaku.data.ROLE_USER
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private enum class MainScreen { CHAT, SETTINGS, MEMORY }

private fun typingLabel(generatedTokens: Int): String =
    "入力中" + ".".repeat((generatedTokens.mod(3)) + 1)

@Composable
fun JinkakuApp(vm: JinkakuViewModel) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val telemetry by InferenceTelemetry.state.collectAsStateWithLifecycle()
    var screen by remember { mutableStateOf(MainScreen.CHAT) }
    val snackbar = remember { SnackbarHostState() }
    val context = androidx.compose.ui.platform.LocalContext.current
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current

    fun dismissIme() {
        focusManager.clearFocus(force = true)
        keyboard?.hide()
    }

    val statusText = if (ui.runtimeStatus == "入力中") {
        typingLabel(telemetry.generatedTokens)
    } else ui.runtimeStatus

    LaunchedEffect(ui.error, ui.notice) {
        val text = ui.error ?: ui.notice
        if (text != null) {
            snackbar.showSnackbar(text)
            vm.clearMessagesNotice()
        }
    }

    MaterialTheme(colorScheme = lightColorScheme()) {
        ModalNavigationDrawer(
            drawerState = drawerState,
            drawerContent = {
                ModalDrawerSheet {
                    Column(Modifier.fillMaxHeight().widthIn(max = 340.dp).statusBarsPadding()) {
                        Text(
                            "Jinkaku",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(20.dp, 18.dp, 20.dp, 8.dp)
                        )
                        NavigationDrawerItem(
                            selected = screen == MainScreen.MEMORY,
                            onClick = {
                                dismissIme()
                                screen = MainScreen.MEMORY
                                vm.refresh()
                                scope.launch { drawerState.close() }
                            },
                            label = { Text("🧠 Memory  ${ui.memoryCount}件") },
                            modifier = Modifier.padding(horizontal = 10.dp)
                        )
                        HorizontalDivider(Modifier.padding(vertical = 8.dp))
                        Text(
                            "Chat履歴",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp)
                        )
                        LazyColumn(
                            Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(10.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            items(ui.chats, key = { it.id }) { chat ->
                                NavigationDrawerItem(
                                    selected = screen == MainScreen.CHAT && chat.id == ui.currentChatId,
                                    onClick = {
                                        dismissIme()
                                        screen = MainScreen.CHAT
                                        vm.selectChat(chat.id)
                                        scope.launch { drawerState.close() }
                                    },
                                    label = { Text(chat.title, maxLines = 2, overflow = TextOverflow.Ellipsis) }
                                )
                            }
                        }
                    }
                }
            }
        ) {
            Scaffold(
                snackbarHost = { SnackbarHost(snackbar) },
                topBar = {
                    Surface(shadowElevation = 1.dp) {
                        Row(
                            Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 10.dp, vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            TextButton(
                                onClick = {
                                    dismissIme()
                                    scope.launch { drawerState.open() }
                                },
                                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp)
                            ) { Text("☰", style = MaterialTheme.typography.titleLarge) }
                            Column(Modifier.weight(1f)) {
                                Text("Jinkaku", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                                Text("$statusText  •  Memory ${ui.memoryCount}", style = MaterialTheme.typography.labelMedium)
                            }
                            if (screen == MainScreen.CHAT) {
                                TextButton(onClick = {
                                    dismissIme()
                                    vm.newChat()
                                }) { Text("New chat") }
                                TextButton(onClick = {
                                    dismissIme()
                                    screen = MainScreen.SETTINGS
                                }) { Text("設定") }
                            } else {
                                TextButton(onClick = {
                                    dismissIme()
                                    screen = MainScreen.CHAT
                                }) { Text("チャット") }
                                if (screen != MainScreen.SETTINGS) {
                                    TextButton(onClick = {
                                        dismissIme()
                                        screen = MainScreen.SETTINGS
                                    }) { Text("設定") }
                                }
                            }
                        }
                    }
                }
            ) { padding ->
                when (screen) {
                    MainScreen.SETTINGS -> SettingsScreen(vm, Modifier.padding(padding)) { file, mime ->
                        val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
                        context.startActivity(
                            Intent.createChooser(
                                Intent(Intent.ACTION_SEND).apply {
                                    type = mime
                                    putExtra(Intent.EXTRA_STREAM, uri)
                                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                },
                                "共有"
                            )
                        )
                    }
                    MainScreen.MEMORY -> MemoryScreen(vm, Modifier.padding(padding))
                    MainScreen.CHAT -> ChatScreen(vm, Modifier.padding(padding))
                }
            }
        }
    }
}

@Composable
private fun ChatScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val telemetry by InferenceTelemetry.state.collectAsStateWithLifecycle()
    var input by remember { mutableStateOf("") }
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    val listState = rememberLazyListState()

    LaunchedEffect(ui.messages.size, ui.generatingText.length, ui.thinking, telemetry.generatedTokens) {
        val total = ui.messages.size + if (ui.busy && (ui.thinking || ui.generatingText.isNotBlank())) 1 else 0
        if (total > 0) listState.animateScrollToItem(total - 1)
    }

    fun submit() {
        val text = input.trim()
        if (text.isBlank()) return
        input = ""
        focusManager.clearFocus(force = true)
        keyboard?.hide()
        vm.send(text)
    }

    Column(modifier.fillMaxSize()) {
        ContextMeter(telemetry = telemetry, configuredContext = ui.contextSize.toInt())

        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(ui.messages, key = { it.id }) { m ->
                Column(Modifier.fillMaxWidth()) {
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = if (m.role == ROLE_USER) Arrangement.End else Arrangement.Start
                    ) {
                        Surface(
                            shape = RoundedCornerShape(18.dp),
                            tonalElevation = if (m.role == ROLE_USER) 3.dp else 1.dp,
                            modifier = Modifier.fillMaxWidth(0.88f)
                        ) {
                            Text(m.content, Modifier.padding(14.dp))
                        }
                    }
                    if (
                        m.role != ROLE_USER && telemetry.phase == "DONE" &&
                        telemetry.finalTextHash != null && telemetry.finalTextHash == m.content.hashCode()
                    ) {
                        InferenceStatsLine(telemetry, Modifier.padding(start = 8.dp, top = 4.dp))
                    }
                }
            }

            if (ui.busy && (ui.thinking || ui.generatingText.isNotBlank())) {
                item {
                    Surface(shape = RoundedCornerShape(18.dp), tonalElevation = 1.dp) {
                        Column(Modifier.padding(14.dp)) {
                            if (ui.thinking && ui.generatingText.isBlank()) {
                                Text(typingLabel(telemetry.generatedTokens), style = MaterialTheme.typography.labelMedium)
                            }
                            if (ui.generatingText.isNotBlank()) Text(ui.generatingText)
                        }
                    }
                }
            }
        }

        HorizontalDivider()
        Row(
            Modifier.fillMaxWidth().imePadding().navigationBarsPadding().padding(10.dp),
            verticalAlignment = Alignment.Bottom
        ) {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("メッセージ") },
                maxLines = 6
            )
            Spacer(Modifier.width(8.dp))
            if (ui.busy) {
                Button(onClick = {
                    focusManager.clearFocus(force = true)
                    keyboard?.hide()
                    vm.stopGeneration()
                }) { Text("停止") }
            } else {
                Button(
                    onClick = ::submit,
                    enabled = input.isNotBlank() &&
                        !ui.e4bImporting && !ui.e2bImporting &&
                        !ui.embeddingImporting && !ui.embeddingReindexing
                ) { Text("送信") }
            }
        }
    }
}

@Composable
private fun ContextMeter(telemetry: InferenceTelemetryState, configuredContext: Int) {
    val max = if (telemetry.contextMax > 0) telemetry.contextMax else configuredContext
    val used = if (telemetry.contextMax > 0) telemetry.contextUsed.coerceIn(0, max) else 0
    val remaining = (max - used).coerceAtLeast(0)
    val fraction = if (max > 0) used.toFloat() / max.toFloat() else 0f

    Surface(tonalElevation = 1.dp) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp)
        ) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text("Context $used / $max", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.weight(1f))
                Text("残り $remaining tok", style = MaterialTheme.typography.labelSmall)
            }
            LinearProgressIndicator(progress = { fraction.coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
        }
    }
}

@Composable
private fun InferenceStatsLine(telemetry: InferenceTelemetryState, modifier: Modifier = Modifier) {
    Text(
        "Prefill ${telemetry.prefillLabel()} tok/s  •  Decode ${telemetry.decodeLabel()} tok/s  •  ${telemetry.generatedTokens} tok  •  ${telemetry.backend}",
        modifier = modifier,
        style = MaterialTheme.typography.labelSmall
    )
}

@Composable
private fun MemoryScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    var confirmClear by remember { mutableStateOf(false) }
    var addingMemory by remember { mutableStateOf(false) }

    if (addingMemory) {
        ManualMemoryDialog(
            vm = vm,
            embeddingInstalled = ui.embeddingInstalled,
            onDismiss = { addingMemory = false }
        )
    }

    if (confirmClear) {
        AlertDialog(
            onDismissRequest = { confirmClear = false },
            title = { Text("Memoryを全削除") },
            text = { Text("長期Memoryと未処理のMemory候補をすべて削除します。チャット履歴とPersonaは残ります。") },
            confirmButton = {
                TextButton(onClick = {
                    confirmClear = false
                    vm.clearMemories()
                }) { Text("削除") }
            },
            dismissButton = { TextButton(onClick = { confirmClear = false }) { Text("キャンセル") } }
        )
    }

    Column(modifier.fillMaxSize()) {
        Surface(tonalElevation = 1.dp) {
            Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Long-term Memory", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                        Text("${ui.memoryCount}件 • ${ui.embeddingEngineName}", style = MaterialTheme.typography.bodySmall)
                    }
                    OutlinedButton(onClick = vm::refresh) { Text("更新") }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = { addingMemory = true },
                        enabled = !ui.busy && !ui.embeddingReindexing
                    ) { Text("＋ Memory追加") }
                    OutlinedButton(
                        onClick = { confirmClear = true },
                        enabled = ui.memoryCount > 0 && !ui.busy && !ui.embeddingReindexing
                    ) { Text("全削除") }
                }
                Text(
                    "手動MemoryではPersona、過去の出来事、好み、関係性、プロジェクトなどを直接登録できます。",
                    style = MaterialTheme.typography.bodySmall
                )
                if (ui.embeddingReindexing) {
                    LinearProgressIndicator(
                        progress = { (ui.embeddingReindexProgress ?: 0f).coerceIn(0f, 1f) },
                        modifier = Modifier.fillMaxWidth()
                    )
                    Text("Embeddingを再索引中… ${((ui.embeddingReindexProgress ?: 0f) * 100).toInt()}%", style = MaterialTheme.typography.labelSmall)
                }
            }
        }
        if (ui.memories.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("まだ長期Memoryはありません") }
        } else {
            LazyColumn(
                Modifier.fillMaxSize(),
                contentPadding = PaddingValues(12.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                items(ui.memories, key = { it.id }) { memory -> MemoryCard(memory) }
            }
        }
    }
}

@Composable
private fun MemoryCard(memory: MemoryRecord) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(memory.type, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.weight(1f))
                Text("#${memory.id}", style = MaterialTheme.typography.labelSmall)
            }
            Text(memory.content)
            Text(
                "importance ${memory.importance}/3  •  confidence ${memory.confidence}/2  •  ${memory.origin}",
                style = MaterialTheme.typography.labelSmall
            )
            Text(
                "index ${memory.embedding.size}d  •  access ${memory.accessCount}  •  ${formatMemoryDate(memory.createdAt)}",
                style = MaterialTheme.typography.labelSmall
            )
            if (memory.tags.isNotBlank()) Text("tags: ${memory.tags}", style = MaterialTheme.typography.labelSmall)
        }
    }
}

private fun formatMemoryDate(timestamp: Long): String =
    SimpleDateFormat("yyyy/MM/dd HH:mm", Locale.getDefault()).format(Date(timestamp))

@Composable
private fun SettingsScreen(
    vm: JinkakuViewModel,
    modifier: Modifier = Modifier,
    share: (java.io.File, String) -> Unit
) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val e4bPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> if (uri != null) vm.importE4B(uri) }
    val e2bPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> if (uri != null) vm.importE2B(uri) }
    val embeddingPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> if (uri != null) vm.importEmbedding(uri) }
    var personaDraft by remember { mutableStateOf(vm.currentPersona()) }

    LazyColumn(
        modifier.fillMaxSize(),
        contentPadding = PaddingValues(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item { Text("Persona", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("Jinkakuの基本人格", fontWeight = FontWeight.SemiBold)
                    OutlinedTextField(
                        value = personaDraft,
                        onValueChange = { personaDraft = it },
                        modifier = Modifier.fillMaxWidth().heightIn(min = 150.dp),
                        label = { Text("Persona") },
                        minLines = 5,
                        maxLines = 12
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = { vm.savePersona(personaDraft) },
                            enabled = personaDraft.isNotBlank() && !ui.busy
                        ) { Text("Personaを保存") }
                        OutlinedButton(onClick = { personaDraft = vm.currentPersona() }) { Text("再読込") }
                    }
                    Text("保存するたびにRevisionとして履歴へ残ります。Personaの一部を長期Memoryにも残したい場合は左上 → Memory → Memory追加からPERSONAを選択できます。", style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        item { Text("モデル", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold) }
        item {
            ModelCard(
                name = "Gemma 4 E4B HauhauCS (Q2_K_P / local GGUF)",
                installed = ui.e4bInstalled,
                downloadProgress = ui.e4bDownload?.progress,
                importing = ui.e4bImporting,
                importProgress = ui.e4bImportProgress,
                download = vm::downloadE4B,
                importLocal = { e4bPicker.launch(arrayOf("*/*")) },
                delete = vm::deleteE4B
            )
        }
        item {
            ModelCard(
                name = "Gemma 4 E2B LiteRT-LM",
                installed = ui.e2bInstalled,
                downloadProgress = ui.e2bDownload?.progress,
                importing = ui.e2bImporting,
                importProgress = ui.e2bImportProgress,
                download = vm::downloadE2B,
                importLocal = { e2bPicker.launch(arrayOf("*/*")) },
                delete = vm::deleteE2B
            )
        }
        item {
            ModelCard(
                name = "EmbeddingGemma 300M Q4_0 (GGUF / 約278MB)",
                installed = ui.embeddingInstalled,
                downloadProgress = ui.embeddingDownload?.progress,
                importing = ui.embeddingImporting,
                importProgress = ui.embeddingImportProgress,
                download = vm::downloadEmbedding,
                importLocal = { embeddingPicker.launch(arrayOf("*/*")) },
                delete = vm::deleteEmbedding
            )
        }
        item {
            Text(
                "EmbeddingGemmaはMemory検索専用です。未導入時はHashing-256へ自動フォールバックします。GGUFはアプリ専用領域へコピーしてから使用します。",
                style = MaterialTheme.typography.bodySmall
            )
        }
        item {
            Text("Context", fontWeight = FontWeight.Bold)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf(1024L, 2048L, 4096L, 8192L).forEach { size ->
                    FilterChip(
                        selected = ui.contextSize == size,
                        onClick = { vm.setContext(size) },
                        label = { Text("${size / 1024}K") }
                    )
                }
            }
            Text("1K/2K/4K/8Kから選択できます。8KはPOCO F7 UltraでもRAM・Prefill負荷が増えるため、失敗時は自動的に4K→2K→1Kへフォールバックします。", style = MaterialTheme.typography.bodySmall)
        }
        item {
            Text("推論表示", fontWeight = FontWeight.Bold)
            Text(
                "CoTは有効で本文は非表示です。思考中は実際の生成tokenが進むたびに「入力中. → 入力中.. → 入力中...」が変化します。tokenが止まれば点も止まります。Prefill/Decode速度・token数・Backendは回答完了後だけ表示します。",
                style = MaterialTheme.typography.bodySmall
            )
        }
        item {
            Text("長期メモリ", fontWeight = FontWeight.Bold)
            Text("Active: ${ui.memoryCount}件 • Index: ${ui.embeddingEngineName}")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = vm::runMemoryMaintenance,
                    enabled = ui.e2bInstalled && !ui.busy && !ui.embeddingReindexing
                ) { Text("今すぐ記憶を整理") }
                OutlinedButton(
                    onClick = vm::reindexMemories,
                    enabled = ui.embeddingInstalled && !ui.busy && !ui.embeddingImporting
                ) { Text("Memory再索引") }
            }
            if (ui.embeddingReindexing) {
                LinearProgressIndicator(
                    progress = { (ui.embeddingReindexProgress ?: 0f).coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth().padding(top = 8.dp)
                )
            }
            Text("Memoryの閲覧・手動追加・全削除は左上メニュー → Memoryから操作できます。", style = MaterialTheme.typography.bodySmall)
        }
        item {
            Text("メンテナンス", fontWeight = FontWeight.Bold)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { share(vm.exportLog(), "text/plain") }) { Text("ログを書き出す") }
                OutlinedButton(onClick = { share(vm.createBackup(), "application/zip") }) { Text("バックアップ") }
            }
            Text("ログは常時ファイルへ追記し、共有前にflush/syncします。空ログは生成しません。", style = MaterialTheme.typography.bodySmall)
        }
        item {
            Text("アプリ更新", fontWeight = FontWeight.Bold)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = vm::checkUpdate) { Text("更新確認") }
                if (ui.updateInfo != null) Button(onClick = vm::downloadUpdate) { Text("APK取得") }
                OutlinedButton(onClick = vm::installUpdate) { Text("インストール") }
            }
        }
        item { Spacer(Modifier.height(32.dp)) }
    }
}

@Composable
private fun ModelCard(
    name: String,
    installed: Boolean,
    downloadProgress: Float?,
    importing: Boolean,
    importProgress: Float?,
    download: () -> Unit,
    importLocal: () -> Unit,
    delete: () -> Unit
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(name, fontWeight = FontWeight.SemiBold)
            Text(when {
                importing -> "ローカルファイルを取り込み中"
                installed -> "インストール済み"
                else -> "未インストール"
            })
            if (importing) {
                if (importProgress != null && importProgress > 0f) {
                    LinearProgressIndicator(progress = { importProgress.coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
                    Text("${(importProgress * 100).toInt()}%", style = MaterialTheme.typography.labelSmall)
                } else {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
            } else if (!installed && downloadProgress != null && downloadProgress > 0f && downloadProgress < 1f) {
                LinearProgressIndicator(progress = { downloadProgress }, modifier = Modifier.fillMaxWidth())
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!installed) Button(onClick = download, enabled = !importing) { Text("ダウンロード") }
                OutlinedButton(onClick = importLocal, enabled = !importing) { Text("ローカルから読込") }
                if (installed) OutlinedButton(onClick = delete, enabled = !importing) { Text("削除") }
            }
        }
    }
}
