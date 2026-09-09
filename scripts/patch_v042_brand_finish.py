from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "BRAND_FINISH_V042" in text:
        print("BRAND_FINISH_V042 already applied")
        return
    if "VISUAL_THEME_V031" not in text or "WORDMARK_PNG_V041" not in text:
        raise RuntimeError("v031 visual theme and v041 PNG wordmark must run before v042")

    replacements = [
        ("Color(0xFF071019)", "Color(0xFF07131F)", "dark base top"),
        ("Color(0xFF0D1118)", "Color(0xFF101426)", "dark base middle"),
        ("Color(0xFF160B1C)", "Color(0xFF1B0C24)", "dark base bottom"),
        ("Color(0xFFE7F6FF)", "Color(0xFFE8F8FF)", "light base top"),
        ("Color(0xFFF5F1FF)", "Color(0xFFF4F1FF)", "light base middle"),
        ("Color(0xFFFFF0F8)", "Color(0xFFFFF0FA)", "light base bottom"),
        ("MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.38f else 0.30f)", "MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.34f else 0.25f)", "primary aurora alpha"),
        ("center = Offset(120f, 100f)", "center = Offset(60f, 40f)", "primary aurora center"),
        ("radius = 1150f", "radius = 1450f", "primary aurora radius"),
        ("Color(0xFF20D6C7).copy(alpha = if (darkMode) 0.24f else 0.20f)", "Color(0xFF22D6E8).copy(alpha = if (darkMode) 0.28f else 0.20f)", "cyan aurora"),
        ("center = Offset(1040f, 650f)", "center = Offset(960f, 320f)", "cyan aurora center"),
        ("radius = 1250f", "radius = 1550f", "cyan aurora radius"),
        ("Color(0xFF8B5CF6).copy(alpha = if (darkMode) 0.27f else 0.21f)", "Color(0xFF725CFF).copy(alpha = if (darkMode) 0.34f else 0.24f)", "violet aurora"),
        ("center = Offset(180f, 1450f)", "center = Offset(110f, 1250f)", "violet aurora center"),
        ("radius = 1450f", "radius = 1700f", "violet aurora radius"),
        ("Color(0xFFFF5FA2).copy(alpha = if (darkMode) 0.16f else 0.14f)", "Color(0xFFFF4FA3).copy(alpha = if (darkMode) 0.22f else 0.16f)", "pink aurora"),
        ("center = Offset(980f, 1850f)", "center = Offset(1060f, 1720f)", "pink aurora center"),
        ("radius = 1350f", "radius = 1600f", "pink aurora radius"),
    ]

    for old, new, label in replacements:
        text = replace_once(text, old, new, label)

    text = replace_once(
        text,
        "                    // VISUAL_THEME_V031: layered aurora background. The selected accent\n",
        "                    // VISUAL_THEME_V031: layered aurora background. The selected accent\n                    // BRAND_FINISH_V042: wider cyan/violet/pink fields for a smoother aurora.\n",
        "v042 marker",
    )

    path.write_text(text, encoding="utf-8")
    print("Applied BRAND_FINISH_V042: refined aurora gradient")


if __name__ == "__main__":
    main()
