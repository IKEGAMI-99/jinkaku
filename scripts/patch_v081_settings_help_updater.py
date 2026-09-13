from pathlib import Path
import re

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
MARKER = "SETTINGS_HELP_UPDATER_V081"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_view_model() -> None:
    text = VM.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to ViewModel")
        return

    # v046 already added Int percentage/downloading/ready fields. Keep that public UI
    # shape, but stop polling the old DownloadManager job because v081 owns the transfer.
    text = one(
        text,
        "        val updateDownload = updater.downloadState()\n",
        "        // SETTINGS_HELP_UPDATER_V081: app-owned transfer; no legacy DownloadManager polling.\n",
        "legacy update download poll",
    )
    old_refresh_fields = '''            embeddingEngineName = memory.embeddingName,
            updateDownloadProgress = updateDownload?.progressPercent,
            updateDownloading = updateDownload?.downloading == true,
            updateDownloadReady = updateDownload?.complete == true
'''
    new_refresh_fields = '''            embeddingEngineName = memory.embeddingName,
            updateDownloadReady = if (_ui.value.updateDownloading) _ui.value.updateDownloadReady else updater.hasDownloadedUpdate()
'''
    text = one(text, old_refresh_fields, new_refresh_fields, "legacy update refresh fields")

    update_pattern = re.compile(
        r'''    fun downloadUpdate\(\) \{.*?^    fun installUpdate\(\) \{[^\n]*\}\n''',
        re.S | re.M,
    )
    replacement = '''    // SETTINGS_HELP_UPDATER_V081: resumable app-owned update download with live progress.
    fun downloadUpdate() {
        val info = _ui.value.updateInfo ?: run {
            setError("先に更新を確認してください")
            return
        }
        if (_ui.value.updateDownloading) return

        viewModelScope.launch {
            _ui.value = _ui.value.copy(
                updateDownloading = true,
                updateDownloadProgress = 0,
                updateDownloadReady = false,
                error = null,
                notice = "更新APKをダウンロードしています"
            )
            runCatching {
                updater.download(info) { progress ->
                    val percent = progress?.let { (it.coerceIn(0f, 1f) * 100f).toInt().coerceIn(0, 99) }
                    _ui.value = _ui.value.copy(updateDownloadProgress = percent)
                }
            }.onSuccess {
                _ui.value = _ui.value.copy(
                    updateDownloading = false,
                    updateDownloadProgress = 100,
                    updateDownloadReady = true,
                    notice = "更新APKを取得しました。「インストール」を押してください"
                )
            }.onFailure { error ->
                logger.e("UPDATE", "App-owned update download failed", error)
                _ui.value = _ui.value.copy(
                    updateDownloading = false,
                    updateDownloadProgress = null,
                    updateDownloadReady = updater.hasDownloadedUpdate(),
                    error = "更新APKの取得に失敗しました: ${error.message ?: "不明なエラー"}"
                )
            }
        }
    }

    fun installUpdate() {
        if (_ui.value.updateDownloading) {
            setError("更新APKをダウンロード中です")
            return
        }
        if (!updater.installDownloaded()) setError("更新APKがまだ見つかりません")
    }
'''
    text, count = update_pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"update actions: expected exactly one block, found {count}")

    VM.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to ViewModel")


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to UI")
        return
    if "SETTINGS_CATEGORIES_V068" not in text:
        raise RuntimeError("categorized Settings UI must exist before v081")

    # Later patches insert their own marker comments between @Composable and the
    # Settings function. Anchor on the function itself so v081 survives those changes.
    settings_start = text.index("private fun ModernSettingsScreen(")
    settings_end = text.index("\n@Composable\nprivate fun ModernSettingsCategoryHeader(", settings_start)
    settings = text[settings_start:settings_end]

    first_category = "        item {\n            ModernSettingsCategoryHeader(\n"
    if first_category not in settings:
        raise RuntimeError("first Settings category anchor not found")
    settings = settings.replace(
        first_category,
        "        item { JinkakuUsageGuide() }\n\n" + first_category,
        1,
    )

    # v046 already renders percentage and disables Install until the APK is complete.
    # Add a small recovery hint so a stalled connection no longer looks terminal.
    settings = settings.replace(
        'if (ui.updateDownloading) "ダウンロード $updateProgress%" else "ダウンロード完了 $updateProgress%",',
        'if (ui.updateDownloading) "ダウンロード $updateProgress%  ·  通信切断時は自動再開" else "ダウンロード完了 $updateProgress%",',
        1,
    )

    text = text[:settings_start] + settings + text[settings_end:]

    guide = r'''
@Composable
private fun JinkakuUsageGuide() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(24.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.58f),
            contentColor = MaterialTheme.colorScheme.onPrimaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(42.dp)
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(Icons.Rounded.Psychology, null, tint = MaterialTheme.colorScheme.onPrimary)
                    }
                }
                Column {
                    Text("使い方", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text(
                        "最初にここだけ読めば動かせます",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.78f)
                    )
                }
            }

            JinkakuGuideStep(
                "1  モデルを入れる",
                "「モデル」カテゴリで E2B LiteRT-LM をダウンロードするか、「端末から読み込み」で gemma-4-E2B-it.litertlm を指定します。メインチャットはE2B LiteRT-LMをGPU + MTPで使います。"
            )
            JinkakuGuideStep(
                "2  Personaを作る",
                "「Persona」カテゴリに性格・口調・呼び方・守ってほしいルールを書いて保存します。重要な指示ほど短く具体的にすると安定します。"
            )
            JinkakuGuideStep(
                "3  Memoryを使う",
                "左メニューの「Memory」で長期記憶を確認できます。「Memory追加」で手動登録も可能です。会話から作られた記憶は、必要なときだけ次の会話へ参照されます。"
            )
            JinkakuGuideStep(
                "4  推論を調整する",
                "「推論」カテゴリで Context、Thinking、Top-K、Top-P、Temperatureを調整します。Thinking ONは回答前に最大512 tokenの推論枠を使います。設定変更は次の生成から反映されます。"
            )
            Text(
                "迷ったら、まずモデル → Persona → そのままチャット。Memoryと推論は後から調整で十分です。",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary
            )
        }
    }
}

@Composable
private fun JinkakuGuideStep(title: String, body: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, fontWeight = FontWeight.SemiBold)
        Text(
            body,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.82f)
        )
    }
}

'''
    text = one(
        text,
        "@Composable\nprivate fun ModernSettingsCategoryHeader(",
        guide + "@Composable\nprivate fun ModernSettingsCategoryHeader(",
        "usage guide composables",
    )

    text = text.replace(
        "private fun JinkakuUsageGuide() {",
        "private fun JinkakuUsageGuide() { // SETTINGS_HELP_UPDATER_V081",
        1,
    )

    UI.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to UI")


def main() -> None:
    patch_view_model()
    patch_ui()
    print(f"Applied {MARKER}: Settings guide + resilient update progress UI")


if __name__ == "__main__":
    main()
