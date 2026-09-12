from pathlib import Path
import re

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")


def main() -> None:
    text = VM.read_text(encoding="utf-8")

    # Top-P is followed by web/reply settings after all prior patches, so keep
    # the generated data-class argument list syntactically valid.
    text = text.replace(
        '            topP = prefs.getFloat("top_p", 0.90f).coerceIn(0.05f, 1.0f)\n            webSearchMode =',
        '            topP = prefs.getFloat("top_p", 0.90f).coerceIn(0.05f, 1.0f),\n            webSearchMode =',
        1,
    )

    # The E2B-only app no longer has a live E4B inference process to recover.
    text = text.replace(
        '    private val previousInferenceInterrupted = prefs.getBoolean(KEY_E4B_ACTIVE, false)\n',
        '    private val previousInferenceInterrupted = false\n',
        1,
    )
    text = re.sub(
        r'(?m)^[ \t]*prefs\.edit\(\)\.putBoolean\(KEY_E4B_ACTIVE, (?:true|false)\)\.commit\(\)\n',
        '',
        text,
    )
    VM.write_text(text, encoding="utf-8")

    ui = UI.read_text(encoding="utf-8")

    # The old E4B/E2B selector sat inside a wrapper item. v077 removes the
    # selector body; remove the now-orphan wrapper close before the E2B card.
    orphan = '        }\n\n        item {\n            ModernModelCard(\n                title = "Gemma 4 E2B LiteRT-LM",'
    fixed = '        item {\n            ModernModelCard(\n                title = "Gemma 4 E2B LiteRT-LM",'
    count = ui.count(orphan)
    if count != 1:
        raise RuntimeError(f"orphan selector brace: expected 1, got {count}")
    ui = ui.replace(orphan, fixed, 1)

    # Keep the existing Compose shape, but make the disabled E2B Thinking state
    # explicit rather than leaving an apparently functional E4B-era switch.
    ui = ui.replace(
        'Text("Thinking", fontWeight = FontWeight.SemiBold)',
        'Text("Thinking (E2BではOFF固定)", fontWeight = FontWeight.SemiBold)',
        1,
    )
    ui = ui.replace(
        'if (ui.thinkingEnabled) "内部Thinkingを使ってから回答" else "Thinkingを省略して直接回答"',
        '"LiteRT-LMはThinkingを使わず直接回答"',
        1,
    )
    ui = ui.replace(
        'checked = ui.thinkingEnabled,\n                            onCheckedChange = vm::setThinkingEnabled,\n                            enabled = !ui.busy && !ui.e4bImporting',
        'checked = false,\n                            onCheckedChange = null,\n                            enabled = false',
        1,
    )
    ui = ui.replace(
        'if (ui.thinkingEnabled) "Thinking内容は非表示です。" else "OFFではJinjaのenable_thinkingも無効化します。"',
        '"GPU + MTPの高速経路を優先するためOFF固定です。"',
        1,
    )
    ui = ui.replace(
        '最新情報をE4Bの回答コンテキストへ追加します',
        '最新情報をE2Bの回答コンテキストへ追加します',
    )
    ui = ui.replace(
        'Thinkingは別枠で最大512 token。返信の長さは回答本文だけに適用します。Context残量が少ない場合はThinking枠を縮めます。',
        'E2BではThinking OFF固定。返信の長さは回答本文の最大token数です。',
    )
    UI.write_text(ui, encoding="utf-8")

    print("Finalized v077 generated sources")
    print("Remaining E4B references in generated ViewModel/UI:")
    for path in (VM, UI):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "e4b" in line.lower():
                print(f"{path}:{number}:{line.strip()}")


if __name__ == "__main__":
    main()
