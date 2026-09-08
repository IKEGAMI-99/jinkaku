package com.ikegami99.jinkaku.ui

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
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
    val themePrefs = remember(context) { context.getSharedPreferences("settings", android.content.Context.MODE_PRIVATE) }
    var darkMode by remember { mutableStateOf(themePrefs.getBoolean("dark_mode", true)) }
    val drawerState = rememberDrawerState(DrawerValue.Closed)
    val scope = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current

    fun dismissIme() {
        focusManager.clearFocus(force = true)
        keyboard?.hide()
    }

    fun setDarkMode(enabled: Boolean) {
        darkMode = enabled
        themePrefs.edit().putBoolean("dark_mode", enabled).apply()
    }

    val statusText = if (ui.busy && (ui.runtimeStatus == "入力中" || ui.runtimeStatus == "生成中")) {
        typingLabel(telemetry.generatedTokens)
    } else ui.runtimeStatus

    LaunchedEffect(ui.error, ui.notice) {
        val text = ui.error ?: ui.notice
        if (text != null) {
            snackbar.showSnackbar(text)
            vm.clearMessagesNotice()
        }
    }

    JinkakuTheme(darkMode = darkMode) {
        ModalNavigationDrawer(
            drawerState = drawerState,
            drawerContent = {
                ModalDrawerSheet(
                    drawerContainerColor = MaterialTheme.colorScheme.background,
                    modifier = Modifier.widthIn(max = 340.dp)
                ) {
                    Column(Modifier.fillMaxHeight().statusBarsPadding()) {
                        Row(
                            Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 18.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Surface(
                                shape = CircleShape,
                                color = MaterialTheme.colorScheme.primaryContainer,
                                modifier = Modifier.size(42.dp)
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Icon(Icons.Rounded.Forum, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                                }
                            }
                            Spacer(Modifier.width(12.dp))
                            Column {
                                Text("Jinkaku", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                                Text("Local persona AI", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }

                        NavigationDrawerItem(
                            selected = screen == MainScreen.MEMORY,
                            onClick = {
                                dismissIme()
                                screen = MainScreen.MEMORY
                                vm.refresh()
                                scope.launch { drawerState.close() }
                            },
                            icon = { Icon(Icons.Rounded.Memory, contentDescription = null) },
                            label = { Text("Memory") },
                            badge = { Text(ui.memoryCount.toString()) },
                            modifier = Modifier.padding(horizontal = 12.dp)
                        )

                        HorizontalDivider(Modifier.padding(horizontal = 16.dp, vertical = 12.dp))
                        Text(
                            "チャット履歴",
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(horizontal = 20.dp, vertical = 4.dp)
                        )

                        LazyColumn(
                            Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 8.dp),
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
                                    icon = { Icon(Icons.Rounded.ChatBubbleOutline, contentDescription = null) },
                                    label = { Text(chat.title, maxLines = 2, overflow = TextOverflow.Ellipsis) }
                                )
                            }
                        }
                    }
                }
            }
        ) {
            Scaffold(
                containerColor = MaterialTheme.colorScheme.background,
                snackbarHost = { SnackbarHost(snackbar) },
                topBar = {
                    ModernTopBar(
                        screen = screen,
                        statusText = statusText,
                        memoryCount = ui.memoryCount,
                        onMenu = {
                            dismissIme()
                            scope.launch { drawerState.open() }
                        },
                        onNewChat = {
                            dismissIme()
                            vm.newChat()
                        },
                        onSettings = {
                            dismissIme()
                            screen = MainScreen.SETTINGS
                        },
                        onChat = {
                            dismissIme()
                            screen = MainScreen.CHAT
                        }
                    )
                }
            ) { padding ->
                when (screen) {
                    MainScreen.CHAT -> ChatScreen(vm, Modifier.padding(padding))
                    MainScreen.MEMORY -> MemoryScreen(vm, Modifier.padding(padding))
                    MainScreen.SETTINGS -> SettingsScreen(
                        vm = vm,
                        modifier = Modifier.padding(padding),
                        darkMode = darkMode,
                        onDarkModeChange = ::setDarkMode,
                        share = { file, mime ->
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
                    )
                }
            }
        }
    }
}

