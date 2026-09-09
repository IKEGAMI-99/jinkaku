package com.ikegami99.jinkaku.ui

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.Backup
import androidx.compose.material.icons.rounded.ChatBubbleOutline
import androidx.compose.material.icons.rounded.DarkMode
import androidx.compose.material.icons.rounded.DeleteOutline
import androidx.compose.material.icons.rounded.Download
import androidx.compose.material.icons.rounded.Edit
import androidx.compose.material.icons.rounded.FolderOpen
import androidx.compose.material.icons.rounded.History
import androidx.compose.material.icons.rounded.LightMode
import androidx.compose.material.icons.rounded.Memory
import androidx.compose.material.icons.rounded.Menu
import androidx.compose.material.icons.rounded.Psychology
import androidx.compose.material.icons.rounded.Refresh
import androidx.compose.material.icons.rounded.Send
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material.icons.rounded.Speed
import androidx.compose.material.icons.rounded.StopCircle
import androidx.compose.material.icons.rounded.Storage
import androidx.compose.material.icons.rounded.SystemUpdate
import androidx.compose.material.icons.rounded.Tune
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DarkColorScheme
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
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

private enum class ModernScreen { CHAT, MEMORY, SETTINGS }

private val ModernLight = lightColorScheme(
    primary = Color(0xFF6B4EFF),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE9E2FF),
    onPrimaryContainer = Color(0xFF21105E),
    secondary = Color(0xFF087F70),
    secondaryContainer = Color(0xFFB9F1E4),
    tertiary = Color(0xFF4E6596),
    background = Color(0xFFF8F7FC),
    surface = Color(0xFFF8F7FC),
    surfaceVariant = Color(0xFFE9E7EF),
    outline = Color(0xFF79747E)
)

private val ModernDark = darkColorScheme(
    primary = Color(0xFFC9B8FF),
    onPrimary = Color(0xFF351A9A),
    primaryContainer = Color(0xFF4934A8),
    onPrimaryContainer = Color(0xFFE9E2FF),
    secondary = Color(0xFF7EDCCB),
    secondaryContainer = Color(0xFF005047),
    tertiary = Color(0xFFB6C7F2),
    background = Color(0xFF0C0D12),
    surface = Color(0xFF0C0D12),
    surfaceVariant = Color(0xFF292A31),
    outline = Color(0xFF96929D)
)

