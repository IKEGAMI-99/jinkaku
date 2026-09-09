from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt"
VM = ROOT / "app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt"
DB = ROOT / "app/src/main/java/com/ikegami99/jinkaku/data/JinkakuDatabase.kt"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


# --- UI: delay the typing bubble until PREFILL actually starts. ---
ui = UI.read_text(encoding="utf-8")
ui = replace_once(
    ui,
    '    var screen by remember { mutableStateOf(ModernScreen.CHAT) }\n',
    '    var screen by remember { mutableStateOf(ModernScreen.CHAT) }\n'
    '    var confirmClearChats by remember { mutableStateOf(false) }\n',
    "add clear-history dialog state",
)

ui = replace_once(
    ui,
    '    ) {\n'
    '        ModalNavigationDrawer(\n',
    '    ) {\n'
    '        if (confirmClearChats) {\n'
    '            AlertDialog(\n'
    '                onDismissRequest = { confirmClearChats = false },\n'
    '                title = { Text("Chat履歴を全件削除") },\n'
    '                text = { Text("すべてのチャットとメッセージを削除します。長期MemoryとPersonaは残ります。") },\n'
    '                confirmButton = {\n'
    '                    Button(\n'
    '                        onClick = {\n'
    '                            confirmClearChats = false\n'
    '                            vm.clearChatHistory()\n'
    '                            screen = ModernScreen.CHAT\n'
    '                            scope.launch { drawerState.close() }\n'
    '                        },\n'
    '                        enabled = !ui.busy\n'
    '                    ) { Text("全件削除") }\n'
    '                },\n'
    '                dismissButton = { TextButton(onClick = { confirmClearChats = false }) { Text("キャンセル") } }\n'
    '            )\n'
    '        }\n\n'
    '        ModalNavigationDrawer(\n',
    "insert clear-history confirmation dialog",
)

ui = replace_once(
    ui,
    '                        Row(\n'
    '                            Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp),\n'
    '                            verticalAlignment = Alignment.CenterVertically\n'
    '                        ) {\n'
    '                            Icon(Icons.Rounded.History, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)\n'
    '                            Spacer(Modifier.width(10.dp))\n'
    '                            Text("Chat履歴", fontWeight = FontWeight.SemiBold)\n'
    '                        }\n',
    '                        Row(\n'
    '                            Modifier.fillMaxWidth().padding(start = 20.dp, end = 10.dp, top = 4.dp, bottom = 4.dp),\n'
    '                            verticalAlignment = Alignment.CenterVertically\n'
    '                        ) {\n'
    '                            Icon(Icons.Rounded.History, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)\n'
    '                            Spacer(Modifier.width(10.dp))\n'
    '                            Text("Chat履歴", fontWeight = FontWeight.SemiBold)\n'
    '                            Spacer(Modifier.weight(1f))\n'
    '                            TextButton(\n'
    '                                onClick = { confirmClearChats = true },\n'
    '                                enabled = ui.chats.isNotEmpty() && !ui.busy &&\n'
    '                                    !ui.e4bImporting && !ui.e2bImporting &&\n'
    '                                    !ui.embeddingImporting && !ui.embeddingReindexing\n'
    '                            ) {\n'
    '                                Icon(Icons.Rounded.DeleteOutline, null, modifier = Modifier.size(17.dp))\n'
    '                                Spacer(Modifier.width(4.dp))\n'
    '                                Text("全件削除")\n'
    '                            }\n'
    '                        }\n',
    "add clear-all button to chat history header",
)

ui = replace_once(
    ui,
    '    val listState = rememberLazyListState()\n\n'
    '    fun submit() {\n',
    '    val listState = rememberLazyListState()\n'
    '    val showTypingBubble = ui.busy && telemetry.phase in setOf("PREFILL", "THINKING", "DECODE")\n\n'
    '    fun submit() {\n',
    "derive typing bubble visibility from inference phase",
)