@Composable
private fun ModernTopBar(
    screen: MainScreen,
    statusText: String,
    memoryCount: Int,
    onMenu: () -> Unit,
    onNewChat: () -> Unit,
    onSettings: () -> Unit,
    onChat: () -> Unit
) {
    Surface(color = MaterialTheme.colorScheme.background) {
        Row(
            Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 8.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onMenu) {
                Icon(Icons.Rounded.Menu, contentDescription = "メニュー")
            }
            Column(Modifier.weight(1f)) {
                Text("Jinkaku", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    StatusDot(statusText)
                    Text(statusText, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("·", color = MaterialTheme.colorScheme.outline)
                    Text("Memory $memoryCount", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            if (screen == MainScreen.CHAT) {
                IconButton(onClick = onNewChat) {
                    Icon(Icons.Rounded.AddComment, contentDescription = "New chat")
                }
                IconButton(onClick = onSettings) {
                    Icon(Icons.Rounded.Settings, contentDescription = "設定")
                }
            } else {
                IconButton(onClick = onChat) {
                    Icon(Icons.Rounded.Chat, contentDescription = "チャット")
                }
                if (screen != MainScreen.SETTINGS) {
                    IconButton(onClick = onSettings) {
                        Icon(Icons.Rounded.Settings, contentDescription = "設定")
                    }
                }
            }
        }
    }
}

@Composable
private fun StatusDot(status: String) {
    val color = when {
        status.contains("ERROR", ignoreCase = true) -> MaterialTheme.colorScheme.error
        status.contains("入力中") || status.contains("生成") -> MaterialTheme.colorScheme.tertiary
        status.contains("READY") -> MaterialTheme.colorScheme.tertiary
        else -> MaterialTheme.colorScheme.outline
    }
    Surface(shape = CircleShape, color = color, modifier = Modifier.size(7.dp)) {}
}

@Composable
private fun ChatScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val telemetry by InferenceTelemetry.state.collectAsStateWithLifecycle()
    var input by remember { mutableStateOf("") }
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    val listState = rememberLazyListState()

    LaunchedEffect(ui.messages.size, ui.busy, telemetry.generatedTokens) {
        val total = ui.messages.size + if (ui.busy) 1 else 0
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
            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            items(ui.messages, key = { it.id }) { message ->
                ChatMessageItem(
                    isUser = message.role == ROLE_USER,
                    text = message.content,
                    telemetry = telemetry
                )
            }

            if (ui.busy) {
                item {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
                        Surface(
                            shape = RoundedCornerShape(20.dp),
                            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.62f)
                        ) {
                            Row(
                                Modifier.padding(horizontal = 16.dp, vertical = 12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(10.dp)
                            ) {
                                CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
                                Text(typingLabel(telemetry.generatedTokens), style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                }
            }
        }

        ChatComposer(
            input = input,
            onInputChange = { input = it },
            busy = ui.busy,
            enabled = !ui.e4bImporting && !ui.e2bImporting && !ui.embeddingImporting && !ui.embeddingReindexing,
            onSend = ::submit,
            onStop = {
                focusManager.clearFocus(force = true)
                keyboard?.hide()
                vm.stopGeneration()
            }
        )
    }
}

@Composable
private fun ChatMessageItem(isUser: Boolean, text: String, telemetry: InferenceTelemetryState) {
    Column(Modifier.fillMaxWidth()) {
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
        ) {
            Surface(
                shape = if (isUser) RoundedCornerShape(22.dp, 22.dp, 6.dp, 22.dp) else RoundedCornerShape(22.dp, 22.dp, 22.dp, 6.dp),
                color = if (isUser) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f),
                modifier = Modifier.widthIn(max = 560.dp).fillMaxWidth(0.9f)
            ) {
                Text(
                    text,
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 13.dp),
                    style = MaterialTheme.typography.bodyLarge
                )
            }
        }

        if (!isUser && telemetry.phase == "DONE" && telemetry.finalTextHash == text.hashCode()) {
            InferenceStatsLine(telemetry, Modifier.padding(start = 8.dp, top = 5.dp))
        }
    }
}

@Composable
private fun ChatComposer(
    input: String,
    onInputChange: (String) -> Unit,
    busy: Boolean,
    enabled: Boolean,
    onSend: () -> Unit,
    onStop: () -> Unit
) {
    Surface(
        color = MaterialTheme.colorScheme.background,
        tonalElevation = 0.dp
    ) {
        Row(
            Modifier.fillMaxWidth().imePadding().navigationBarsPadding().padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.Bottom,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            TextField(
                value = input,
                onValueChange = onInputChange,
                modifier = Modifier.weight(1f),
                placeholder = { Text("メッセージ") },
                maxLines = 6,
                shape = RoundedCornerShape(26.dp),
                colors = TextFieldDefaults.colors(
                    focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.7f),
                    unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.7f),
                    focusedIndicatorColor = Color.Transparent,
                    unfocusedIndicatorColor = Color.Transparent
                )
            )

            FilledIconButton(
                onClick = if (busy) onStop else onSend,
                enabled = if (busy) true else input.isNotBlank() && enabled,
                modifier = Modifier.size(52.dp)
            ) {
                Icon(
                    imageVector = if (busy) Icons.Rounded.Stop else Icons.Rounded.ArrowUpward,
                    contentDescription = if (busy) "停止" else "送信"
                )
            }
        }
    }
}

