from pathlib import Path

P = Path("scripts/patch_v062_tavily_web_search.py")


def one(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"v062 fixer anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = P.read_text(encoding="utf-8")
    marker = "V062_GENERATED_ANCHORS_FIXED"
    if marker in text:
        print("v062 generated-source anchors already fixed")
        return

    # v028 inserts Top-K and Temperature between thinkingEnabled and error,
    # so v062 must not assume error immediately follows thinkingEnabled.
    text = one(
        text,
        '        "    val thinkingEnabled: Boolean = true,\\n    val error: String? = null,\\n",\n'
        '        "    val thinkingEnabled: Boolean = true,\\n"\n'
        '        "    val webSearchMode: String = \\"MANUAL\\",\\n"\n'
        '        "    val webSearchDepth: String = \\"basic\\",\\n"\n'
        '        "    val webSearchConfigured: Boolean = false,\\n"\n'
        '        "    val webSearching: Boolean = false,\\n"\n'
        '        "    val error: String? = null,\\n",\n',
        '        "    val thinkingEnabled: Boolean = true,\\n",\n'
        '        "    val thinkingEnabled: Boolean = true,\\n"\n'
        '        "    val webSearchMode: String = \\"MANUAL\\",\\n"\n'
        '        "    val webSearchDepth: String = \\"basic\\",\\n"\n'
        '        "    val webSearchConfigured: Boolean = false,\\n"\n'
        '        "    val webSearching: Boolean = false,\\n",\n',
        "UiState fields",
    )

    # v028 also turns the initial thinkingEnabled assignment into a comma and
    # appends Top-K/Temperature. Insert web preferences after Temperature.
    text = one(
        text,
        '        "            thinkingEnabled = prefs.getBoolean(KEY_THINKING_ENABLED, true)\\n",\n'
        '        "            thinkingEnabled = prefs.getBoolean(KEY_THINKING_ENABLED, true),\\n"\n'
        '        "            webSearchMode = prefs.getString(KEY_WEB_SEARCH_MODE, WEB_MODE_MANUAL) ?: WEB_MODE_MANUAL,\\n"\n'
        '        "            webSearchDepth = prefs.getString(KEY_WEB_SEARCH_DEPTH, \\"basic\\") ?: \\"basic\\",\\n"\n'
        '        "            webSearchConfigured = !prefs.getString(KEY_TAVILY_API_KEY, \\"\\").isNullOrBlank()\\n",\n',
        '        "            temperature = prefs.getFloat(\\"temperature\\", 1.0f).coerceIn(0.1f, 1.5f)\\n",\n'
        '        "            temperature = prefs.getFloat(\\"temperature\\", 1.0f).coerceIn(0.1f, 1.5f),\\n"\n'
        '        "            webSearchMode = prefs.getString(KEY_WEB_SEARCH_MODE, WEB_MODE_MANUAL) ?: WEB_MODE_MANUAL,\\n"\n'
        '        "            webSearchDepth = prefs.getString(KEY_WEB_SEARCH_DEPTH, \\"basic\\") ?: \\"basic\\",\\n"\n'
        '        "            webSearchConfigured = !prefs.getString(KEY_TAVILY_API_KEY, \\"\\").isNullOrBlank()\\n",\n',
        "initial state",
    )

    text = text.replace(
        'def patch_view_model() -> None:\n',
        'def patch_view_model() -> None:\n    # V062_GENERATED_ANCHORS_FIXED\n',
        1,
    )
    P.write_text(text, encoding="utf-8")
    print("Fixed v062 anchors for post-v028 generated ViewModel")


if __name__ == "__main__":
    main()
