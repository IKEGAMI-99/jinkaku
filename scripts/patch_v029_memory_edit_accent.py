from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_database() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/data/JinkakuDatabase.kt")
    text = path.read_text(encoding="utf-8")
    if "MEMORY_EDIT_DELETE_V029" in text:
        print("Database memory edit/delete already applied")
        return

    anchor = '''    fun touchMemories(ids: List<Long>) {\n'''
    insertion = '''    // MEMORY_EDIT_DELETE_V029\n    fun updateMemory(\n        id: Long,\n        content: String,\n        type: String,\n        importance: Int,\n        confidence: Int,\n        tags: String,\n        embedding: FloatArray\n    ): Int {\n        val v = ContentValues().apply {\n            put("content", content)\n            put("type", type)\n            put("importance", importance.coerceIn(0, 3))\n            put("confidence", confidence.coerceIn(0, 2))\n            put("tags", tags)\n            put("embedding", floatsToBlob(embedding))\n            put("updated_at", System.currentTimeMillis())\n        }\n        return writableDatabase.update("memories", v, "id=? AND status='ACTIVE'", arrayOf(id.toString()))\n    }\n\n    fun deleteMemory(id: Long): Int = writableDatabase.delete(\n        "memories",\n        "id=?",\n        arrayOf(id.toString())\n    )\n\n    fun touchMemories(ids: List<Long>) {\n'''
    text = replace_once(text, anchor, insertion, "database memory mutation methods")
    path.write_text(text, encoding="utf-8")


def patch_memory_engine() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ai/MemoryEngine.kt")
    text = path.read_text(encoding="utf-8")
    if "MEMORY_EDIT_DELETE_V029" in text:
        print("MemoryEngine edit method already applied")
        return

    anchor = '''    /** Rebuilds all active vectors with the currently selected embedding engine. */\n'''
    insertion = '''    // MEMORY_EDIT_DELETE_V029: editing text must rebuild the vector immediately,\n    // otherwise retrieval would keep searching for the old meaning.\n    fun updateMemory(\n        id: Long,\n        content: String,\n        type: String,\n        importance: Int,\n        confidence: Int,\n        tags: String\n    ): Boolean {\n        val clean = content.trim().replace(Regex("\\\\s+"), " ")\n        if (clean.length !in 4..700) return false\n        val cleanType = type.trim().uppercase().take(32).ifBlank { "FACT" }\n        val cleanTags = tags.trim().take(500)\n        val vector = documentEmbedding(clean)\n        val updated = db.updateMemory(\n            id = id,\n            content = clean,\n            type = cleanType,\n            importance = importance.coerceIn(0, 3),\n            confidence = confidence.coerceIn(0, 2),\n            tags = cleanTags,\n            embedding = vector\n        ) > 0\n        if (updated) logger?.i("MEMORY", "Memory edited id=$id embedding=${embedding.name}")\n        return updated\n    }\n\n    /** Rebuilds all active vectors with the currently selected embedding engine. */\n'''
    text = replace_once(text, anchor, insertion, "MemoryEngine updateMemory")
    path.write_text(text, encoding="utf-8")


