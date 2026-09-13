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

    text = one(
        text,
        "    val updateInfo: UpdateInfo? = null\n",
        "    val updateInfo: UpdateInfo? = null,\n"
        "    val updateDownloading: Boolean = false,\n"
        "    val updateDownloadProgress: Float? = null,\n"
        "    val updateReadyToInstall: Boolean = false\n",
        "update UI state",
    )

    update_pattern = re.compile(
        r'''    fun downloadUpdate\(\) \{.*?^    fun installUpdate\(\) \{[^\n]*\}\n''',
        re.S | re.M,
    )
    replacement = '''    // SETTINGS_HELP_UPDATER_V081: app-owned update download with progress + retry.
    fun downloadUpdate() {
        val info = _ui.value.updateInfo ?: run {
            setError("先に更新を確認してください")
            return
        }
        if (_ui.value.updateDownloading) return

        viewModelScope.launch {
            _ui.value = _ui.value.copy(
                updateDownloading = true,
                updateDownloadProgress = 0f,
                updateReadyToInstall = false,
                error = null,
                notice = null
            )
            runCatching {
                updater.download(info) { progress ->
                    _ui.value = _ui.value.copy(updateDownloadProgress = progress)
                }
            }.onSuccess {
                _ui.value = _ui.value.copy(
                    updateDownloading = false,
                    updateDownloadProgress = 1f,
                    updateReadyToInstall = true,
                    notice = "更新APKを取得しました。「インストール」を押してください"
                )
            }.onFailure { error ->
                logger.e("UPDATE", "App-owned update download failed", error)
                _ui.value = _ui.value.copy(
                    updateDownloading = false,
                    updateDownloadProgress = null,
                    updateReadyToInstall = false,
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

    settings_start = text.index("@Composable\nprivate fun ModernSettingsScreen(")
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

    download_button = '''                        OutlinedButton(onClick = vm::downloadUpdate, modifier = Modifier.fillMaxWidth()) {
                            Icon(Icons.Rounded.Download, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("APKを取得")
                        }
'''
    download_replacement = '''                        OutlinedButton(
                            onClick = vm::downloadUpdate,
                            enabled = !ui.updateDownloading,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Icon(Icons.Rounded.Download, null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(6.dp))
                            Text(if (ui.updateDownloading) "ダウンロード中" else "APKを取得")
                        }
'''
    if download_button not in settings:
        raise RuntimeError("update download button anchor not found")
    settings = settings.replace(download_button, download_replacement, 1)

    install_button = '''                    OutlinedButton(onClick = vm::installUpdate, modifier = Modifier.fillMaxWidth()) {
                        Icon(Icons.Rounded.SystemUpdate, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("インストール")
                    }
'''
    install_replacement = '''                    if (ui.updateDownloading || ui.updateDownloadProgress != null) {
                        val progress = ui.updateDownloadProgress
                        if (progress != null) {
                            LinearProgressIndicator(
                                progress = { progress.coerceIn(0f, 1f) },
                                modifier = Modifier.fillMaxWidth()
                            )
                            Text(
                                "${(progress.coerceIn(0f, 1f) * 100).toInt()}%  ·  途中で通信が切れても自動再開します",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        } else {
                            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                            Text(
                                "APKを取得中… サイズ確認後に進捗を表示します",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                    OutlinedButton(
                        onClick = vm::installUpdate,
                        enabled = !ui.updateDownloading,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Rounded.SystemUpdate, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("インストール")
                    }
'''
    if install_button not in settings:
        raise RuntimeError("update install button anchor not found")
    settings = settings.replace(install_button, install_replacement, 1)

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
                "「モデル」カテゴリで E2B LiteRT-LM を選び、ダウンロードするか「端末から読み込み」で gemma-4-E2B-it.litertlm を指定します。JinkakuのメインチャットはE2B LiteRT-LMをGPU + MTPで使います。"
            )
            JinkakuGuideStep(
                "2  Personaを作る",
                "「Persona」カテゴリに性格・口調・呼び方・守ってほしいルールを書いて保存します。重要な指示ほど短く具体的にすると安定します。"
            )
            JinkakuGuideStep(
                "3  Memoryを使う",
                "左メニューの「Memory」で長期記憶を確認できます。「Memory追加」で手動登録も可能です。会話中の情報はMemory機能が整理し、次の会話で必要な記憶だけ参照します。"
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
