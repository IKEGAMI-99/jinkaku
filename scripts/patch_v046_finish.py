from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "FINISH_V046" in text:
        print("FINISH_V046 UI already applied")
        return
    if "VIVID_MIX_V043" not in text or "WORDMARK_PNG_V041" not in text:
        raise RuntimeError("v041/v043 must run before v046")

    if "import androidx.compose.foundation.layout.calculateTopPadding\n" not in text:
        text = replace_once(
            text,
            "import androidx.compose.foundation.layout.PaddingValues\n",
            "import androidx.compose.foundation.layout.PaddingValues\nimport androidx.compose.foundation.layout.calculateTopPadding\n",
            "calculateTopPadding import",
        )

    start = text.index("// VIVID_MIX_V043: saturated mixed accent roles instead of pastel Material containers.")
    end = text.index("private fun modernTypingLabel", start)
    scheme = '''// VIVID_MIX_V043: saturated mixed accent roles instead of pastel Material containers.
// FINISH_V046: every interactive Material role now follows the selected accent family.
private fun modernColorScheme(dark: Boolean, accentName: String): androidx.compose.material3.ColorScheme {
    val accent = ModernAccents.firstOrNull { it.name == accentName } ?: ModernAccents.first()
    val base = if (dark) ModernDark else ModernLight
    val primary = if (dark) accent.darkPrimary else accent.lightPrimary
    val container = if (dark) accent.darkContainer else accent.lightContainer
    val secondary = when (accent.name) {
        "Purple" -> Color(0xFF9A4DFF)
        "Blue" -> Color(0xFF008DFF)
        "Cyan" -> Color(0xFF00BFD8)
        "Green" -> Color(0xFF00C97C)
        "Orange" -> Color(0xFFFF8A2B)
        "Pink" -> Color(0xFFFF2F83)
        else -> primary
    }
    val tertiary = when (accent.name) {
        "Purple" -> Color(0xFF6C38FF)
        "Blue" -> Color(0xFF315DFF)
        "Cyan" -> Color(0xFF00A4F2)
        "Green" -> Color(0xFF35B95F)
        "Orange" -> Color(0xFFFF5A24)
        "Pink" -> Color(0xFFFF66A8)
        else -> primary
    }
    return base.copy(
        primary = primary,
        onPrimary = Color.White,
        primaryContainer = container,
        onPrimaryContainer = Color.White,
        secondary = secondary,
        onSecondary = Color.White,
        secondaryContainer = container,
        onSecondaryContainer = Color.White,
        tertiary = tertiary,
        onTertiary = Color.White,
        tertiaryContainer = container,
        onTertiaryContainer = Color.White,
        surfaceTint = primary,
        inversePrimary = primary,
        onBackground = if (dark) Color.White else base.onBackground,
        onSurface = if (dark) Color.White else base.onSurface,
        onSurfaceVariant = if (dark) Color(0xFFE7E9F2) else Color(0xFF34323A)
    )
}

'''
    text = text[:start] + scheme + text[end:]

    old_wordmark = '''                                if (wordmarkBitmap != null) {
                                    Image(
                                        bitmap = wordmarkBitmap!!,
                                        contentDescription = "Jinkaku",
                                        modifier = Modifier.width(142.dp).height(23.dp)
                                    )
                                } else {
                                    Text("JINKAKU", fontWeight = FontWeight.Bold)
                                }
'''
    new_wordmark = '''                                // FINISH_V046: translucent contrast band keeps the wordmark readable
                                // over both the bright and dark aurora backgrounds.
                                Surface(
                                    shape = RoundedCornerShape(12.dp),
                                    color = Color(0xFF06101E).copy(alpha = if (darkMode) 0.46f else 0.24f),
                                    tonalElevation = 0.dp
                                ) {
                                    Box(
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                        contentAlignment = Alignment.CenterStart
                                    ) {
                                        if (wordmarkBitmap != null) {
                                            Image(
                                                bitmap = wordmarkBitmap!!,
                                                contentDescription = "Jinkaku",
                                                modifier = Modifier.width(142.dp).height(23.dp)
                                            )
                                        } else {
                                            Text("JINKAKU", fontWeight = FontWeight.Bold, color = Color.White)
                                        }
                                    }
                                }
'''
    text = replace_once(text, old_wordmark, new_wordmark, "wordmark contrast band")

    text = replace_once(
        text,
        "                    ModernScreen.CHAT -> ModernChatScreen(vm, Modifier.padding(padding))\n",
        "                    ModernScreen.CHAT -> ModernChatScreen(vm, Modifier.padding(top = padding.calculateTopPadding()))\n",
        "chat bottom inset ownership",
    )

    old_composer = '''        Surface(
            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.72f),
            contentColor = MaterialTheme.colorScheme.onSurface,
            tonalElevation = 0.dp
        ) {
'''
    new_composer = '''        Surface(
            // FINISH_V046: continuous composer band through the gesture/navigation area.
            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.82f),
            contentColor = MaterialTheme.colorScheme.onSurface,
            tonalElevation = 0.dp,
            modifier = Modifier.fillMaxWidth()
        ) {
'''
    text = replace_once(text, old_composer, new_composer, "continuous composer surface")

    old_update = '''                    if (ui.updateInfo != null) {
                        OutlinedButton(onClick = vm::downloadUpdate, modifier = Modifier.fillMaxWidth()) {
                            Icon(Icons.Rounded.Download, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("APKを取得")
                        }
                    }
                    OutlinedButton(onClick = vm::installUpdate, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Rounded.SystemUpdate, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("インストール")
                    }
'''
    new_update = '''                    if (ui.updateInfo != null) {
                        OutlinedButton(
                            onClick = vm::downloadUpdate,
                            enabled = !ui.updateDownloading,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(Icons.Rounded.Download, null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text(if (ui.updateDownloading) "ダウンロード中" else "APKを取得")
                        }
                        if (ui.updateDownloadProgress != null) {
                            val updateProgress = ui.updateDownloadProgress.coerceIn(0, 100)
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    if (ui.updateDownloading) "ダウンロード $updateProgress%" else "ダウンロード完了 $updateProgress%",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                Spacer(Modifier.weight(1f))
                                Text("$updateProgress%", fontWeight = FontWeight.SemiBold, color = MaterialTheme.colorScheme.primary)
                            }
                            LinearProgressIndicator(
                                progress = { updateProgress / 100f },
                                modifier = Modifier.fillMaxWidth().height(7.dp).clip(RoundedCornerShape(999.dp))
                            )
                        }
                    }
                    OutlinedButton(
                        onClick = vm::installUpdate,
                        enabled = ui.updateDownloadReady,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Rounded.SystemUpdate, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("インストール")
                    }
'''
    text = replace_once(text, old_update, new_update, "update download progress UI")

    path.write_text(text, encoding="utf-8")
    print("Applied FINISH_V046 UI: accent sync, wordmark band, continuous composer, update %")


