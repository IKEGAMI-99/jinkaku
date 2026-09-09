from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "BRIGHT_ACCENT_V051" in text:
        print("BRIGHT_ACCENT_V051 already applied")
        return
    if "EDGE_GLOSS_V050" not in text:
        raise RuntimeError("v050 edge gloss patch must run before v051")

    # BRIGHT_ACCENT_V051: use the same bright pair in dark mode as in light mode.
    old_scheme = '''    val primary = if (dark) accent.darkPrimary else accent.lightPrimary\n    val primaryContainer = if (dark) accent.darkContainer else accent.lightContainer\n    val secondary = if (dark) accent.darkSecondary else accent.lightSecondary\n    val secondaryContainer = if (dark) accent.darkSecondaryContainer else accent.lightSecondaryContainer\n'''
    new_scheme = '''    // BRIGHT_ACCENT_V051: dark mode no longer switches to muted accent variants.\n    val primary = accent.lightPrimary\n    val primaryContainer = accent.lightContainer\n    val secondary = accent.lightSecondary\n    val secondaryContainer = accent.lightSecondaryContainer\n'''
    text = replace_once(text, old_scheme, new_scheme, "bright accent scheme")

    text = replace_once(
        text,
        "color = if (darkMode) accent.darkPrimary else accent.lightPrimary,",
        "color = accent.lightPrimary,",
        "bright primary swatch",
    )
    text = replace_once(
        text,
        "color = if (darkMode) accent.darkSecondary else accent.lightSecondary,",
        "color = accent.lightSecondary,",
        "bright secondary swatch",
    )

    # Remove the pill/background band behind the compact context readout.
    text = replace_once(
        text,
        "color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.40f)",
        "color = Color.Transparent",
        "transparent context background",
    )

    # Replace the wide + New button with a compact sparkling plus icon.
    start_marker = '''                                FilledTonalButton(\n                                    onClick = { dismissIme(); vm.newChat() },\n'''
    end_marker = '''                            }\n                            IconButton(onClick = {\n'''
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError("anchor not found: new chat button start")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError("anchor not found: new chat button end")

    new_button = '''                                FilledIconButton(\n                                    onClick = { dismissIme(); vm.newChat() },\n                                    modifier = Modifier.padding(end = 8.dp).size(48.dp),\n                                    colors = androidx.compose.material3.IconButtonDefaults.filledIconButtonColors(\n                                        containerColor = MaterialTheme.colorScheme.primary,\n                                        contentColor = Color.White\n                                    )\n                                ) {\n                                    Box(Modifier.size(30.dp), contentAlignment = Alignment.Center) {\n                                        Icon(\n                                            Icons.Rounded.Add,\n                                            contentDescription = "新規チャット",\n                                            modifier = Modifier.size(24.dp)\n                                        )\n                                        Text(\n                                            "✦",\n                                            modifier = Modifier.align(Alignment.TopEnd),\n                                            color = MaterialTheme.colorScheme.secondary,\n                                            style = MaterialTheme.typography.labelSmall,\n                                            fontWeight = FontWeight.Black\n                                        )\n                                    }\n                                }\n'''
    text = text[:start] + new_button + text[end:]

    path.write_text(text, encoding="utf-8")
    print("Applied BRIGHT_ACCENT_V051: bright dark-mode accents + no context band + sparkle add button")


if __name__ == "__main__":
    patch_ui()
