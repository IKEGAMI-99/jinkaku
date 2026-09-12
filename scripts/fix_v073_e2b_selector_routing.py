from pathlib import Path

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
MARKER = "E2B_SELECTOR_ROUTING_V073"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = VM.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied")
        return

    # Respect the user's explicit engine choice even while the other model is being
    # imported/replaced. Installation state belongs in send()'s guard, not in the selector.
    old_current = '''    private fun currentMainChatEngine(): String {
        val stored = prefs.getString(KEY_MAIN_CHAT_ENGINE, "E4B") ?: "E4B"
        return when {
            stored == "E2B" && models.isE2BInstalled() -> "E2B"
            stored == "E4B" && models.isE4BInstalled() -> "E4B"
            models.isE2BInstalled() && !models.isE4BInstalled() -> "E2B"
            models.isE4BInstalled() -> "E4B"
            else -> stored
        }
    }
'''
    new_current = f'''    // {MARKER}: explicit selection must not bounce back because an import is in progress.
    private fun currentMainChatEngine(): String {{
        val stored = prefs.getString(KEY_MAIN_CHAT_ENGINE, null)
        if (stored == "E2B" || stored == "E4B") return stored
        return if (models.isE2BInstalled() && !models.isE4BInstalled()) "E2B" else "E4B"
    }}
'''
    text = one(text, old_current, new_current, "main engine preference")

    old_setter = '''    fun setMainChatEngine(value: String) {
        if (_ui.value.busy || anyModelImporting()) return
        val engine = if (value.uppercase() == "E2B") "E2B" else "E4B"
'''
    new_setter = '''    fun setMainChatEngine(value: String) {
        if (_ui.value.busy) {
            logger.w("MODEL", "Main chat engine switch blocked while generation is busy")
            setError("生成中はメインチャットAIを切り替えられません")
            return
        }
        val engine = if (value.uppercase() == "E2B") "E2B" else "E4B"
'''
    text = one(text, old_setter, new_setter, "selector busy guard")

    # The UI has dedicated pickers, but keep a second routing layer at the ViewModel
    # boundary. A .litertlm file must never reach the GGUF validator again.
    import_anchor = "    fun importE4B(uri: Uri) {\n"
    if import_anchor not in text:
        raise RuntimeError("importE4B insertion anchor not found")

    helper = '''    private fun selectedImportName(uri: Uri): String {
        return runCatching {
            getApplication<Application>().contentResolver.query(
                uri,
                arrayOf(android.provider.OpenableColumns.DISPLAY_NAME),
                null,
                null,
                null
            )?.use { cursor ->
                if (!cursor.moveToFirst()) return@use null
                val index = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
                if (index >= 0) cursor.getString(index) else null
            }
        }.getOrNull() ?: uri.lastPathSegment.orEmpty()
    }

'''
    text = text.replace(import_anchor, helper + import_anchor, 1)

    old_e4b = '''    fun importE4B(uri: Uri) {
        if (_ui.value.busy || anyModelImporting()) { setError("別の処理が実行中です"); return }
'''
    new_e4b = '''    fun importE4B(uri: Uri) {
        val selectedName = selectedImportName(uri)
        if (selectedName.endsWith(".litertlm", ignoreCase = true)) {
            logger.w("MODEL", "Import router E4B->E2B source=$selectedName")
            prefs.edit().putString(KEY_MAIN_CHAT_ENGINE, "E2B").apply()
            importE2B(uri)
            return
        }
        logger.i("MODEL", "Import request route=E4B source=$selectedName")
        if (_ui.value.busy || anyModelImporting()) { setError("別の処理が実行中です"); return }
'''
    text = one(text, old_e4b, new_e4b, "E4B defensive import router")

    old_e2b = '''    fun importE2B(uri: Uri) {
        if (_ui.value.busy || anyModelImporting()) { setError("別の処理が実行中です"); return }
'''
    new_e2b = '''    fun importE2B(uri: Uri) {
        val selectedName = selectedImportName(uri)
        logger.i("MODEL", "Import request route=E2B source=$selectedName")
        if (_ui.value.busy || anyModelImporting()) { setError("別の処理が実行中です"); return }
'''
    text = one(text, old_e2b, new_e2b, "E2B import diagnostics")

    # Keep UI state immediately in sync with the tap. refresh() may run while a model file
    # is being replaced, so write the explicit choice into UiState as well.
    old_notice = '''        _ui.value = _ui.value.copy(
            runtimeStatus = "IDLE",
            notice = if (engine == "E2B")
'''
    new_notice = '''        _ui.value = _ui.value.copy(
            mainChatEngine = engine,
            runtimeStatus = "IDLE",
            notice = if (engine == "E2B")
'''
    text = one(text, old_notice, new_notice, "selector immediate UI state")

    VM.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER}: responsive selector + defensive LiteRT import routing")


if __name__ == "__main__":
    main()