ui = replace_once(
    ui,
    '    LaunchedEffect(ui.messages.size, ui.busy, telemetry.generatedTokens) {\n'
    '        val total = ui.messages.size + if (ui.busy) 1 else 0\n'
    '        if (total > 0) listState.animateScrollToItem(total - 1)\n'
    '    }\n',
    '    LaunchedEffect(ui.messages.size, showTypingBubble, telemetry.generatedTokens) {\n'
    '        val total = ui.messages.size + if (showTypingBubble) 1 else 0\n'
    '        if (total > 0) listState.animateScrollToItem(total - 1)\n'
    '    }\n',
    "sync auto-scroll with actual typing bubble visibility",
)

ui = replace_once(
    ui,
    '            if (ui.busy) {\n'
    '                item {\n'
    '                    Surface(\n',
    '            if (showTypingBubble) {\n'
    '                item {\n'
    '                    Surface(\n',
    "show typing bubble only from PREFILL onward",
)

UI.write_text(ui, encoding="utf-8")


# --- Database: atomically remove all chats/messages and immediately create a fresh chat. ---
db = DB.read_text(encoding="utf-8")
anchor = '''    fun listChats(limit: Int = 100): List<ChatSession> {
        val out = mutableListOf<ChatSession>()
        readableDatabase.rawQuery(
            "SELECT id,title,created_at,updated_at FROM chats ORDER BY updated_at DESC,id DESC LIMIT ?",
            arrayOf(limit.toString())
        ).use { c ->
            while (c.moveToNext()) out += ChatSession(c.getLong(0), c.getString(1), c.getLong(2), c.getLong(3))
        }
        return out
    }
'''
replacement = anchor + '''
    fun clearAllChatsAndCreateFresh(): Pair<Int, Long> {
        val database = writableDatabase
        database.beginTransaction()
        return try {
            val deleted = database.delete("chats", null, null)
            val now = System.currentTimeMillis()
            val values = ContentValues().apply {
                put("title", "New chat")
                put("created_at", now)
                put("updated_at", now)
            }
            val newChatId = database.insertOrThrow("chats", null, values)
            database.setTransactionSuccessful()
            deleted to newChatId
        } finally {
            database.endTransaction()
        }
    }
'''
db = replace_once(db, anchor, replacement, "add database clear-all-chats transaction")
DB.write_text(db, encoding="utf-8")


# --- ViewModel: expose safe chat-history clearing while preserving memories/persona. ---
vm = VM.read_text(encoding="utf-8")
anchor = '''    fun selectChat(chatId: Long) {
        if (_ui.value.busy || anyModelImporting()) {
            setError("処理中はチャットを切り替えられません")
            return
        }
        if (!db.chatExists(chatId)) {
            setError("チャット履歴が見つかりません")
            return
        }
        e4b.unload()
        currentChatId = chatId
        prefs.edit().putLong(KEY_CURRENT_CHAT_ID, currentChatId).apply()
        _ui.value = _ui.value.copy(generatingText = "", thinking = false, runtimeStatus = "IDLE")
        refresh()
        logger.i("CHAT", "Chat selected id=$chatId")
    }
'''
replacement = anchor + '''
    fun clearChatHistory() {
        if (_ui.value.busy || anyModelImporting()) {
            setError("処理中はChat履歴を削除できません")
            return
        }
        generationJob?.cancel()
        memoryIdleJob?.cancel()
        e4b.unload()
        val (deleted, freshChatId) = db.clearAllChatsAndCreateFresh()
        currentChatId = freshChatId
        prefs.edit().putLong(KEY_CURRENT_CHAT_ID, currentChatId).apply()
        _ui.value = _ui.value.copy(
            generatingText = "",
            thinking = false,
            runtimeStatus = "IDLE",
            notice = "Chat履歴を${deleted}件削除しました"
        )
        refresh()
        logger.w("CHAT", "All chat history cleared deletedChats=$deleted freshChatId=$freshChatId")
    }
'''
vm = replace_once(vm, anchor, replacement, "add ViewModel clearChatHistory")
VM.write_text(vm, encoding="utf-8")

print("Patched typing bubble timing and chat history clear-all support.")
