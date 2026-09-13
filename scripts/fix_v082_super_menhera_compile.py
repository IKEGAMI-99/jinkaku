from pathlib import Path

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
MARKER = "SUPER_MENHERA_V082_THINKING_FIX"


def main() -> None:
    text = VM.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied")
        return

    old = '''                        maxGenerationTokens = 320,
                        topK = _ui.value.topK,
'''
    new = '''                        maxGenerationTokens = 320,
                        enableThinking = false, // SUPER_MENHERA_V082_THINKING_FIX: game owns its inference behavior
                        topK = _ui.value.topK,
'''
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Super Menhera E2B call: expected exactly one anchor, found {count}")

    VM.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Applied {MARKER}: Super Menhera uses direct E2B replies")


if __name__ == "__main__":
    main()
