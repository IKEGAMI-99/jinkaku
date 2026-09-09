from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def replace_range(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    try:
        start = text.index(start_marker)
        end = text.index(end_marker, start)
    except ValueError as exc:
        raise RuntimeError(f"range anchor not found: {label}") from exc
    return text[:start] + replacement + text[end:]


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "UI_REFINEMENT_V047" in text:
        print("UI_REFINEMENT_V047 already applied")
        return
    if "FINISH_V046" not in text:
        raise RuntimeError("v046 finish patch must run before v047")

    accent_block = '''// UI_REFINEMENT_V047: complementary two-colour accent presets.\nprivate data class ModernAccent(\n    val name: String,\n    val label: String,\n    val lightPrimary: Color,\n    val lightContainer: Color,\n    val darkPrimary: Color,\n    val darkContainer: Color,\n    val lightSecondary: Color,\n    val lightSecondaryContainer: Color,\n    val darkSecondary: Color,\n    val darkSecondaryContainer: Color,\n    val tertiary: Color\n)\n\nprivate val ModernAccents = listOf(\n    ModernAccent("Purple", "Purple × Lime", Color(0xFF7A3CFF), Color(0xFF6034D9), Color(0xFFA77CFF), Color(0xFF4C2D91), Color(0xFF78B800), Color(0xFFD7F5A4), Color(0xFFA6D94E), Color(0xFF3D5C16), Color(0xFF00B8D8)),\n    ModernAccent("Blue", "Blue × Orange", Color(0xFF1967FF), Color(0xFF164FD1), Color(0xFF5B95FF), Color(0xFF173E80), Color(0xFFFF8A00), Color(0xFFFFD7A3), Color(0xFFFFB14B), Color(0xFF6E430F), Color(0xFF8A4DFF)),\n    ModernAccent("Cyan", "Cyan × Coral", Color(0xFF00A8C6), Color(0xFF007E98), Color(0xFF45CBE0), Color(0xFF155769), Color(0xFFF04C3E), Color(0xFFFFC7C1), Color(0xFFFF7A6D), Color(0xFF702B25), Color(0xFFFFB000)),\n    ModernAccent("Green", "Green × Magenta", Color(0xFF00A96B), Color(0xFF087F59), Color(0xFF50D197), Color(0xFF1C5B46), Color(0xFFE83E9B), Color(0xFFFFC3E2), Color(0xFFFF6DB4), Color(0xFF70294E), Color(0xFF3D7BFF)),\n    ModernAccent("Orange", "Orange × Azure", Color(0xFFF26A1B), Color(0xFFD65412), Color(0xFFFF9A5B), Color(0xFF703618), Color(0xFF1C78FF), Color(0xFFC7DDFF), Color(0xFF66A4FF), Color(0xFF214A82), Color(0xFFE34BCB)),\n    ModernAccent("Pink", "Pink × Teal", Color(0xFFF43F8B), Color(0xFFD32878), Color(0xFFFF79AE), Color(0xFF702D4E), Color(0xFF00A88F), Color(0xFFB9F0E6), Color(0xFF43C8AE), Color(0xFF185D52), Color(0xFF8C5BFF))\n)\n\nprivate fun modernColorScheme(dark: Boolean, accentName: String): androidx.compose.material3.ColorScheme {\n    val accent = ModernAccents.firstOrNull { it.name == accentName } ?: ModernAccents.first()\n    val base = if (dark) ModernDark else ModernLight\n    val primary = if (dark) accent.darkPrimary else accent.lightPrimary\n    val primaryContainer = if (dark) accent.darkContainer else accent.lightContainer\n    val secondary = if (dark) accent.darkSecondary else accent.lightSecondary\n    val secondaryContainer = if (dark) accent.darkSecondaryContainer else accent.lightSecondaryContainer\n    return base.copy(\n        primary = primary,\n        onPrimary = Color.White,\n        primaryContainer = primaryContainer,\n        onPrimaryContainer = Color.White,\n        secondary = secondary,\n        onSecondary = if (dark) Color(0xFF101318) else Color(0xFF151515),\n        secondaryContainer = secondaryContainer,\n        onSecondaryContainer = if (dark) Color.White else Color(0xFF151515),\n        tertiary = accent.tertiary,\n        onTertiary = Color.White,\n        tertiaryContainer = accent.tertiary.copy(alpha = if (dark) 0.48f else 0.30f),\n        onTertiaryContainer = if (dark) Color.White else Color(0xFF17151C),\n        surfaceTint = primary,\n        inversePrimary = primary,\n        onBackground = if (dark) Color.White else base.onBackground,\n        onSurface = if (dark) Color.White else base.onSurface,\n        onSurfaceVariant = if (dark) Color(0xFFE7E9F2) else Color(0xFF34323A)\n    )\n}\n\n'''
    text = replace_range(text, "private data class ModernAccent(", "private fun modernTypingLabel", accent_block, "accent pair model + scheme")

    text = replace_once(
        text,
        '''                    TopAppBar(\n                        colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent),\n''',
        '''                    TopAppBar(\n                        modifier = Modifier.background(\n                            Brush.horizontalGradient(\n                                listOf(\n                                    Color(0xFF06101E).copy(alpha = if (darkMode) 0.78f else 0.56f),\n                                    MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.54f else 0.46f),\n                                    MaterialTheme.colorScheme.secondary.copy(alpha = if (darkMode) 0.48f else 0.40f),\n                                    Color(0xFF06101E).copy(alpha = if (darkMode) 0.78f else 0.56f)\n                                )\n                            )\n                        ),\n                        colors = TopAppBarDefaults.topAppBarColors(\n                            containerColor = Color.Transparent,\n                            navigationIconContentColor = Color.White,\n                            titleContentColor = Color.White,\n                            actionIconContentColor = Color.White\n                        ),\n''',
        "full-width header band",
    )

    text = replace_once(
        text,
        '''                                // FINISH_V046: translucent contrast band keeps the wordmark readable\n                                // over both the bright and dark aurora backgrounds.\n                                Surface(\n                                    shape = RoundedCornerShape(12.dp),\n                                    color = Color(0xFF06101E).copy(alpha = if (darkMode) 0.46f else 0.24f),\n                                    tonalElevation = 0.dp\n                                ) {\n                                    Box(\n                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),\n                                        contentAlignment = Alignment.CenterStart\n                                    ) {\n                                        if (wordmarkBitmap != null) {\n                                            Image(\n                                                bitmap = wordmarkBitmap!!,\n                                                contentDescription = "Jinkaku",\n                                                modifier = Modifier.width(142.dp).height(23.dp)\n                                            )\n                                        } else {\n                                            Text("JINKAKU", fontWeight = FontWeight.Bold, color = Color.White)\n                                        }\n                                    }\n                                }\n''',
        '''                                // UI_REFINEMENT_V047: the whole app bar supplies the contrast band.\n                                if (wordmarkBitmap != null) {\n                                    Image(\n                                        bitmap = wordmarkBitmap!!,\n                                        contentDescription = "Jinkaku",\n                                        modifier = Modifier.width(142.dp).height(23.dp)\n                                    )\n                                } else {\n                                    Text("JINKAKU", fontWeight = FontWeight.Bold, color = Color.White)\n                                }\n''',
        "remove local wordmark band",
    )

    text = replace_once(
        text,
        '''                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                                    StatusDot(ui.busy)\n                                    Text(\n                                        "$statusText  ·  Memory ${ui.memoryCount}",\n                                        style = MaterialTheme.typography.labelMedium,\n                                        color = MaterialTheme.colorScheme.onSurfaceVariant\n                                    )\n                                }\n''',
        "",
        "remove header status/memory line",
    )

    text = replace_once(text, "ModernAccents.chunked(3).forEach { row ->", "ModernAccents.chunked(2).forEach { row ->", "two-column accent presets")
    text = replace_once(text, 'Text("UIの強調色", fontWeight = FontWeight.SemiBold)', 'Text("2色アクセント", fontWeight = FontWeight.SemiBold)', "accent heading")
    text = replace_once(text, '"チャットバブル、ボタン、進捗表示などのアクセントを変更します。"', '"反対色の2色をセットで切り替えます。UI全体に2色を分散して使います。"', "accent description")
    text = replace_once(
        text,
        '''                                    label = { Text(accent.name) },\n                                    leadingIcon = {\n                                        Surface(\n                                            shape = RoundedCornerShape(999.dp),\n                                            color = if (darkMode) accent.darkPrimary else accent.lightPrimary,\n                                            modifier = Modifier.size(14.dp)\n                                        ) {}\n                                    },\n''',
        '''                                    label = { Text(accent.label, maxLines = 1) },\n                                    leadingIcon = {\n                                        Row(horizontalArrangement = Arrangement.spacedBy(2.dp)) {\n                                            Surface(\n                                                shape = RoundedCornerShape(999.dp),\n                                                color = if (darkMode) accent.darkPrimary else accent.lightPrimary,\n                                                modifier = Modifier.size(10.dp)\n                                            ) {}\n                                            Surface(\n                                                shape = RoundedCornerShape(999.dp),\n                                                color = if (darkMode) accent.darkSecondary else accent.lightSecondary,\n                                                modifier = Modifier.size(10.dp)\n                                            ) {}\n                                        }\n                                    },\n''',
        "dual colour swatches",
    )

    text = replace_once(text, '''                title = "Gemma 4 E4B HauhauCS",\n                subtitle = "Main chat model · GGUF",\n''', '''                title = "Gemma 4 E4B HauhauCS",\n                subtitle = "Main chat model · GGUF",\n                modelIcon = Icons.Rounded.Psychology,\n                iconColor = MaterialTheme.colorScheme.primary,\n''', "E4B model icon")
    text = replace_once(text, '''                title = "Gemma 4 E2B LiteRT-LM",\n                subtitle = "Memory maintenance model",\n''', '''                title = "Gemma 4 E2B LiteRT-LM",\n                subtitle = "Memory maintenance model",\n                modelIcon = Icons.Rounded.Memory,\n                iconColor = MaterialTheme.colorScheme.secondary,\n''', "E2B model icon")
    text = replace_once(text, '''                title = "EmbeddingGemma 300M Q4_0",\n                subtitle = "Memory retrieval · 約278MB",\n''', '''                title = "EmbeddingGemma 300M Q4_0",\n                subtitle = "Memory retrieval · 約278MB",\n                modelIcon = Icons.Rounded.Storage,\n                iconColor = MaterialTheme.colorScheme.tertiary,\n''', "embedding model icon")
    text = replace_once(text, '''private fun ModernModelCard(\n    title: String,\n    subtitle: String,\n    installed: Boolean,\n''', '''private fun ModernModelCard(\n    title: String,\n    subtitle: String,\n    modelIcon: androidx.compose.ui.graphics.vector.ImageVector,\n    iconColor: Color,\n    installed: Boolean,\n''', "model card parameters")
    text = replace_once(
        text,
        '''                Surface(shape = RoundedCornerShape(14.dp), color = MaterialTheme.colorScheme.secondaryContainer, modifier = Modifier.size(42.dp)) {\n                    Box(contentAlignment = Alignment.Center) { Icon(Icons.Rounded.Storage, null, tint = MaterialTheme.colorScheme.secondary) }\n                }\n''',
        '''                Surface(\n                    shape = RoundedCornerShape(14.dp),\n                    color = iconColor.copy(alpha = 0.20f),\n                    modifier = Modifier.size(42.dp)\n                ) {\n                    Box(contentAlignment = Alignment.Center) { Icon(modelIcon, null, tint = iconColor) }\n                }\n''',
        "model card coloured icon",
    )

    compact_context = '''@Composable\nprivate fun ModernContextCard(telemetry: InferenceTelemetryState, configuredContext: Int, modifier: Modifier = Modifier) {\n    val max = if (telemetry.contextMax > 0) telemetry.contextMax else configuredContext\n    val used = if (telemetry.contextMax > 0) telemetry.contextUsed.coerceIn(0, max) else 0\n    val fraction = if (max > 0) used.toFloat() / max else 0f\n\n    Surface(\n        modifier = modifier.fillMaxWidth(),\n        shape = RoundedCornerShape(14.dp),\n        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.40f)\n    ) {\n        Row(\n            Modifier.fillMaxWidth().padding(horizontal = 11.dp, vertical = 7.dp),\n            verticalAlignment = Alignment.CenterVertically,\n            horizontalArrangement = Arrangement.spacedBy(8.dp)\n        ) {\n            Text("CTX", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)\n            LinearProgressIndicator(\n                progress = { fraction.coerceIn(0f, 1f) },\n                modifier = Modifier.weight(1f).height(4.dp).clip(RoundedCornerShape(999.dp))\n            )\n            Text("$used / $max", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)\n        }\n    }\n}\n\n'''
    text = replace_range(text, "@Composable\nprivate fun ModernContextCard(", "@Composable\nprivate fun ModernMemoryScreen(", compact_context, "compact context meter")
    text = replace_once(text, "ModernContextCard(telemetry, ui.contextSize.toInt(), Modifier.padding(horizontal = 14.dp, vertical = 8.dp))", "ModernContextCard(telemetry, ui.contextSize.toInt(), Modifier.padding(horizontal = 14.dp, vertical = 4.dp))", "compact context outer padding")

    text = replace_once(
        text,
        '''                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {\n                    Text("Context window", fontWeight = FontWeight.SemiBold)\n                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                        listOf(1024L, 2048L, 4096L, 8192L).forEach { size ->\n                            FilterChip(\n                                selected = ui.contextSize == size,\n                                onClick = { vm.setContext(size) },\n                                label = { Text("${size / 1024}K") }\n                            )\n                        }\n                    }\n                    Text("CoTは有効で非表示。回答本文はDecode完了後に一括表示します。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)\n                }\n''',
        '''                Row(\n                    modifier = Modifier.fillMaxWidth(),\n                    verticalAlignment = Alignment.CenterVertically,\n                    horizontalArrangement = Arrangement.spacedBy(5.dp)\n                ) {\n                    Text("Context", fontWeight = FontWeight.SemiBold)\n                    Spacer(Modifier.weight(1f))\n                    listOf(1024L, 2048L, 4096L, 8192L).forEach { size ->\n                        FilterChip(\n                            selected = ui.contextSize == size,\n                            onClick = { vm.setContext(size) },\n                            label = { Text("${size / 1024}K") }\n                        )\n                    }\n                }\n''',
        "compact settings context selector",
    )

    path.write_text(text, encoding="utf-8")
    print("Applied UI_REFINEMENT_V047: dual accents, distinct models, compact context, full-width header")


def main() -> None:
    patch_ui()


if __name__ == "__main__":
    main()