@Composable
private fun ContextMeter(telemetry: InferenceTelemetryState, configuredContext: Int) {
    val max = if (telemetry.contextMax > 0) telemetry.contextMax else configuredContext
    val used = if (telemetry.contextMax > 0) telemetry.contextUsed.coerceIn(0, max) else 0
    val remaining = (max - used).coerceAtLeast(0)
    val fraction = if (max > 0) used.toFloat() / max else 0f

    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("CONTEXT", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.weight(1f))
            Text("$used / $max · 残り $remaining", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(5.dp))
        LinearProgressIndicator(
            progress = { fraction.coerceIn(0f, 1f) },
            modifier = Modifier.fillMaxWidth().height(3.dp),
            trackColor = MaterialTheme.colorScheme.surfaceVariant
        )
    }
}

@Composable
private fun InferenceStatsLine(telemetry: InferenceTelemetryState, modifier: Modifier = Modifier) {
    Text(
        "Prefill ${telemetry.prefillLabel()} tok/s  ·  Decode ${telemetry.decodeLabel()} tok/s  ·  ${telemetry.generatedTokens} tok  ·  ${telemetry.backend}",
        modifier = modifier,
        style = MaterialTheme.typography.labelSmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant
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
            icon = { Icon(Icons.Rounded.DeleteOutline, contentDescription = null) },
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

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Long-term Memory", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    InfoChip(Icons.Rounded.Memory, "${ui.memoryCount}件")
                    InfoChip(Icons.Rounded.Hub, ui.embeddingEngineName)
                }
            }
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilledTonalButton(
                    onClick = { addingMemory = true },
                    enabled = !ui.busy && !ui.embeddingReindexing
                ) {
                    Icon(Icons.Rounded.Add, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("Memory追加")
                }
                OutlinedButton(
                    onClick = { confirmClear = true },
                    enabled = ui.memoryCount > 0 && !ui.busy && !ui.embeddingReindexing
                ) {
                    Icon(Icons.Rounded.DeleteOutline, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("全削除")
                }
                IconButton(onClick = vm::refresh) {
                    Icon(Icons.Rounded.Refresh, contentDescription = "更新")
                }
            }
        }

        item { MemoryTypeGuide() }

        if (ui.embeddingReindexing) {
            item {
                Surface(shape = MaterialTheme.shapes.medium, color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f)) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Embeddingを再索引中", fontWeight = FontWeight.SemiBold)
                        LinearProgressIndicator(
                            progress = { (ui.embeddingReindexProgress ?: 0f).coerceIn(0f, 1f) },
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            }
        }

        if (ui.memories.isEmpty()) {
            item {
                Box(Modifier.fillMaxWidth().padding(vertical = 56.dp), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(Icons.Rounded.Memory, contentDescription = null, tint = MaterialTheme.colorScheme.outline, modifier = Modifier.size(34.dp))
                        Text("まだ長期Memoryはありません", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        } else {
            items(ui.memories, key = { it.id }) { memory -> ModernMemoryCard(memory) }
        }

        item { Spacer(Modifier.height(24.dp)) }
    }
}

@Composable
private fun InfoChip(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) {
    Surface(shape = CircleShape, color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.65f)) {
        Row(
            Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(15.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
            Text(text, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun ModernMemoryCard(memory: MemoryRecord) {
    Surface(
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.46f)
    ) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer) {
                    Text(
                        memory.type,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onPrimaryContainer
                    )
                }
                Spacer(Modifier.weight(1f))
                Text("#${memory.id}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(memory.content, style = MaterialTheme.typography.bodyLarge)
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("importance ${memory.importance}/3", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text("confidence ${memory.confidence}/2", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(
                "${memory.origin}  ·  ${memory.embedding.size}d  ·  access ${memory.accessCount}  ·  ${formatMemoryDate(memory.createdAt)}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            if (memory.tags.isNotBlank()) {
                Text("# ${memory.tags.replace(",", "   #")}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            }
        }
    }
}

private fun formatMemoryDate(timestamp: Long): String =
    SimpleDateFormat("yyyy/MM/dd HH:mm", Locale.getDefault()).format(Date(timestamp))

@Composable
private fun SettingsScreen(
    vm: JinkakuViewModel,
    modifier: Modifier = Modifier,
    darkMode: Boolean,
    onDarkModeChange: (Boolean) -> Unit,
    share: (java.io.File, String) -> Unit
) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val e4bPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> if (uri != null) vm.importE4B(uri) }
    val e2bPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> if (uri != null) vm.importE2B(uri) }
    val embeddingPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> if (uri != null) vm.importEmbedding(uri) }
    var personaDraft by remember { mutableStateOf(vm.currentPersona()) }

    LazyColumn(
        modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { ScreenTitle("設定", "モデル・人格・外観・メンテナンス") }

        item {
            SettingsSection("外観") {
                SettingsToggleRow(
                    icon = Icons.Rounded.DarkMode,
                    title = "ダークモード",
                    subtitle = "画面全体を暗い配色にします。設定は次回起動後も保持されます。",
                    checked = darkMode,
                    onCheckedChange = onDarkModeChange
                )
            }
        }

        item {
            SettingsSection("Persona") {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedTextField(
                        value = personaDraft,
                        onValueChange = { personaDraft = it },
                        modifier = Modifier.fillMaxWidth().heightIn(min = 150.dp),
                        label = { Text("Jinkakuの基本人格") },
                        minLines = 5,
                        maxLines = 12
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = { vm.savePersona(personaDraft) },
                            enabled = personaDraft.isNotBlank() && !ui.busy
                        ) { Text("保存") }
                        TextButton(onClick = { personaDraft = vm.currentPersona() }) { Text("再読込") }
                    }
                    Text(
                        "保存するたびRevisionとして残ります。長期Memoryとして残す場合はMemory追加からPERSONAを選択します。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

        item { SectionLabel("モデル") }
        item {
            ModelCard(
                icon = Icons.Rounded.SmartToy,
                name = "Gemma 4 E4B HauhauCS",
                detail = "Main chat · Q2_K_P / local GGUF",
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
                icon = Icons.Rounded.AutoFixHigh,
                name = "Gemma 4 E2B LiteRT-LM",
                detail = "Memory worker",
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
                icon = Icons.Rounded.Hub,
                name = "EmbeddingGemma 300M Q4_0",
                detail = "Memory search · 約278MB",
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
            SettingsSection("Context") {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf(1024L, 2048L, 4096L, 8192L).forEach { size ->
                            FilterChip(
                                selected = ui.contextSize == size,
                                onClick = { vm.setContext(size) },
                                label = { Text("${size / 1024}K") }
                            )
                        }
                    }
                    Text(
                        "8Kで確保できない場合は4K → 2K → 1Kへ自動フォールバックします。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

        item {
            SettingsSection("長期メモリ") {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("${ui.memoryCount}件 · ${ui.embeddingEngineName}", fontWeight = FontWeight.SemiBold)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilledTonalButton(
                            onClick = vm::runMemoryMaintenance,
                            enabled = ui.e2bInstalled && !ui.busy && !ui.embeddingReindexing
                        ) { Text("記憶を整理") }
                        OutlinedButton(
                            onClick = vm::reindexMemories,
                            enabled = ui.embeddingInstalled && !ui.busy && !ui.embeddingImporting
                        ) { Text("再索引") }
                    }
                    if (ui.embeddingReindexing) {
                        LinearProgressIndicator(
                            progress = { (ui.embeddingReindexProgress ?: 0f).coerceIn(0f, 1f) },
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }
            }
        }

        item {
            SettingsSection("メンテナンス") {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SettingsActionRow(Icons.Rounded.Description, "ログを書き出す", "推論・モデル・Memoryの診断ログ") {
                        share(vm.exportLog(), "text/plain")
                    }
                    HorizontalDivider()
                    SettingsActionRow(Icons.Rounded.Backup, "バックアップ", "Persona・Memory・会話履歴をZIPへ保存") {
                        share(vm.createBackup(), "application/zip")
                    }
                }
            }
        }

        item {
            SettingsSection("アプリ更新") {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    SettingsActionRow(Icons.Rounded.SystemUpdate, "更新を確認", "GitHub Releasesから最新版を確認") { vm.checkUpdate() }
                    if (ui.updateInfo != null) {
                        HorizontalDivider()
                        SettingsActionRow(Icons.Rounded.Download, "APKを取得", "${ui.updateInfo?.versionName ?: "最新版"}をダウンロード") { vm.downloadUpdate() }
                    }
                    HorizontalDivider()
                    SettingsActionRow(Icons.Rounded.InstallMobile, "インストール", "ダウンロード済みAPKを開く") { vm.installUpdate() }
                }
            }
        }

        item { Spacer(Modifier.height(32.dp)) }
    }
}

@Composable
private fun ScreenTitle(title: String, subtitle: String) {
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(subtitle, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(text, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, modifier = Modifier.padding(top = 4.dp))
}

@Composable
private fun SettingsSection(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(7.dp)) {
        SectionLabel(title)
        Surface(
            shape = MaterialTheme.shapes.large,
            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.42f)
        ) { content() }
    }
}

@Composable
private fun SettingsToggleRow(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit
) {
    Row(
        Modifier.fillMaxWidth().padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
        Column(Modifier.weight(1f)) {
            Text(title, fontWeight = FontWeight.SemiBold)
            Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}

@Composable
private fun SettingsActionRow(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit
) {
    Surface(onClick = onClick, color = Color.Transparent) {
        Row(
            Modifier.fillMaxWidth().padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.Medium)
                Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(Icons.Rounded.ChevronRight, contentDescription = null, tint = MaterialTheme.colorScheme.outline)
        }
    }
}

@Composable
private fun ModelCard(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    name: String,
    detail: String,
    installed: Boolean,
    downloadProgress: Float?,
    importing: Boolean,
    importProgress: Float?,
    download: () -> Unit,
    importLocal: () -> Unit,
    delete: () -> Unit
) {
    Surface(
        shape = MaterialTheme.shapes.large,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.42f)
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Surface(shape = CircleShape, color = MaterialTheme.colorScheme.primaryContainer, modifier = Modifier.size(42.dp)) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
                    }
                }
                Column(Modifier.weight(1f)) {
                    Text(name, fontWeight = FontWeight.SemiBold)
                    Text(detail, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (installed) {
                    Icon(Icons.Rounded.CheckCircle, contentDescription = null, tint = MaterialTheme.colorScheme.tertiary)
                }
            }

            Text(
                when {
                    importing -> "ローカルファイルを取り込み中"
                    installed -> "インストール済み"
                    else -> "未インストール"
                },
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            if (importing) {
                LinearProgressIndicator(
                    progress = { (importProgress ?: 0f).coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth()
                )
            } else if (!installed && downloadProgress != null && downloadProgress > 0f && downloadProgress < 1f) {
                LinearProgressIndicator(progress = { downloadProgress }, modifier = Modifier.fillMaxWidth())
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!installed) {
                    FilledTonalButton(onClick = download, enabled = !importing) {
                        Icon(Icons.Rounded.Download, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text("ダウンロード")
                    }
                }
                OutlinedButton(onClick = importLocal, enabled = !importing) {
                    Icon(Icons.Rounded.FolderOpen, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("ローカル")
                }
                if (installed) {
                    TextButton(onClick = delete, enabled = !importing) { Text("削除") }
                }
            }
        }
    }
}
