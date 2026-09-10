from pathlib import Path

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")


def one(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = VM.read_text(encoding="utf-8")
    if "WEB_PREFILL_BUDGET_V063" in text:
        print("WEB_PREFILL_BUDGET_V063 already applied")
        return
    if "TAVILY_WEB_SEARCH_V062" not in text:
        raise RuntimeError("v062 Tavily web search must run before v063")

    text = one(
        text,
        '                    val webResults = searchWebIfNeeded(clean, forceWebSearch)\n'
        '                    _ui.value = _ui.value.copy(webSearching = false, runtimeStatus = "入力中")\n'
        '                    val relevant = withContext(Dispatchers.IO) { memory.retrieve(clean, 10) }\n',
        '                    val webResults = searchWebIfNeeded(clean, forceWebSearch)\n'
        '                    _ui.value = _ui.value.copy(\n'
        '                        webSearching = false,\n'
        '                        runtimeStatus = if (webResults.isEmpty()) "入力中" else "WEB情報を読込中"\n'
        '                    )\n'
        '                    val relevant = withContext(Dispatchers.IO) { memory.retrieve(clean, 10) }\n',
        "web prefill status",
    )

    text = one(
        text,
        '                    val systemWithWeb = if (webResults.isEmpty()) system else system + "\\n\\n" + buildWebContext(webResults)\n',
        '                    val systemWithWeb = if (webResults.isEmpty()) system else system + "\\n\\n" + buildWebContext(webResults)\n'
        '                    if (webResults.isNotEmpty()) {\n'
        '                        _ui.value = _ui.value.copy(runtimeStatus = "WEB情報を読込中")\n'
        '                    }\n',
        "web context status",
    )

    text = one(
        text,
        '                    depth = state.webSearchDepth,\n'
        '                    maxResults = 5\n',
        '                    depth = state.webSearchDepth,\n'
        '                    maxResults = if (state.webSearchDepth.equals("advanced", ignoreCase = true)) 5 else 3\n',
        "result count by depth",
    )

    old_context = '''    private fun buildWebContext(results: List<WebSearchResult>): String {
        val budget = when {
            _ui.value.contextSize <= 2048L -> 2200
            _ui.value.contextSize <= 4096L -> 4400
            else -> 7600
        }
        val chunks = StringBuilder()
        results.forEachIndexed { index, result ->
            if (chunks.length >= budget) return@forEachIndexed
            val title = result.title.replace("\\n", " ").trim()
            val url = result.url.replace("\\n", "").trim()
            val header = "[${index + 1}] $title\\nURL: $url\\nExcerpt: "
            val room = (budget - chunks.length - header.length - 2).coerceAtLeast(0)
            if (room < 80) return@forEachIndexed
            val excerpt = result.content
                .replace("<|", "< |")
                .replace("|>", "| >")
                .replace(Regex("\\\\s+"), " ")
                .trim()
                .take(room.coerceAtMost(1100))
            chunks.append(header).append(excerpt).append("\\n\\n")
        }
'''

    new_context = '''    // WEB_PREFILL_BUDGET_V063: keep Web grounding useful without turning CPU prefill into a multi-minute stall.
    private fun buildWebContext(results: List<WebSearchResult>): String {
        val advanced = _ui.value.webSearchDepth.equals("advanced", ignoreCase = true)
        val budget = when {
            !advanced && _ui.value.contextSize <= 2048L -> 1100
            !advanced -> 1500
            _ui.value.contextSize <= 2048L -> 1600
            _ui.value.contextSize <= 4096L -> 2400
            else -> 3000
        }
        val perResultLimit = if (advanced) 600 else 450
        val chunks = StringBuilder()
        results.forEachIndexed { index, result ->
            if (chunks.length >= budget) return@forEachIndexed
            val title = result.title.replace("\\n", " ").trim()
            val url = result.url.replace("\\n", "").trim()
            val header = "[${index + 1}] $title\\nURL: $url\\nExcerpt: "
            val room = (budget - chunks.length - header.length - 2).coerceAtLeast(0)
            if (room < 80) return@forEachIndexed
            val excerpt = result.content
                .replace("<|", "< |")
                .replace("|>", "| >")
                .replace(Regex("\\\\s+"), " ")
                .trim()
                .take(room.coerceAtMost(perResultLimit))
            chunks.append(header).append(excerpt).append("\\n\\n")
        }
        logger.i(
            "WEB",
            "Web context prepared depth=${_ui.value.webSearchDepth} results=${results.size} chars=${chunks.length} budget=$budget perResult=$perResultLimit"
        )
'''

    text = one(text, old_context, new_context, "web context budget")
    VM.write_text(text, encoding="utf-8")
    print("Applied WEB_PREFILL_BUDGET_V063: Basic 3x450, Advanced 5x600, context-aware total budget")


if __name__ == "__main__":
    main()
