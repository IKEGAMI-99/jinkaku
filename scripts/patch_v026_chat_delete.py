from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_database() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/data/JinkakuDatabase.kt")
    text = path.read_text(encoding="utf-8")
    if "fun deleteChat(chatId: Long)" in text:
        print("JinkakuDatabase chat-delete patch already applied")
        return

    anchor = '''    fun maybeTitleChat(chatId: Long, firstUserText: String) {\n'''
    insertion = '''    fun deleteChat(chatId: Long): Int = writableDatabase.delete(\n        "chats",\n        "id=?",\n        arrayOf(chatId.toString())\n    )\n\n    fun maybeTitleChat(chatId: Long, firstUserText: String) {\n'''
    text = replace_once(text, anchor, insertion, "database deleteChat")
    path.write_text(text, encoding="utf-8")


def patch_view_model() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
    text = path.read_text(encoding="utf-8")
    if "fun deleteChat(chatId: Long)" in text:
        print("JinkakuViewModel chat-delete patch already applied")
        return

    anchor = '''    fun send(text: String) {\n'''
    insertion = '''    fun deleteChat(chatId: Long) {\n        if (_ui.value.busy || anyModelImporting()) {\n            setError("処理中はチャット履歴を削除できません")\n            return\n        }\n        if (!db.chatExists(chatId)) {\n            setError("削除するチャット履歴が見つかりません")\n            return\n        }\n\n        val deletingCurrent = chatId == currentChatId\n        if (deletingCurrent) {\n            memoryIdleJob?.cancel()\n            e4b.unload()\n        }\n\n        val deleted = db.deleteChat(chatId)\n        if (deleted <= 0) {\n            setError("チャット履歴を削除できませんでした")\n            return\n        }\n\n        if (deletingCurrent) {\n            currentChatId = db.listChats(1).firstOrNull()?.id ?: db.createChat()\n            prefs.edit().putLong(KEY_CURRENT_CHAT_ID, currentChatId).apply()\n            _ui.value = _ui.value.copy(\n                generatingText = "",\n                thinking = false,\n                runtimeStatus = "IDLE"\n            )\n        }\n\n        refresh()\n        _ui.value = _ui.value.copy(notice = "チャット履歴を削除しました")\n        logger.w("CHAT", "Chat deleted id=$chatId current=$deletingCurrent")\n    }\n\n    fun send(text: String) {\n'''
    text = replace_once(text, anchor, insertion, "view model deleteChat")
    path.write_text(text, encoding="utf-8")


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")
    if "pendingDeleteChatId" in text:
        print("ModernJinkakuApp chat-delete patch already applied")
        return

    text = replace_once(
        text,
        '''    var screen by remember { mutableStateOf(ModernScreen.CHAT) }\n''',
        '''    var screen by remember { mutableStateOf(ModernScreen.CHAT) }\n    var pendingDeleteChatId by remember { mutableStateOf<Long?>(null) }\n''',
        "delete dialog state",
    )

    old_items = '''                            items(ui.chats, key = { it.id }) { chat ->\n                                NavigationDrawerItem(\n                                    selected = screen == ModernScreen.CHAT && chat.id == ui.currentChatId,\n                                    onClick = {\n                                        dismissIme(); screen = ModernScreen.CHAT; vm.selectChat(chat.id)\n                                        scope.launch { drawerState.close() }\n                                    },\n                                    label = { Text(chat.title, maxLines = 2, overflow = TextOverflow.Ellipsis) }\n                                )\n                            }\n'''
    new_items = '''                            items(ui.chats, key = { it.id }) { chat ->\n                                Row(\n                                    modifier = Modifier.fillMaxWidth(),\n                                    verticalAlignment = Alignment.CenterVertically\n                                ) {\n                                    NavigationDrawerItem(\n                                        selected = screen == ModernScreen.CHAT && chat.id == ui.currentChatId,\n                                        onClick = {\n                                            dismissIme(); screen = ModernScreen.CHAT; vm.selectChat(chat.id)\n                                            scope.launch { drawerState.close() }\n                                        },\n                                        label = { Text(chat.title, maxLines = 2, overflow = TextOverflow.Ellipsis) },\n                                        modifier = Modifier.weight(1f)\n                                    )\n                                    IconButton(\n                                        onClick = { pendingDeleteChatId = chat.id },\n                                        enabled = !ui.busy\n                                    ) {\n                                        Icon(\n                                            Icons.Rounded.DeleteOutline,\n                                            contentDescription = "チャット履歴を削除",\n                                            tint = MaterialTheme.colorScheme.onSurfaceVariant\n                                        )\n                                    }\n                                }\n                            }\n'''
    text = replace_once(text, old_items, new_items, "chat history delete buttons")

    modal_anchor = '''        ModalNavigationDrawer(\n'''
    modal_with_dialog = '''        val pendingDeleteTitle = pendingDeleteChatId?.let { id ->\n            ui.chats.firstOrNull { it.id == id }?.title ?: "このチャット"\n        }\n        if (pendingDeleteChatId != null) {\n            AlertDialog(\n                onDismissRequest = { pendingDeleteChatId = null },\n                title = { Text("チャット履歴を削除") },\n                text = {\n                    Text(\n                        "「${pendingDeleteTitle ?: "このチャット"}」を削除します。会話本文は削除されますが、長期Memoryは残ります。"\n                    )\n                },\n                confirmButton = {\n                    TextButton(\n                        onClick = {\n                            val id = pendingDeleteChatId\n                            pendingDeleteChatId = null\n                            if (id != null) vm.deleteChat(id)\n                        }\n                    ) { Text("削除") }\n                },\n                dismissButton = {\n                    TextButton(onClick = { pendingDeleteChatId = null }) { Text("キャンセル") }\n                }\n            )\n        }\n\n        ModalNavigationDrawer(\n'''
    text = replace_once(text, modal_anchor, modal_with_dialog, "delete confirmation dialog")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_database()
    patch_view_model()
    patch_ui()
    print("Applied CHAT_DELETE_V026: per-chat history delete with confirmation; long-term Memory is preserved")


if __name__ == "__main__":
    main()