private fun modernTypingLabel(tokens: Int): String = "入力中" + ".".repeat((tokens.mod(3)) + 1)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ModernJinkakuApp(vm: JinkakuViewModel) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val telemetry by InferenceTelemetry.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    val prefs = remember(context) { context.getSharedPreferences("settings", android.content.Context.MODE_PRIVATE) }
    var darkMode by remember { mutableStateOf(prefs.getBoolean("dark_mode", false)) }
    var screen by remember { mutableStateOf(ModernScreen.CHAT) }
    var confirmClearChats by remember { mutableStateOf(false) }
    val drawerState = androidx.compose.material3.rememberDrawerState(androidx.compose.material3.DrawerValue.Closed)
    val snackbar = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current

    fun dismissIme() {
        focusManager.clearFocus(force = true)
        keyboard?.hide()
    }

    fun changeDarkMode(enabled: Boolean) {
        darkMode = enabled
        prefs.edit().putBoolean("dark_mode", enabled).apply()
    }

    val statusText = if (ui.busy && (ui.runtimeStatus == "入力中" || ui.runtimeStatus == "生成中")) {
        modernTypingLabel(telemetry.generatedTokens)
    } else ui.runtimeStatus

    LaunchedEffect(ui.error, ui.notice) {
        val message = ui.error ?: ui.notice
        if (message != null) {
            snackbar.showSnackbar(message)
            vm.clearMessagesNotice()
        }
    }

    MaterialTheme(
        colorScheme = if (darkMode) ModernDark else ModernLight,
        shapes = androidx.compose.material3.Shapes(
            extraSmall = RoundedCornerShape(10.dp),
            small = RoundedCornerShape(14.dp),
            medium = RoundedCornerShape(20.dp),
            large = RoundedCornerShape(28.dp),
            extraLarge = RoundedCornerShape(34.dp)
        )
    ) {
        if (confirmClearChats) {
            AlertDialog(
                onDismissRequest = { confirmClearChats = false },
                title = { Text("Chat履歴を全件削除") },
                text = { Text("すべてのチャットとメッセージを削除します。長期MemoryとPersonaは残ります。") },
                confirmButton = {
                    Button(
                        onClick = {
                            confirmClearChats = false
                            vm.clearChatHistory()
                            screen = ModernScreen.CHAT
                            scope.launch { drawerState.close() }
                        },
                        enabled = !ui.busy
                    ) { Text("全件削除") }
                },
                dismissButton = { TextButton(onClick = { confirmClearChats = false }) { Text("キャンセル") } }
            )
        }

        ModalNavigationDrawer(
            drawerState = drawerState,
            drawerContent = {
                ModalDrawerSheet(
                    drawerContainerColor = MaterialTheme.colorScheme.surface,
                    modifier = Modifier.widthIn(max = 360.dp)
                ) {
                    Column(Modifier.fillMaxHeight().statusBarsPadding()) {
                        BrandHeader(Modifier.padding(horizontal = 20.dp, vertical = 18.dp))
                        NavigationDrawerItem(
                            selected = screen == ModernScreen.CHAT,
                            onClick = {
                                dismissIme(); screen = ModernScreen.CHAT
                                scope.launch { drawerState.close() }
                            },
                            icon = { Icon(Icons.Rounded.ChatBubbleOutline, null) },
                            label = { Text("チャット") },
                            modifier = Modifier.padding(horizontal = 12.dp)
                        )
                        NavigationDrawerItem(
                            selected = screen == ModernScreen.MEMORY,
                            onClick = {
                                dismissIme(); screen = ModernScreen.MEMORY; vm.refresh()
                                scope.launch { drawerState.close() }
                            },
                            icon = { Icon(Icons.Rounded.Memory, null) },
                            label = { Text("Memory  ${ui.memoryCount}") },
                            modifier = Modifier.padding(horizontal = 12.dp)
                        )
                        NavigationDrawerItem(
                            selected = screen == ModernScreen.SETTINGS,
                            onClick = {
                                dismissIme(); screen = ModernScreen.SETTINGS
                                scope.launch { drawerState.close() }
                            },
                            icon = { Icon(Icons.Rounded.Settings, null) },
                            label = { Text("設定") },
                            modifier = Modifier.padding(horizontal = 12.dp)
                        )
                        HorizontalDivider(Modifier.padding(vertical = 12.dp))
                        Row(
                            Modifier.fillMaxWidth().padding(start = 20.dp, end = 10.dp, top = 4.dp, bottom = 4.dp),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Icon(Icons.Rounded.History, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
                            Spacer(Modifier.width(10.dp))
                            Text("Chat履歴", fontWeight = FontWeight.SemiBold)
                            Spacer(Modifier.weight(1f))
                            TextButton(
                                onClick = { confirmClearChats = true },
                                enabled = ui.chats.isNotEmpty() && !ui.busy &&
                                    !ui.e4bImporting && !ui.e2bImporting &&
                                    !ui.embeddingImporting && !ui.embeddingReindexing
                            ) {
                                Icon(Icons.Rounded.DeleteOutline, null, modifier = Modifier.size(17.dp))
                                Spacer(Modifier.width(4.dp))
                                Text("全件削除")
                            }
                        }
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(horizontal = 10.dp, vertical = 4.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            items(ui.chats, key = { it.id }) { chat ->
                                NavigationDrawerItem(
                                    selected = screen == ModernScreen.CHAT && chat.id == ui.currentChatId,
                                    onClick = {
                                        dismissIme(); screen = ModernScreen.CHAT; vm.selectChat(chat.id)
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
                containerColor = MaterialTheme.colorScheme.background,
                snackbarHost = { SnackbarHost(snackbar) },
                topBar = {
                    TopAppBar(
                        colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),
                        navigationIcon = {
                            IconButton(onClick = { dismissIme(); scope.launch { drawerState.open() } }) {
                                Icon(Icons.Rounded.Menu, contentDescription = "メニュー")
                            }
                        },
                        title = {
                            Column {
                                Text("Jinkaku", fontWeight = FontWeight.Bold)
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    StatusDot(ui.busy)
                                    Text(
                                        "$statusText  ·  Memory ${ui.memoryCount}",
                                        style = MaterialTheme.typography.labelMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        },
                        actions = {
                            if (screen == ModernScreen.CHAT) {
                                FilledTonalButton(
                                    onClick = { dismissIme(); vm.newChat() },
                                    contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
                                    modifier = Modifier.padding(end = 6.dp)
                                ) {
                                    Icon(Icons.Rounded.Add, null, modifier = Modifier.size(18.dp))
                                    Spacer(Modifier.width(4.dp))
                                    Text("New")
                                }
                            }
                            IconButton(onClick = {
                                dismissIme(); screen = if (screen == ModernScreen.SETTINGS) ModernScreen.CHAT else ModernScreen.SETTINGS
                            }) {
                                Icon(if (screen == ModernScreen.SETTINGS) Icons.Rounded.ChatBubbleOutline else Icons.Rounded.Settings, null)
                            }
                        }
                    )
                }
            ) { padding ->
                when (screen) {
                    ModernScreen.CHAT -> ModernChatScreen(vm, Modifier.padding(padding))
                    ModernScreen.MEMORY -> ModernMemoryScreen(vm, Modifier.padding(padding))
                    ModernScreen.SETTINGS -> ModernSettingsScreen(
                        vm = vm,
                        modifier = Modifier.padding(padding),
                        darkMode = darkMode,
                        onDarkModeChange = ::changeDarkMode,
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
private fun BrandHeader(modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Surface(
            shape = RoundedCornerShape(18.dp),
            color = MaterialTheme.colorScheme.primaryContainer,
            modifier = Modifier.size(48.dp)
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(Icons.Rounded.Psychology, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(28.dp))
            }
        }
        Column {
            Text("Jinkaku", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("Local persona AI", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun StatusDot(active: Boolean) {
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = if (active) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.outline,
        modifier = Modifier.size(7.dp)
    ) {}
}

@Composable
private fun ModernChatScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val telemetry by InferenceTelemetry.state.collectAsStateWithLifecycle()
    var input by remember { mutableStateOf("") }
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    val listState = rememberLazyListState()
    val showTypingBubble = ui.busy && telemetry.phase in setOf("PREFILL", "THINKING", "DECODE")

    fun submit() {
        val value = input.trim()
        if (value.isBlank()) return
        input = ""
        focusManager.clearFocus(force = true)
        keyboard?.hide()
        vm.send(value)
    }

    LaunchedEffect(ui.messages.size, showTypingBubble, telemetry.generatedTokens) {
        val total = ui.messages.size + if (showTypingBubble) 1 else 0
        if (total > 0) listState.animateScrollToItem(total - 1)
    }

    Column(modifier.fillMaxSize()) {
        ModernContextCard(telemetry, ui.contextSize.toInt(), Modifier.padding(horizontal = 14.dp, vertical = 8.dp))

        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(ui.messages, key = { it.id }) { message ->
                Column(Modifier.fillMaxWidth()) {
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = if (message.role == ROLE_USER) Arrangement.End else Arrangement.Start
                    ) {
                        Surface(
                            shape = if (message.role == ROLE_USER) {
                                RoundedCornerShape(24.dp, 24.dp, 6.dp, 24.dp)
                            } else {
                                RoundedCornerShape(24.dp, 24.dp, 24.dp, 6.dp)
                            },
                            color = if (message.role == ROLE_USER) {
                                MaterialTheme.colorScheme.primaryContainer
                            } else {
                                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.7f)
                            },
                            modifier = Modifier.fillMaxWidth(0.88f)
                        ) {
                            Text(
                                message.content,
                                modifier = Modifier.padding(horizontal = 16.dp, vertical = 13.dp),
                                style = MaterialTheme.typography.bodyLarge
                            )
                        }
                    }
                    if (
                        message.role != ROLE_USER && telemetry.phase == "DONE" &&
                        telemetry.finalTextHash != null && telemetry.finalTextHash == message.content.hashCode()
                    ) {
                        Text(
                            "Prefill ${telemetry.prefillLabel()} tok/s  ·  Decode ${telemetry.decodeLabel()} tok/s  ·  ${telemetry.generatedTokens} tok  ·  ${telemetry.backend}",
                            modifier = Modifier.padding(start = 10.dp, top = 5.dp),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }

            if (showTypingBubble) {
                item {
                    Surface(
                        shape = RoundedCornerShape(24.dp, 24.dp, 24.dp, 6.dp),
                        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.7f)
                    ) {
                        Row(
                            Modifier.padding(horizontal = 16.dp, vertical = 13.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            StatusDot(true)
                            Text(modernTypingLabel(telemetry.generatedTokens), color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }

        Surface(
            color = MaterialTheme.colorScheme.background,
            tonalElevation = 2.dp
        ) {
            Row(
                Modifier.fillMaxWidth().imePadding().navigationBarsPadding().padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.Bottom,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = input,
                    onValueChange = { input = it },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("メッセージを入力") },
                    shape = RoundedCornerShape(24.dp),
                    maxLines = 6
                )
                FilledIconButton(
                    onClick = {
                        if (ui.busy) {
                            focusManager.clearFocus(force = true); keyboard?.hide(); vm.stopGeneration()
                        } else submit()
                    },
                    enabled = ui.busy || input.isNotBlank(),
                    modifier = Modifier.size(54.dp)
                ) {
                    Icon(if (ui.busy) Icons.Rounded.StopCircle else Icons.Rounded.Send, null)
                }
            }
        }
    }
}

@Composable
private fun ModernContextCard(telemetry: InferenceTelemetryState, configuredContext: Int, modifier: Modifier = Modifier) {
    val max = if (telemetry.contextMax > 0) telemetry.contextMax else configuredContext
    val used = if (telemetry.contextMax > 0) telemetry.contextUsed.coerceIn(0, max) else 0
    val remaining = (max - used).coerceAtLeast(0)
    val fraction = if (max > 0) used.toFloat() / max else 0f

    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.45f)),
        shape = RoundedCornerShape(20.dp)
    ) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column {
                    Text("CONTEXT", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                    Text("$used / $max tok", fontWeight = FontWeight.SemiBold)
                }
                Spacer(Modifier.weight(1f))
                AssistChip(onClick = {}, label = { Text("残り $remaining") })
            }
            LinearProgressIndicator(
                progress = { fraction.coerceIn(0f, 1f) },
                modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(999.dp))
            )
        }
    }
}

@Composable
private fun ModernMemoryScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    var adding by remember { mutableStateOf(false) }
    var confirmClear by remember { mutableStateOf(false) }

    if (adding) {
        ManualMemoryDialog(vm, ui.embeddingInstalled) { adding = false }
    }

    if (confirmClear) {
        AlertDialog(
            onDismissRequest = { confirmClear = false },
            title = { Text("Memoryを全削除") },
            text = { Text("長期Memoryと未処理のMemory候補を削除します。チャット履歴とPersonaは残ります。") },
            confirmButton = {
                Button(onClick = { confirmClear = false; vm.clearMemories() }) { Text("削除") }
            },
            dismissButton = { TextButton(onClick = { confirmClear = false }) { Text("キャンセル") } }
        )
    }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.75f)),
                shape = RoundedCornerShape(28.dp)
            ) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Surface(
                            shape = RoundedCornerShape(16.dp),
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.size(44.dp)
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(Icons.Rounded.Memory, null, tint = MaterialTheme.colorScheme.onPrimary)
                            }
                        }
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text("Long-term Memory", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                            Text("${ui.memoryCount}件  ·  ${ui.embeddingEngineName}", color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.78f))
                        }
                        IconButton(onClick = vm::refresh) { Icon(Icons.Rounded.Refresh, null) }
                    }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { adding = true }, enabled = !ui.busy && !ui.embeddingReindexing) {
                            Icon(Icons.Rounded.Add, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(5.dp)); Text("Memory追加")
                        }
                        OutlinedButton(onClick = { confirmClear = true }, enabled = ui.memoryCount > 0 && !ui.busy) {
                            Icon(Icons.Rounded.DeleteOutline, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(5.dp)); Text("全削除")
                        }
                    }
                }
            }
        }

        item { MemoryTypeGuide() }

        if (ui.embeddingReindexing) {
            item {
                Card {
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
                Box(Modifier.fillMaxWidth().height(220.dp), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(Icons.Rounded.Storage, null, modifier = Modifier.size(36.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
                        Text("まだMemoryはありません", color = MaterialTheme.colorScheme.onSurfaceVariant)
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
private fun ModernMemoryCard(memory: MemoryRecord) {
    Card(
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f))
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                AssistChip(onClick = {}, label = { Text(memory.type) })
                Spacer(Modifier.weight(1f))
                Text("#${memory.id}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(memory.content, style = MaterialTheme.typography.bodyLarge)
            Text(
                "重要度 ${memory.importance}/3  ·  confidence ${memory.confidence}/2  ·  ${memory.origin}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                "${memory.embedding.size}d index  ·  access ${memory.accessCount}  ·  ${modernMemoryDate(memory.createdAt)}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            if (memory.tags.isNotBlank()) Text("# ${memory.tags}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary)
        }
    }
}

private fun modernMemoryDate(timestamp: Long): String = SimpleDateFormat("yyyy/MM/dd HH:mm", Locale.getDefault()).format(Date(timestamp))

@Composable
private fun ModernSettingsScreen(
    vm: JinkakuViewModel,
    modifier: Modifier = Modifier,
    darkMode: Boolean,
    onDarkModeChange: (Boolean) -> Unit,
    share: (java.io.File, String) -> Unit
) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val e4bPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { if (it != null) vm.importE4B(it) }
    val e2bPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { if (it != null) vm.importE2B(it) }
    val embeddingPicker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { if (it != null) vm.importEmbedding(it) }
    var personaDraft by remember { mutableStateOf(vm.currentPersona()) }

    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item { ModernSectionTitle("外観", Icons.Rounded.DarkMode) }
        item {
            ModernSettingsCard {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Surface(shape = RoundedCornerShape(14.dp), color = MaterialTheme.colorScheme.primaryContainer, modifier = Modifier.size(42.dp)) {
                        Box(contentAlignment = Alignment.Center) { Icon(if (darkMode) Icons.Rounded.DarkMode else Icons.Rounded.LightMode, null) }
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text("ダークモード", fontWeight = FontWeight.SemiBold)
                        Text("アプリ全体の配色を切り替えます", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Switch(checked = darkMode, onCheckedChange = onDarkModeChange)
                }
            }
        }

        item { ModernSectionTitle("Persona", Icons.Rounded.Psychology) }
        item {
            ModernSettingsCard {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedTextField(
                        value = personaDraft,
                        onValueChange = { personaDraft = it },
                        modifier = Modifier.fillMaxWidth().heightIn(min = 150.dp),
                        label = { Text("Jinkakuの基本人格") },
                        minLines = 5,
                        maxLines = 12,
                        shape = RoundedCornerShape(18.dp)
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { vm.savePersona(personaDraft) }, enabled = personaDraft.isNotBlank() && !ui.busy) {
                            Icon(Icons.Rounded.Edit, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(5.dp)); Text("保存")
                        }
                        OutlinedButton(onClick = { personaDraft = vm.currentPersona() }) { Text("再読込") }
                    }
                    Text("Personaの一部を長期Memoryにも残したい場合はMemory画面からPERSONAとして追加できます。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        item { ModernSectionTitle("モデル", Icons.Rounded.Storage) }
        item {
            ModernModelCard(
                title = "Gemma 4 E4B HauhauCS",
                subtitle = "Main chat model · GGUF",
                installed = ui.e4bInstalled,
                progress = ui.e4bDownload?.progress,
                importing = ui.e4bImporting,
                importProgress = ui.e4bImportProgress,
                onDownload = vm::downloadE4B,
                onLocal = { e4bPicker.launch(arrayOf("*/*")) },
                onDelete = vm::deleteE4B
            )
        }
        item {
            ModernModelCard(
                title = "Gemma 4 E2B LiteRT-LM",
                subtitle = "Memory maintenance model",
                installed = ui.e2bInstalled,
                progress = ui.e2bDownload?.progress,
                importing = ui.e2bImporting,
                importProgress = ui.e2bImportProgress,
                onDownload = vm::downloadE2B,
                onLocal = { e2bPicker.launch(arrayOf("*/*")) },
                onDelete = vm::deleteE2B
            )
        }
        item {
            ModernModelCard(
                title = "EmbeddingGemma 300M Q4_0",
                subtitle = "Memory retrieval · 約278MB",
                installed = ui.embeddingInstalled,
                progress = ui.embeddingDownload?.progress,
                importing = ui.embeddingImporting,
                importProgress = ui.embeddingImportProgress,
                onDownload = vm::downloadEmbedding,
                onLocal = { embeddingPicker.launch(arrayOf("*/*")) },
                onDelete = vm::deleteEmbedding
            )
        }

        item { ModernSectionTitle("推論", Icons.Rounded.Speed) }
        item {
            ModernSettingsCard {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("Context window", fontWeight = FontWeight.SemiBold)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf(1024L, 2048L, 4096L, 8192L).forEach { size ->
                            FilterChip(
                                selected = ui.contextSize == size,
                                onClick = { vm.setContext(size) },
                                label = { Text("${size / 1024}K") }
                            )
                        }
                    }
                    Text("CoTは有効で非表示。回答本文はDecode完了後に一括表示します。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        item { ModernSectionTitle("Memory", Icons.Rounded.Memory) }
        item {
            ModernSettingsCard {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("${ui.memoryCount}件  ·  ${ui.embeddingEngineName}", fontWeight = FontWeight.SemiBold)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = vm::runMemoryMaintenance, enabled = ui.e2bInstalled && !ui.busy && !ui.embeddingReindexing) { Text("記憶を整理") }
                        OutlinedButton(onClick = vm::reindexMemories, enabled = ui.embeddingInstalled && !ui.busy && !ui.embeddingImporting) { Text("再索引") }
                    }
                    if (ui.embeddingReindexing) LinearProgressIndicator(progress = { (ui.embeddingReindexProgress ?: 0f).coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
                }
            }
        }

        item { ModernSectionTitle("メンテナンス", Icons.Rounded.Tune) }
        item {
            ModernSettingsCard {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { share(vm.exportLog(), "text/plain") }, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Rounded.Storage, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("ログを書き出す")
                    }
                    OutlinedButton(onClick = { share(vm.createBackup(), "application/zip") }, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Rounded.Backup, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("バックアップ")
                    }
                }
            }
        }

        item { ModernSectionTitle("アプリ更新", Icons.Rounded.SystemUpdate) }
        item {
            ModernSettingsCard {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = vm::checkUpdate, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Rounded.Refresh, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("更新を確認")
                    }
                    if (ui.updateInfo != null) {
                        OutlinedButton(onClick = vm::downloadUpdate, modifier = Modifier.fillMaxWidth()) {
                            Icon(Icons.Rounded.Download, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("APKを取得")
                        }
                    }
                    OutlinedButton(onClick = vm::installUpdate, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Rounded.SystemUpdate, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("インストール")
                    }
                }
            }
        }

        item { Spacer(Modifier.height(30.dp)) }
    }
}

@Composable
private fun ModernSectionTitle(text: String, icon: androidx.compose.ui.graphics.vector.ImageVector) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 6.dp, start = 4.dp)) {
        Icon(icon, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
        Text(text, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun ModernSettingsCard(content: @Composable () -> Unit) {
    Card(
        shape = RoundedCornerShape(22.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.46f))
    ) {
        Box(Modifier.fillMaxWidth().padding(16.dp)) { content() }
    }
}

@Composable
private fun ModernModelCard(
    title: String,
    subtitle: String,
    installed: Boolean,
    progress: Float?,
    importing: Boolean,
    importProgress: Float?,
    onDownload: () -> Unit,
    onLocal: () -> Unit,
    onDelete: () -> Unit
) {
    ModernSettingsCard {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Surface(shape = RoundedCornerShape(14.dp), color = MaterialTheme.colorScheme.secondaryContainer, modifier = Modifier.size(42.dp)) {
                    Box(contentAlignment = Alignment.Center) { Icon(Icons.Rounded.Storage, null, tint = MaterialTheme.colorScheme.secondary) }
                }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(title, fontWeight = FontWeight.SemiBold)
                    Text(subtitle, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                AssistChip(onClick = {}, label = { Text(if (installed) "Installed" else if (importing) "Importing" else "Not installed") })
            }
            if (importing) {
                LinearProgressIndicator(progress = { (importProgress ?: 0f).coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
            } else if (!installed && progress != null && progress > 0f && progress < 1f) {
                LinearProgressIndicator(progress = { progress.coerceIn(0f, 1f) }, modifier = Modifier.fillMaxWidth())
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!installed) {
                    Button(onClick = onDownload, enabled = !importing, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Rounded.Download, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Download")
                    }
                }
                OutlinedButton(onClick = onLocal, enabled = !importing, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Rounded.FolderOpen, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("Local")
                }
                if (installed) {
                    OutlinedButton(onClick = onDelete, enabled = !importing, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Rounded.DeleteOutline, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(4.dp)); Text("削除")
                    }
                }
            }
        }
    }
}
