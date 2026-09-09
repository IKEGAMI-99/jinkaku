from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "VISUAL_THEME_V031" in text:
        print("VISUAL_THEME_V031 already applied")
        return
    if "MEMORY_EDIT_DELETE_V029" not in text:
        raise RuntimeError("v0.1.29 accent patch must run before VISUAL_THEME_V031")

    text = replace_once(
        text,
        "import androidx.compose.foundation.layout.Arrangement\n",
        "import androidx.compose.foundation.background\nimport androidx.compose.foundation.layout.Arrangement\n",
        "background import",
    )
    text = replace_once(
        text,
        "import androidx.compose.ui.graphics.Color\n",
        "import androidx.compose.ui.graphics.Brush\nimport androidx.compose.ui.graphics.Color\n",
        "brush import",
    )

    old_scheme = '''private fun modernColorScheme(dark: Boolean, accentName: String): androidx.compose.material3.ColorScheme {\n    val accent = ModernAccents.firstOrNull { it.name == accentName } ?: ModernAccents.first()\n    val base = if (dark) ModernDark else ModernLight\n    return base.copy(\n        primary = if (dark) accent.darkPrimary else accent.lightPrimary,\n        onPrimary = if (dark) Color(0xFF101014) else Color.White,\n        primaryContainer = if (dark) accent.darkContainer else accent.lightContainer,\n        onPrimaryContainer = if (dark) Color.White else Color(0xFF161218)\n    )\n}\n'''
    new_scheme = '''// VISUAL_THEME_V031: keep every Material accent role in sync with the selected preset.\nprivate fun modernColorScheme(dark: Boolean, accentName: String): androidx.compose.material3.ColorScheme {\n    val accent = ModernAccents.firstOrNull { it.name == accentName } ?: ModernAccents.first()\n    val base = if (dark) ModernDark else ModernLight\n    val primary = if (dark) accent.darkPrimary else accent.lightPrimary\n    val container = if (dark) accent.darkContainer else accent.lightContainer\n    val onAccent = if (dark) Color(0xFF101014) else Color.White\n    val onContainer = if (dark) Color.White else Color(0xFF161218)\n    return base.copy(\n        primary = primary,\n        onPrimary = onAccent,\n        primaryContainer = container,\n        onPrimaryContainer = onContainer,\n        secondary = primary,\n        onSecondary = onAccent,\n        secondaryContainer = container,\n        onSecondaryContainer = onContainer,\n        tertiary = primary,\n        onTertiary = onAccent,\n        tertiaryContainer = container,\n        onTertiaryContainer = onContainer,\n        surfaceTint = primary,\n        inversePrimary = primary,\n        onBackground = if (dark) Color.White else base.onBackground,\n        onSurface = if (dark) Color.White else base.onSurface,\n        onSurfaceVariant = if (dark) Color(0xFFE0E4E8) else base.onSurfaceVariant\n    )\n}\n'''
    text = replace_once(text, old_scheme, new_scheme, "full accent color scheme")

    old_scaffold = '''            Scaffold(\n                containerColor = MaterialTheme.colorScheme.background,\n'''
    new_scaffold = '''            Scaffold(\n                modifier = Modifier\n                    .fillMaxSize()\n                    .background(MaterialTheme.colorScheme.background)\n                    .background(\n                        Brush.verticalGradient(\n                            colors = listOf(\n                                MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.20f else 0.14f),\n                                Color.Transparent,\n                                MaterialTheme.colorScheme.primaryContainer.copy(alpha = if (darkMode) 0.14f else 0.22f)\n                            )\n                        )\n                    ),\n                containerColor = Color.Transparent,\n                contentColor = MaterialTheme.colorScheme.onBackground,\n'''
    text = replace_once(text, old_scaffold, new_scaffold, "accent-aware background gradient")

    text = replace_once(
        text,
        '''                        colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background),\n''',
        '''                        colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent),\n''',
        "transparent top app bar",
    )

    text = replace_once(
        text,
        '''        Surface(\n            color = MaterialTheme.colorScheme.background,\n            tonalElevation = 2.dp\n        ) {\n''',
        '''        Surface(\n            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.72f),\n            contentColor = MaterialTheme.colorScheme.onSurface,\n            tonalElevation = 0.dp\n        ) {\n''',
        "translucent chat composer",
    )

    # Cards use semi-transparent container colors. Material3 cannot infer a matching
    # content color from a copied color with alpha, so explicitly inherit white/light
    # text through Scaffold and set the most visible settings card to onSurface.
    text = replace_once(
        text,
        '''        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.46f))\n''',
        '''        colors = CardDefaults.cardColors(\n            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.46f),\n            contentColor = MaterialTheme.colorScheme.onSurface\n        )\n''',
        "settings card content color",
    )

    path.write_text(text, encoding="utf-8")
    print("Applied VISUAL_THEME_V031: visible gradient + synchronized accents + readable dark text")


if __name__ == "__main__":
    main()
