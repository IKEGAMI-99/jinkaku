from pathlib import Path

GAME = Path("app/src/main/java/com/ikegami99/jinkaku/game/SuperMenheraGame.kt")
MARKER = "SUPER_MENHERA_V085_COMPILE_FIX"


def main() -> None:
    text = GAME.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied")
        return

    old_map = r'''.map { it.content.replace(Regex("\s+"), " ").trim().take(180) }'''
    new_map = '''.map { it.content.lines().joinToString(" ") { line -> line.trim() }.trim().take(180) }'''
    if old_map not in text:
        raise RuntimeError("v085 recent-assistant whitespace anchor not found")
    text = text.replace(old_map, new_map, 1)

    old_normalize = r'''    private fun normalizeLoopText(raw: String): String = raw
        .lowercase()
        .replace(Regex("[\s。、！？!?「」『』…,.・:：;；()（）\[\]【】]+"), "")
        .trim()
'''
    new_normalize = '''    // SUPER_MENHERA_V085_COMPILE_FIX: avoid regex escaping through the Python patch layer.
    private fun normalizeLoopText(raw: String): String = raw
        .lowercase()
        .filterNot { ch -> ch.isWhitespace() || ch in "。、！？!?「」『』…,.・:：;；()（）[]【】" }
        .trim()
'''
    if old_normalize not in text:
        raise RuntimeError("v085 normalization anchor not found")
    text = text.replace(old_normalize, new_normalize, 1)

    GAME.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER}: removed invalid Kotlin regex escapes")


if __name__ == "__main__":
    main()