def patch_view_model() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
    text = path.read_text(encoding="utf-8")
    if "MEMORY_EDIT_DELETE_V029" in text:
        print("ViewModel memory edit/delete already applied")
        return

    anchor = '''    fun clearMemories() {\n'''
    insertion = '''    // MEMORY_EDIT_DELETE_V029\n    fun editMemory(\n        record: MemoryRecord,\n        content: String,\n        type: String,\n        importance: Int,\n        confidence: Int,\n        tags: String\n    ) {\n        if (_ui.value.busy || anyModelImporting()) {\n            setError("処理中はMemoryを編集できません")\n            return\n        }\n        val clean = content.trim()\n        if (clean.length !in 4..700) {\n            setError("Memory本文は4〜700文字にしてください")\n            return\n        }\n        viewModelScope.launch {\n            runtimeMutex.withLock {\n                try {\n                    _ui.value = _ui.value.copy(busy = true, runtimeStatus = "MEMORY EDIT")\n                    val updated = withContext(Dispatchers.IO) {\n                        memory.updateMemory(record.id, clean, type, importance, confidence, tags)\n                    }\n                    _ui.value = _ui.value.copy(\n                        busy = false,\n                        runtimeStatus = "IDLE",\n                        notice = if (updated) "Memory #${record.id} を更新しました" else "Memoryを更新できませんでした"\n                    )\n                    refresh()\n                } catch (t: Throwable) {\n                    logger.e("MEMORY", "Memory edit failed id=${record.id}", t)\n                    _ui.value = _ui.value.copy(\n                        busy = false,\n                        runtimeStatus = "ERROR",\n                        error = "Memory編集: ${t.message}"\n                    )\n                }\n            }\n        }\n    }\n\n    fun deleteMemory(record: MemoryRecord) {\n        if (_ui.value.busy || anyModelImporting()) {\n            setError("処理中はMemoryを削除できません")\n            return\n        }\n        val deleted = db.deleteMemory(record.id)\n        refresh()\n        _ui.value = _ui.value.copy(\n            notice = if (deleted > 0) "Memory #${record.id} を削除しました" else "Memoryを削除できませんでした"\n        )\n        logger.w("MEMORY", "Memory deleted id=${record.id} deleted=$deleted")\n    }\n\n    fun clearMemories() {\n'''
    text = replace_once(text, anchor, insertion, "ViewModel memory mutation methods")
    path.write_text(text, encoding="utf-8")


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")
    if "MEMORY_EDIT_DELETE_V029" in text:
        print("UI memory/accent patch already applied")
        return

    # Accent palette helpers.
    anchor = ''')\n\nprivate fun modernTypingLabel(tokens: Int): String = "入力中" + ".".repeat((tokens.mod(3)) + 1)\n'''
    insertion = ''')\n\n// MEMORY_EDIT_DELETE_V029\nprivate data class ModernAccent(\n    val name: String,\n    val lightPrimary: Color,\n    val lightContainer: Color,\n    val darkPrimary: Color,\n    val darkContainer: Color\n)\n\nprivate val ModernAccents = listOf(\n    ModernAccent("Purple", Color(0xFF6B4EFF), Color(0xFFE9E2FF), Color(0xFFC9B8FF), Color(0xFF4934A8)),\n    ModernAccent("Blue", Color(0xFF246BCE), Color(0xFFD9E7FF), Color(0xFFA9C7FF), Color(0xFF184A8C)),\n    ModernAccent("Cyan", Color(0xFF007C91), Color(0xFFC5F1F7), Color(0xFF75D7E6), Color(0xFF005361)),\n    ModernAccent("Green", Color(0xFF2E7D4F), Color(0xFFD3F3DE), Color(0xFF8AD6A7), Color(0xFF205839)),\n    ModernAccent("Orange", Color(0xFFB85C00), Color(0xFFFFE1C2), Color(0xFFFFB86B), Color(0xFF7C3E00)),\n    ModernAccent("Pink", Color(0xFFB34B76), Color(0xFFFFD9E8), Color(0xFFFFAECF), Color(0xFF78324F))\n)\n\nprivate fun modernColorScheme(dark: Boolean, accentName: String): androidx.compose.material3.ColorScheme {\n    val accent = ModernAccents.firstOrNull { it.name == accentName } ?: ModernAccents.first()\n    val base = if (dark) ModernDark else ModernLight\n    return base.copy(\n        primary = if (dark) accent.darkPrimary else accent.lightPrimary,\n        onPrimary = if (dark) Color(0xFF101014) else Color.White,\n        primaryContainer = if (dark) accent.darkContainer else accent.lightContainer,\n        onPrimaryContainer = if (dark) Color.White else Color(0xFF161218)\n    )\n}\n\nprivate fun modernTypingLabel(tokens: Int): String = "入力中" + ".".repeat((tokens.mod(3)) + 1)\n'''
    text = replace_once(text, anchor, insertion, "accent palette helpers")

    # App-level accent state and persistence.
    text = replace_once(
        text,
        '''    var darkMode by remember { mutableStateOf(prefs.getBoolean("dark_mode", false)) }\n''',
        '''    var darkMode by remember { mutableStateOf(prefs.getBoolean("dark_mode", false)) }\n    var accentColor by remember { mutableStateOf(prefs.getString("accent_color", "Purple") ?: "Purple") }\n''',
        "accent state",
    )
    text = replace_once(
        text,
        '''    fun changeDarkMode(enabled: Boolean) {\n        darkMode = enabled\n        prefs.edit().putBoolean("dark_mode", enabled).apply()\n    }\n''',
        '''    fun changeDarkMode(enabled: Boolean) {\n        darkMode = enabled\n        prefs.edit().putBoolean("dark_mode", enabled).apply()\n    }\n\n    fun changeAccentColor(value: String) {\n        val safe = ModernAccents.firstOrNull { it.name == value }?.name ?: "Purple"\n        accentColor = safe\n        prefs.edit().putString("accent_color", safe).apply()\n    }\n''',
        "accent persistence",
    )
    text = replace_once(
        text,
        '''        colorScheme = if (darkMode) ModernDark else ModernLight,\n''',
        '''        colorScheme = modernColorScheme(darkMode, accentColor),\n''',
        "dynamic color scheme",
    )
    text = replace_once(
        text,
        '''                        darkMode = darkMode,\n                        onDarkModeChange = ::changeDarkMode,\n                        share = { file, mime ->\n''',
        '''                        darkMode = darkMode,\n                        onDarkModeChange = ::changeDarkMode,\n                        accentColor = accentColor,\n                        onAccentColorChange = ::changeAccentColor,\n                        share = { file, mime ->\n''',
        "settings accent arguments",
    )

    # Memory screen state.
    text = replace_once(
        text,
        '''    var adding by remember { mutableStateOf(false) }\n    var confirmClear by remember { mutableStateOf(false) }\n''',
        '''    var adding by remember { mutableStateOf(false) }\n    var confirmClear by remember { mutableStateOf(false) }\n    var editingMemory by remember { mutableStateOf<MemoryRecord?>(null) }\n    var deletingMemory by remember { mutableStateOf<MemoryRecord?>(null) }\n    var editContent by remember { mutableStateOf("") }\n    var editType by remember { mutableStateOf("") }\n    var editTags by remember { mutableStateOf("") }\n    var editImportance by remember { mutableStateOf(1f) }\n    var editConfidence by remember { mutableStateOf(1f) }\n''',
        "memory dialog states",
    )

    # Dialogs inserted before list.
    anchor = '''    LazyColumn(\n        modifier = modifier.fillMaxSize(),\n'''
    insertion = '''    val pendingDelete = deletingMemory\n    if (pendingDelete != null) {\n        AlertDialog(\n            onDismissRequest = { deletingMemory = null },\n            title = { Text("Memoryを削除") },\n            text = { Text("Memory #${pendingDelete.id} を削除します。この操作は元に戻せません。") },\n            confirmButton = {\n                Button(onClick = {\n                    deletingMemory = null\n                    vm.deleteMemory(pendingDelete)\n                }) { Text("削除") }\n            },\n            dismissButton = { TextButton(onClick = { deletingMemory = null }) { Text("キャンセル") } }\n        )\n    }\n\n    val pendingEdit = editingMemory\n    if (pendingEdit != null) {\n        AlertDialog(\n            onDismissRequest = { editingMemory = null },\n            title = { Text("Memory #${pendingEdit.id} を編集") },\n            text = {\n                Column(\n                    modifier = Modifier.fillMaxWidth().heightIn(max = 520.dp),\n                    verticalArrangement = Arrangement.spacedBy(10.dp)\n                ) {\n                    OutlinedTextField(\n                        value = editContent,\n                        onValueChange = { editContent = it },\n                        label = { Text("Memory本文") },\n                        minLines = 3,\n                        maxLines = 7,\n                        modifier = Modifier.fillMaxWidth()\n                    )\n                    OutlinedTextField(\n                        value = editType,\n                        onValueChange = { editType = it },\n                        label = { Text("Type") },\n                        singleLine = true,\n                        modifier = Modifier.fillMaxWidth()\n                    )\n                    OutlinedTextField(\n                        value = editTags,\n                        onValueChange = { editTags = it },\n                        label = { Text("Tags") },\n                        singleLine = true,\n                        modifier = Modifier.fillMaxWidth()\n                    )\n                    Text("重要度 ${editImportance.toInt()}/3", style = MaterialTheme.typography.labelMedium)\n                    Slider(\n                        value = editImportance,\n                        onValueChange = { editImportance = it },\n                        valueRange = 0f..3f,\n                        steps = 2\n                    )\n                    Text("Confidence ${editConfidence.toInt()}/2", style = MaterialTheme.typography.labelMedium)\n                    Slider(\n                        value = editConfidence,\n                        onValueChange = { editConfidence = it },\n                        valueRange = 0f..2f,\n                        steps = 1\n                    )\n                    Text(\n                        "本文を変更するとEmbeddingも自動で再生成します。",\n                        style = MaterialTheme.typography.bodySmall,\n                        color = MaterialTheme.colorScheme.onSurfaceVariant\n                    )\n                }\n            },\n            confirmButton = {\n                Button(\n                    onClick = {\n                        editingMemory = null\n                        vm.editMemory(\n                            pendingEdit,\n                            editContent,\n                            editType,\n                            editImportance.toInt(),\n                            editConfidence.toInt(),\n                            editTags\n                        )\n                    },\n                    enabled = editContent.trim().length in 4..700 && !ui.busy\n                ) { Text("保存") }\n            },\n            dismissButton = { TextButton(onClick = { editingMemory = null }) { Text("キャンセル") } }\n        )\n    }\n\n    LazyColumn(\n        modifier = modifier.fillMaxSize(),\n'''
    text = replace_once(text, anchor, insertion, "memory dialogs")

    # Wire card callbacks.
    text = replace_once(
        text,
        '''            items(ui.memories, key = { it.id }) { memory -> ModernMemoryCard(memory) }\n''',
        '''            items(ui.memories, key = { it.id }) { memory ->\n                ModernMemoryCard(\n                    memory = memory,\n                    onEdit = {\n                        editingMemory = memory\n                        editContent = memory.content\n                        editType = memory.type\n                        editTags = memory.tags\n                        editImportance = memory.importance.toFloat()\n                        editConfidence = memory.confidence.toFloat()\n                    },\n                    onDelete = { deletingMemory = memory },\n                    enabled = !ui.busy && !ui.embeddingReindexing\n                )\n            }\n''',
        "memory card callbacks",
    )

    text = replace_once(
        text,
        '''private fun ModernMemoryCard(memory: MemoryRecord) {\n''',
        '''private fun ModernMemoryCard(\n    memory: MemoryRecord,\n    onEdit: () -> Unit,\n    onDelete: () -> Unit,\n    enabled: Boolean\n) {\n''',
        "memory card signature",
    )
    text = replace_once(
        text,
        '''                Text("#${memory.id}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)\n            }\n''',
        '''                Text("#${memory.id}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)\n                IconButton(onClick = onEdit, enabled = enabled) {\n                    Icon(Icons.Rounded.Edit, contentDescription = "Memoryを編集", modifier = Modifier.size(19.dp))\n                }\n                IconButton(onClick = onDelete, enabled = enabled) {\n                    Icon(Icons.Rounded.DeleteOutline, contentDescription = "Memoryを削除", modifier = Modifier.size(19.dp))\n                }\n            }\n''',
        "memory card action buttons",
    )

    # Settings signature + accent controls.
    text = replace_once(
        text,
        '''    darkMode: Boolean,\n    onDarkModeChange: (Boolean) -> Unit,\n    share: (java.io.File, String) -> Unit\n''',
        '''    darkMode: Boolean,\n    onDarkModeChange: (Boolean) -> Unit,\n    accentColor: String,\n    onAccentColorChange: (String) -> Unit,\n    share: (java.io.File, String) -> Unit\n''',
        "settings signature accent",
    )

    anchor = '''        item { ModernSectionTitle("Persona", Icons.Rounded.Psychology) }\n'''
    insertion = '''        item { ModernSectionTitle("アクセントカラー", Icons.Rounded.Tune) }\n        item {\n            ModernSettingsCard {\n                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {\n                    Text("UIの強調色", fontWeight = FontWeight.SemiBold)\n                    Text(\n                        "チャットバブル、ボタン、進捗表示などのアクセントを変更します。",\n                        style = MaterialTheme.typography.bodySmall,\n                        color = MaterialTheme.colorScheme.onSurfaceVariant\n                    )\n                    ModernAccents.chunked(3).forEach { row ->\n                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                            row.forEach { accent ->\n                                FilterChip(\n                                    selected = accentColor == accent.name,\n                                    onClick = { onAccentColorChange(accent.name) },\n                                    label = { Text(accent.name) },\n                                    leadingIcon = {\n                                        Surface(\n                                            shape = RoundedCornerShape(999.dp),\n                                            color = if (darkMode) accent.darkPrimary else accent.lightPrimary,\n                                            modifier = Modifier.size(14.dp)\n                                        ) {}\n                                    },\n                                    modifier = Modifier.weight(1f)\n                                )\n                            }\n                        }\n                    }\n                }\n            }\n        }\n\n        item { ModernSectionTitle("Persona", Icons.Rounded.Psychology) }\n'''
    text = replace_once(text, anchor, insertion, "accent settings UI")

    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_database()
    patch_memory_engine()
    patch_view_model()
    patch_ui()
    print("Applied MEMORY_EDIT_DELETE_V029: per-memory edit/delete + persistent accent color presets")


if __name__ == "__main__":
    main()
