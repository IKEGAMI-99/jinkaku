from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "CANDY_GLASS_V048" in text:
        print("CANDY_GLASS_V048 already applied")
        return
    if "UI_REFINEMENT_V047" not in text:
        raise RuntimeError("v047 UI patch must run before v048")

    if "import androidx.compose.foundation.border\n" not in text:
        text = replace_once(
            text,
            "import androidx.compose.foundation.background\n",
            "import androidx.compose.foundation.background\nimport androidx.compose.foundation.border\n",
            "border import",
        )

    # CANDY_GLASS_V048: more saturated candy-like complementary presets.
    start = text.index("// UI_REFINEMENT_V047: complementary two-colour accent presets.")
    end = text.index("private fun modernColorScheme", start)
    accent_block = '''// UI_REFINEMENT_V047: complementary two-colour accent presets.\n// CANDY_GLASS_V048: higher-chroma candy colors and brighter containers.\nprivate data class ModernAccent(\n    val name: String,\n    val label: String,\n    val lightPrimary: Color,\n    val lightContainer: Color,\n    val darkPrimary: Color,\n    val darkContainer: Color,\n    val lightSecondary: Color,\n    val lightSecondaryContainer: Color,\n    val darkSecondary: Color,\n    val darkSecondaryContainer: Color,\n    val tertiary: Color\n)\n\nprivate val ModernAccents = listOf(\n    ModernAccent("Purple", "Purple × Lime", Color(0xFF8A42FF), Color(0xFF804CFF), Color(0xFFB88CFF), Color(0xFF6A35E6), Color(0xFF8CCB16), Color(0xFF96C928), Color(0xFFB7ED57), Color(0xFF4F780D), Color(0xFF19D7F2)),\n    ModernAccent("Blue", "Blue × Orange", Color(0xFF176CFF), Color(0xFF3174FF), Color(0xFF6FA4FF), Color(0xFF1D5ED6), Color(0xFFFF8B16), Color(0xFFFF9B32), Color(0xFFFFB85C), Color(0xFFA85A08), Color(0xFFB05BFF)),\n    ModernAccent("Cyan", "Cyan × Coral", Color(0xFF00B8D9), Color(0xFF12B6D1), Color(0xFF57E2F4), Color(0xFF087F9C), Color(0xFFFF5147), Color(0xFFFF665A), Color(0xFFFF8A80), Color(0xFFA53A31), Color(0xFFFFC01F)),\n    ModernAccent("Green", "Green × Magenta", Color(0xFF00B978), Color(0xFF19B77A), Color(0xFF63E6AC), Color(0xFF128060), Color(0xFFF43B9E), Color(0xFFF04EA8), Color(0xFFFF79BE), Color(0xFFA62369), Color(0xFF4F86FF)),\n    ModernAccent("Orange", "Orange × Azure", Color(0xFFFF7318), Color(0xFFFF7A2A), Color(0xFFFFA15F), Color(0xFFC64D12), Color(0xFF1888FF), Color(0xFF4193FF), Color(0xFF79B5FF), Color(0xFF245DA6), Color(0xFFF257D4)),\n    ModernAccent("Pink", "Pink × Teal", Color(0xFFFF3F91), Color(0xFFF84F97), Color(0xFFFF7DB1), Color(0xFFC92A73), Color(0xFF00B8A0), Color(0xFF18B8A2), Color(0xFF55DFC8), Color(0xFF08776A), Color(0xFF9B68FF))\n)\n\n'''
    text = text[:start] + accent_block + text[end:]

    # Brighter, cleaner candy aurora. Avoid the grey/brown mud that happened when
    # multiple low-chroma translucent layers stacked over a nearly black base.
    replacements = [
        ("Color(0xFF07182A)", "Color(0xFF071D3A)"),
        ("Color(0xFF151632)", "Color(0xFF20184D)"),
        ("Color(0xFF260F2E)", "Color(0xFF45113D)"),
        ("Color(0xFFD7F4FF)", "Color(0xFFCEF7FF)"),
        ("Color(0xFFE3DEFF)", "Color(0xFFE9DBFF)"),
        ("Color(0xFFFFD8EB)", "Color(0xFFFFD7F0)"),
        ("MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.42f else 0.32f)", "MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.62f else 0.50f)"),
        ("Color(0xFF18D8F0).copy(alpha = if (darkMode) 0.36f else 0.28f)", "Color(0xFF27E7FF).copy(alpha = if (darkMode) 0.56f else 0.44f)"),
        ("Color(0xFF7657FF).copy(alpha = if (darkMode) 0.40f else 0.30f)", "Color(0xFF9A62FF).copy(alpha = if (darkMode) 0.58f else 0.46f)"),
        ("Color(0xFFFF3F9A).copy(alpha = if (darkMode) 0.30f else 0.24f)", "Color(0xFFFF55BE).copy(alpha = if (darkMode) 0.52f else 0.42f)"),
    ]
    for old, new in replacements:
        if old not in text:
            raise RuntimeError(f"candy aurora anchor not found: {old}")
        text = text.replace(old, new, 1)

    # Add a warm peach glow so the background is not only blue/purple/pink.
    pink_layer = '''                    .background(\n                        Brush.radialGradient(\n                            colors = listOf(\n                                Color(0xFFFF55BE).copy(alpha = if (darkMode) 0.52f else 0.42f),\n                                Color.Transparent\n                            ),\n                            center = Offset(1060f, 1720f),\n                            radius = 1600f\n                        )\n                    ),\n'''
    peach_layer = '''                    .background(\n                        Brush.radialGradient(\n                            colors = listOf(\n                                Color(0xFFFF55BE).copy(alpha = if (darkMode) 0.52f else 0.42f),\n                                Color.Transparent\n                            ),\n                            center = Offset(1060f, 1720f),\n                            radius = 1600f\n                        )\n                    )\n                    .background(\n                        Brush.radialGradient(\n                            colors = listOf(\n                                Color(0xFFFFB45F).copy(alpha = if (darkMode) 0.30f else 0.34f),\n                                Color.Transparent\n                            ),\n                            center = Offset(960f, 260f),\n                            radius = 900f\n                        )\n                    ),\n'''
    text = replace_once(text, pink_layer, peach_layer, "peach aurora glow")

    # Replace the opaque/tinted header strip with a translucent liquid-glass layer.
    old_top = '''                        modifier = Modifier.background(\n                            Brush.horizontalGradient(\n                                listOf(\n                                    Color(0xFF06101E).copy(alpha = if (darkMode) 0.78f else 0.56f),\n                                    MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.54f else 0.46f),\n                                    MaterialTheme.colorScheme.secondary.copy(alpha = if (darkMode) 0.48f else 0.40f),\n                                    Color(0xFF06101E).copy(alpha = if (darkMode) 0.78f else 0.56f)\n                                )\n                            )\n                        ),\n'''
    new_top = '''                        // CANDY_GLASS_V048: liquid-glass style. The aurora stays visible\n                        // through the bar; white highlights and color refraction provide\n                        // the glass edge instead of an opaque dark strip.\n                        modifier = Modifier\n                            .background(\n                                Brush.horizontalGradient(\n                                    listOf(\n                                        Color.White.copy(alpha = if (darkMode) 0.13f else 0.34f),\n                                        MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.13f else 0.15f),\n                                        MaterialTheme.colorScheme.secondary.copy(alpha = if (darkMode) 0.11f else 0.13f),\n                                        Color.White.copy(alpha = if (darkMode) 0.07f else 0.24f)\n                                    )\n                                )\n                            )\n                            .border(\n                                width = 0.8.dp,\n                                brush = Brush.horizontalGradient(\n                                    listOf(\n                                        Color.White.copy(alpha = if (darkMode) 0.40f else 0.68f),\n                                        MaterialTheme.colorScheme.primary.copy(alpha = 0.36f),\n                                        MaterialTheme.colorScheme.secondary.copy(alpha = 0.34f),\n                                        Color.White.copy(alpha = if (darkMode) 0.22f else 0.48f)\n                                    )\n                                ),\n                                shape = RoundedCornerShape(0.dp)\n                            ),\n'''
    text = replace_once(text, old_top, new_top, "liquid glass top bar")

    # Bottom composer gets the same transparent glass treatment and continues through
    # the gesture/navigation inset because v046 moved that padding inside this surface.
    old_bottom = '''        Surface(\n            // FINISH_V046: continuous composer band through the gesture/navigation area.\n            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.82f),\n            contentColor = MaterialTheme.colorScheme.onSurface,\n            tonalElevation = 0.dp,\n            modifier = Modifier.fillMaxWidth()\n        ) {\n'''
    new_bottom = '''        Surface(\n            // FINISH_V046: continuous composer band through the gesture/navigation area.\n            // CANDY_GLASS_V048: transparent liquid-glass composer instead of a black slab.\n            color = Color.Transparent,\n            contentColor = MaterialTheme.colorScheme.onSurface,\n            tonalElevation = 0.dp,\n            modifier = Modifier\n                .fillMaxWidth()\n                .background(\n                    Brush.verticalGradient(\n                        listOf(\n                            Color.White.copy(alpha = if (MaterialTheme.colorScheme.background.luminance() < 0.5f) 0.10f else 0.30f),\n                            MaterialTheme.colorScheme.surface.copy(alpha = if (MaterialTheme.colorScheme.background.luminance() < 0.5f) 0.22f else 0.16f),\n                            MaterialTheme.colorScheme.primary.copy(alpha = 0.07f)\n                        )\n                    )\n                )\n                .border(\n                    width = 0.8.dp,\n                    brush = Brush.horizontalGradient(\n                        listOf(\n                            Color.White.copy(alpha = 0.38f),\n                            MaterialTheme.colorScheme.primary.copy(alpha = 0.30f),\n                            MaterialTheme.colorScheme.secondary.copy(alpha = 0.28f),\n                            Color.White.copy(alpha = 0.18f)\n                        )\n                    ),\n                    shape = RoundedCornerShape(0.dp)\n                )\n        ) {\n'''
    text = replace_once(text, old_bottom, new_bottom, "liquid glass bottom bar")

    # luminance() extension import is needed for a dark/light aware glass alpha.
    if "import androidx.compose.ui.graphics.luminance\n" not in text:
        text = replace_once(
            text,
            "import androidx.compose.ui.graphics.Color\n",
            "import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.graphics.luminance\n",
            "luminance import",
        )

    path.write_text(text, encoding="utf-8")
    print("Applied CANDY_GLASS_V048: vivid candy aurora + translucent liquid-glass bars")


def main() -> None:
    patch_ui()


if __name__ == "__main__":
    main()