def patch_viewmodel() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
    text = path.read_text(encoding="utf-8")

    if "updateDownloadProgress" in text:
        print("FINISH_V046 ViewModel already applied")
        return

    text = replace_once(
        text,
        "    val updateInfo: UpdateInfo? = null\n",
        '''    val updateInfo: UpdateInfo? = null,
    val updateDownloadProgress: Int? = null,
    val updateDownloading: Boolean = false,
    val updateDownloadReady: Boolean = false
''',
        "UiState update download fields",
    )

    start = text.index("    private fun refreshDownloads() {")
    end = text.index("\n    fun newChat()", start)
    segment = text[start:end]
    segment = replace_once(
        segment,
        "    private fun refreshDownloads() {\n",
        "    private fun refreshDownloads() {\n        val updateDownload = updater.downloadState()\n",
        "download state query",
    )
    segment = replace_once(
        segment,
        "            embeddingEngineName = memory.embeddingName\n",
        '''            embeddingEngineName = memory.embeddingName,
            updateDownloadProgress = updateDownload?.progressPercent,
            updateDownloading = updateDownload?.downloading == true,
            updateDownloadReady = updateDownload?.complete == true
''',
        "download state copy",
    )
    text = text[:start] + segment + text[end:]

    old_download = '''    fun downloadUpdate() {
        _ui.value.updateInfo?.let {
            updater.download(it)
            _ui.value = _ui.value.copy(notice = "APKをダウンロードしています。完了後に「インストール」を押してください")
        }
    }
'''
    new_download = '''    fun downloadUpdate() {
        _ui.value.updateInfo?.let {
            updater.download(it)
            _ui.value = _ui.value.copy(
                notice = "APKをダウンロードしています",
                updateDownloadProgress = 0,
                updateDownloading = true,
                updateDownloadReady = false
            )
        }
    }
'''
    text = replace_once(text, old_download, new_download, "downloadUpdate state")

    path.write_text(text, encoding="utf-8")
    print("Applied FINISH_V046 ViewModel update progress state")


def patch_updater() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/update/AppUpdater.kt")
    text = path.read_text(encoding="utf-8")

    if "data class UpdateDownloadState" in text:
        print("FINISH_V046 AppUpdater already applied")
        return

    text = replace_once(
        text,
        "data class UpdateInfo(val versionName: String, val versionCode: Int, val apkUrl: String)\n",
        '''data class UpdateInfo(val versionName: String, val versionCode: Int, val apkUrl: String)
data class UpdateDownloadState(
    val progressPercent: Int,
    val downloading: Boolean,
    val complete: Boolean,
    val failed: Boolean
)
''',
        "UpdateDownloadState data class",
    )

    anchor = '''    fun installDownloaded(): Boolean {
'''
    method = '''    fun downloadState(): UpdateDownloadState? {
        val prefs = context.getSharedPreferences("update", Context.MODE_PRIVATE)
        val id = prefs.getLong("id", -1L)
        if (id <= 0L) return null

        val manager = context.getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
        val cursor = manager.query(DownloadManager.Query().setFilterById(id)) ?: return null
        cursor.use { c ->
            if (!c.moveToFirst()) return null
            val status = c.getInt(c.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
            val downloaded = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
            val total = c.getLong(c.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
            val complete = status == DownloadManager.STATUS_SUCCESSFUL
            val failed = status == DownloadManager.STATUS_FAILED
            val downloading = status == DownloadManager.STATUS_PENDING ||
                status == DownloadManager.STATUS_RUNNING ||
                status == DownloadManager.STATUS_PAUSED
            val percent = when {
                complete -> 100
                total > 0L -> ((downloaded * 100L) / total).toInt().coerceIn(0, 99)
                else -> 0
            }
            return UpdateDownloadState(
                progressPercent = percent,
                downloading = downloading,
                complete = complete,
                failed = failed
            )
        }
    }

'''
    text = replace_once(text, anchor, method + anchor, "DownloadManager progress query")

    path.write_text(text, encoding="utf-8")
    print("Applied FINISH_V046 AppUpdater DownloadManager progress query")


def main() -> None:
    patch_ui()
    patch_viewmodel()
    patch_updater()


if __name__ == "__main__":
    main()
