from pathlib import Path

E2B_CHAT = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E2BChatEngine.kt")
MARKER = "E2B_THOUGHT_CHANNEL_V074"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = E2B_CHAT.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied")
        return

    # Jinkaku's E4B prompt may carry an explicit <|think|> control marker.
    # LiteRT-LM already receives ThinkingConfig(enableThinking=false), so do not pass
    # that E4B-only marker into the E2B prompt template.
    old_prompt = '''        val systemWithHistory = buildString {
            append(systemPrompt.trim())
'''
    new_prompt = f'''        // {MARKER}: keep E4B control tokens out of the LiteRT-LM prompt.
        val e2bSystemPrompt = systemPrompt.replace("<|think|>", "").trim()
        val systemWithHistory = buildString {{
            append(e2bSystemPrompt)
'''
    text = one(text, old_prompt, new_prompt, "E2B system prompt sanitization")

    # IMPORTANT: LiteRT-LM defines null as "use channel metadata from the model" while
    # emptyList() disables channel parsing entirely. Disabling it exposes control text such as
    # <|channel>thought in Message.contents, which Jinkaku then streams to the chat UI.
    text = one(
        text,
        "                channels = emptyList(),\n",
        "                channels = null,\n",
        "LiteRT-LM channel metadata",
    )

    text = one(
        text,
        '            "Generation start runtime=LiteRT-LM backend=GPU mtp=ON async=true ctx=$maxContext " +\n',
        '            "Generation start runtime=LiteRT-LM backend=GPU mtp=ON channels=metadata thinking=OFF async=true ctx=$maxContext " +\n',
        "E2B diagnostic log",
    )

    E2B_CHAT.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER}: restore model channel parsing and strip E4B think marker")


if __name__ == "__main__":
    main()
