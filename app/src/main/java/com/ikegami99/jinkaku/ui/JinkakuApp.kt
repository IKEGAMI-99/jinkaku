package com.ikegami99.jinkaku.ui

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ikegami99.jinkaku.JinkakuViewModel
import com.ikegami99.jinkaku.data.ROLE_USER
import kotlinx.coroutines.launch

@Composable
fun JinkakuApp(vm: JinkakuViewModel) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    var settings by remember { mutableStateOf(false) }
    val snackbar = remember { SnackbarHostState() }
    val context = androidx.compose.ui.platform.LocalContext.current
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()

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
                            "Chat履歴",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(20.dp, 18.dp, 20.dp, 12.dp)
                        )
                        HorizontalDivider()
                        LazyColumn(
                            Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(10.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            items(ui.chats, key = { it.id }) { chat ->
                                NavigationDrawerItem(
                                    selected = chat.id == ui.currentChatId,
                                    onClick = {
                                        settings = false
                                        vm.selectChat(chat.id)
                                        scope.launch { drawerState.close() }
                                    },
                                    label = {
                                        Text(
                                            chat.title,
                                            maxLines = 2,
                                            overflow = TextOverflow.Ellipsis
                                        )
                                    }
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
                                onClick = { scope.launch { drawerState.open() } },
                                contentPadding = PaddingValues(horizontal = 8.dp, vertical = 4.dp)
                            ) {
                                Text("☰", style = MaterialTheme.typography.titleLarge)
                            }
                            Column(Modifier.weight(1f)) {
                                Text("Jinkaku", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                                Text("${ui.runtimeStatus}  •  Memory ${ui.memoryCount}", style = MaterialTheme.typography.labelMedium)
                            }
                            TextButton(onClick = {
                                settings = false
                                vm.newChat()
                            }) { Text("New chat") }
                            TextButton(onClick = { settings = !settings }) {
                                Text(if (settings) "チャット" else "設定")
                            }
                        }
                    }
                }
            ) { padding ->
                if (settings) {
                    SettingsScreen(vm, Modifier.padding(padding)) { file, mime ->
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
                } else {
                    ChatScreen(vm, Modifier.padding(padding))
                }
            }
        }
    }
}

@Composable
private fun ChatScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    var input by remember { mutableStateOf("") }
    Column(modifier.fillMaxSize().imePadding()) {
        LazyColumn(
            Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            items(ui.messages, key = { it.id }) { m ->
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
            }
            if (ui.busy && (ui.thinking || ui.generatingText.isNotBlank())) {
                item {
                    Surface(shape = RoundedCornerShape(18.dp), tonalElevation = 1.dp) {
                        Column(Modifier.padding(14.dp)) {
                            if (ui.thinking && ui.generatingText.isBlank()) {
                                Text("Thinking…", style = MaterialTheme.typography.labelMedium)
                            }
                            if (ui.generatingText.isNotBlank()) Text(ui.generatingText)
                        }
                    }
                }
            }
        }
        HorizontalDivider()
        Row(Modifier.fillMaxWidth().padding(10.dp), verticalAlignment = Alignment.Bottom) {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("メッセージ") },
                maxLines = 6
            )
            Spacer(Modifier.width(8.dp))
            if (ui.busy) {
                Button(onClick = vm::stopGeneration) { Text("停止") }
            } else {
                Button(
                    onClick = {
                        val t = input
                        input = ""
                        vm.send(t)
                    },
                    enabled = input.isNotBlank() && !ui.e4bImporting && !ui.e2bImporting
                ) { Text("送信") }
            }
        }
    }
}

@Composable
private fun SettingsScreen(
    vm: JinkakuViewModel,
    modifier: Modifier = Modifier,
    share: (java.io.File, String) -> Unit
) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val e4bPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) vm.importE4B(uri)
    }
    val e2bPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) vm.importE2B(uri)
    }

    LazyColumn(
        modifier.fillMaxSize(),
        contentPadding = PaddingValues(18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
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
            Text(
                "ローカルファイルはAndroidのファイル選択画面から選べます。選択したモデルはアプリ専用領域へ安全にコピーしてから使用します。E4BはGGUFヘッダを検証します。取り込み中は元ファイルとコピーの両方が存在するため、モデル容量ぶんの追加空き容量が必要です。",
                style = MaterialTheme.typography.bodySmall
            )
        }
        item {
            Text("Context", fontWeight = FontWeight.Bold)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                listOf(1024L, 2048L).forEach { size ->
                    FilterChip(
                        selected = ui.contextSize == size,
                        onClick = { vm.setContext(size) },
                        label = { Text("${size / 1024}K") }
                    )
                }
            }
            Text("現在はCPU安定性優先で1K/2Kに制限しています。", style = MaterialTheme.typography.bodySmall)
        }
        item {
            Text("長期メモリ", fontWeight = FontWeight.Bold)
            Text("Active: ${ui.memoryCount}件。E2Bは会話中には常駐せず、アイドル時に整理します。")
            Button(
                onClick = vm::runMemoryMaintenance,
                enabled = ui.e2bInstalled && !ui.busy && !ui.e4bImporting && !ui.e2bImporting
            ) {
                Text("今すぐ記憶を整理")
            }
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
        item {
            Text("Embedding", fontWeight = FontWeight.Bold)
            Text(
                "MVPでは256次元の完全ローカルHashing Embedding + 固有名詞検索を使用。EmbeddingGemma 300MはHugging Faceの利用同意が必要なため、次段階で差し替え可能な構造にしています。",
                style = MaterialTheme.typography.bodySmall
            )
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
            Text(
                when {
                    importing -> "ローカルファイルを取り込み中"
                    installed -> "インストール済み"
                    else -> "未インストール"
                }
            )
            if (importing) {
                if (importProgress != null && importProgress > 0f) {
                    LinearProgressIndicator(
                        progress = { importProgress.coerceIn(0f, 1f) },
                        modifier = Modifier.fillMaxWidth()
                    )
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
