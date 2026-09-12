from pathlib import Path

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
PATCH = Path("scripts/patch_v077_e2b_only.py")


def main() -> None:
    # v062/v067 append more UiState arguments after Temperature. The old v028
    # initializer shape expected by v077 did not include a trailing comma.
    text = VM.read_text(encoding="utf-8")
    old = '            temperature = prefs.getFloat("temperature", 1.0f).coerceIn(0.1f, 1.5f),\n'
    if old in text:
        text = text.replace(old, old[:-2] + "\n", 1)
        VM.write_text(text, encoding="utf-8")

    # Keep the generated Compose structure intact. E2B is still Thinking-OFF;
    # the finalizer below only changes the existing control text/state.
    patch = PATCH.read_text(encoding="utf-8")
    patch = patch.replace(
        '    thinking_label = \'Text("Thinking", fontWeight = FontWeight.SemiBold)\'\n',
        '    thinking_label = "__SKIP_DESTRUCTIVE_THINKING_REWRITE__"\n',
        1,
    )
    PATCH.write_text(patch, encoding="utf-8")
    print("Prepared generated v077 anchors")


if __name__ == "__main__":
    main()
