from pathlib import Path


def main() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "VIVID_MIX_V043" in text:
        print("VIVID_MIX_V043 already applied")
        return
    if "BRAND_FINISH_V042" not in text:
        raise RuntimeError("v042 must run before v043")

    start = text.index("private val ModernAccents = listOf(")
    end = text.index("private fun modernTypingLabel", start)

    block = '''private val ModernAccents = listOf(
    ModernAccent("Purple", Color(0xFF7A3CFF), Color(0xFF5E2ED6), Color(0xFF8E5CFF), Color(0xFF6034D9)),
    ModernAccent("Blue", Color(0xFF1268FF), Color(0xFF164FD1), Color(0xFF2D7DFF), Color(0xFF1857DE)),
    ModernAccent("Cyan", Color(0xFF00A4C7), Color(0xFF007EA8), Color(0xFF00B6D9), Color(0xFF0089B2)),
    ModernAccent("Green", Color(0xFF00A96B), Color(0xFF087F59), Color(0xFF18B878), Color(0xFF0B8B61)),
    ModernAccent("Orange", Color(0xFFF87420), Color(0xFFD65412), Color(0xFFFF8433), Color(0xFFD95F17)),
    ModernAccent("Pink", Color(0xFFF43F8B), Color(0xFFD32878), Color(0xFFFF559B), Color(0xFFD72F7B))
)

// VIVID_MIX_V043: saturated mixed accent roles instead of pastel Material containers.
private fun modernColorScheme(dark: Boolean, accentName: String): androidx.compose.material3.ColorScheme {
    val accent = ModernAccents.firstOrNull { it.name == accentName } ?: ModernAccents.first()
    val base = if (dark) ModernDark else ModernLight
    val primary = if (dark) accent.darkPrimary else accent.lightPrimary
    val container = if (dark) accent.darkContainer else accent.lightContainer
    val secondary = when (accent.name) {
        "Purple" -> Color(0xFF00BFEA)
        "Blue" -> Color(0xFF00BFEA)
        "Cyan" -> Color(0xFF2979FF)
        "Green" -> Color(0xFF00BFAF)
        "Orange" -> Color(0xFFFF3D8D)
        "Pink" -> Color(0xFF7B4DFF)
        else -> Color(0xFF00BFEA)
    }
    val tertiary = when (accent.name) {
        "Purple" -> Color(0xFFFF3DAF)
        "Blue" -> Color(0xFF7B4DFF)
        "Cyan" -> Color(0xFF00C98B)
        "Green" -> Color(0xFF79C92D)
        "Orange" -> Color(0xFFFFB000)
        "Pink" -> Color(0xFF00BFEA)
        else -> Color(0xFFFF3DAF)
    }
    return base.copy(
        primary = primary,
        onPrimary = Color.White,
        primaryContainer = container,
        onPrimaryContainer = Color.White,
        secondary = secondary,
        onSecondary = Color.White,
        secondaryContainer = secondary.copy(alpha = if (dark) 0.82f else 0.92f),
        onSecondaryContainer = Color.White,
        tertiary = tertiary,
        onTertiary = Color.White,
        tertiaryContainer = tertiary.copy(alpha = if (dark) 0.80f else 0.90f),
        onTertiaryContainer = Color.White,
        surfaceTint = primary,
        inversePrimary = primary,
        onBackground = if (dark) Color.White else base.onBackground,
        onSurface = if (dark) Color.White else base.onSurface,
        onSurfaceVariant = if (dark) Color(0xFFE7E9F2) else Color(0xFF34323A)
    )
}

'''
    text = text[:start] + block + text[end:]

    replacements = [
        ("Color(0xFF07131F)", "Color(0xFF07182A)"),
        ("Color(0xFF101426)", "Color(0xFF151632)"),
        ("Color(0xFF1B0C24)", "Color(0xFF260F2E)"),
        ("Color(0xFFE8F8FF)", "Color(0xFFD7F4FF)"),
        ("Color(0xFFF4F1FF)", "Color(0xFFE3DEFF)"),
        ("Color(0xFFFFF0FA)", "Color(0xFFFFD8EB)"),
        ("MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.34f else 0.25f)", "MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.42f else 0.32f)"),
        ("Color(0xFF22D6E8).copy(alpha = if (darkMode) 0.28f else 0.20f)", "Color(0xFF18D8F0).copy(alpha = if (darkMode) 0.36f else 0.28f)"),
        ("Color(0xFF725CFF).copy(alpha = if (darkMode) 0.34f else 0.24f)", "Color(0xFF7657FF).copy(alpha = if (darkMode) 0.40f else 0.30f)"),
        ("Color(0xFFFF4FA3).copy(alpha = if (darkMode) 0.22f else 0.16f)", "Color(0xFFFF3F9A).copy(alpha = if (darkMode) 0.30f else 0.24f)"),
    ]
    for old, new in replacements:
        if old not in text:
            raise RuntimeError(f"v043 color anchor not found: {old}")
        text = text.replace(old, new, 1)

    path.write_text(text, encoding="utf-8")
    print("Applied VIVID_MIX_V043: richer mixed accents + stronger aurora")


if __name__ == "__main__":
    main()
