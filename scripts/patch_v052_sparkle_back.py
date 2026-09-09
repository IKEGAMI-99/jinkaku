from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "SPARKLE_BACK_V052" in text:
        print("SPARKLE_BACK_V052 already applied")
        return
    if "BRIGHT_ACCENT_V051" not in text:
        raise RuntimeError("v051 bright accent patch must run before v052")

    # Android back should navigate from Memory/Settings back to Chat instead of
    # finishing the Activity. This keeps system-back behavior consistent with
    # an in-app navigation stack.
    if "import androidx.activity.compose.BackHandler\n" not in text:
        text = replace_once(
            text,
            "import androidx.activity.compose.rememberLauncherForActivityResult\n",
            "import androidx.activity.compose.BackHandler\nimport androidx.activity.compose.rememberLauncherForActivityResult\n",
            "BackHandler import",
        )

    if "import androidx.compose.material.icons.rounded.AutoAwesome\n" not in text:
        text = replace_once(
            text,
            "import androidx.compose.material.icons.rounded.Backup\n",
            "import androidx.compose.material.icons.rounded.AutoAwesome\nimport androidx.compose.material.icons.rounded.Backup\n",
            "AutoAwesome import",
        )

    back_anchor = '''    MaterialTheme(\n        colorScheme = modernColorScheme(darkMode, accentColor),\n'''
    back_insert = '''    // SPARKLE_BACK_V052: system back returns sub-screens to Chat.\n    BackHandler(enabled = screen != ModernScreen.CHAT) {\n        dismissIme()\n        screen = ModernScreen.CHAT\n    }\n\n    MaterialTheme(\n        colorScheme = modernColorScheme(darkMode, accentColor),\n'''
    text = replace_once(text, back_anchor, back_insert, "sub-screen back navigation")

    old_button = '''                                FilledIconButton(\n                                    onClick = { dismissIme(); vm.newChat() },\n                                    modifier = Modifier.padding(end = 8.dp).size(48.dp),\n                                    colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(\n                                        containerColor = MaterialTheme.colorScheme.primary,\n                                        contentColor = Color.White\n                                    )\n                                ) {\n                                    Box(Modifier.size(30.dp), contentAlignment = Alignment.Center) {\n                                        Icon(\n                                            Icons.Rounded.Add,\n                                            contentDescription = "新規チャット",\n                                            modifier = Modifier.size(24.dp)\n                                        )\n                                        Text(\n                                            "✦",\n                                            modifier = Modifier.align(Alignment.TopEnd),\n                                            color = MaterialTheme.colorScheme.secondary,\n                                            style = MaterialTheme.typography.labelSmall,\n                                            fontWeight = FontWeight.Black\n                                        )\n                                    }\n                                }\n'''
    new_button = '''                                FilledIconButton(\n                                    onClick = { dismissIme(); vm.newChat() },\n                                    modifier = Modifier.padding(end = 8.dp).size(48.dp),\n                                    colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(\n                                        containerColor = MaterialTheme.colorScheme.primary,\n                                        contentColor = Color.White\n                                    )\n                                ) {\n                                    Icon(\n                                        Icons.Rounded.AutoAwesome,\n                                        contentDescription = "新規チャット",\n                                        modifier = Modifier.size(27.dp),\n                                        tint = Color.White\n                                    )\n                                }\n'''
    text = replace_once(text, old_button, new_button, "sparkle-only new chat icon")

    path.write_text(text, encoding="utf-8")
    print("Applied SPARKLE_BACK_V052: sparkle-only new chat + sub-screen system back")


if __name__ == "__main__":
    patch_ui()
