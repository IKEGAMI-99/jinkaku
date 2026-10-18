"""AUTO_VOICE_V088: install automatic voice playback after v086 has patched the modern UI."""
from pathlib import Path

UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
MARKER = "AUTO_VOICE_V088"

def main():
    text = UI.read_text(encoding="utf-8")
    if MARKER in text:
        print("AUTO_VOICE_V088 already applied")
        return
    if "QWEN_TTS_V086" not in text:
        raise RuntimeError("Run v086 Qwen voice UI patch first")

    def one(old, new, label):
        nonlocal text
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"{label}: expected one anchor, found {count}")
        text = text.replace(old, new, 1)

    one(
        "import com.ikegami99.jinkaku.voice.JinkakuVoiceDialog\n",
        "import com.ikegami99.jinkaku.voice.JinkakuVoiceDialog\n"
        "import com.ikegami99.jinkaku.voice.JinkakuAutoVoice\n",
        "Auto voice import",
    )
    one(
        "            JinkakuVoiceDialog(vm) { showVoiceDialog = false }\n"
        "        }\n",
        "            JinkakuVoiceDialog(vm) { showVoiceDialog = false }\n"
        "        }\n"
        "        // AUTO_VOICE_V088: responds only to new completed user/assistant turns.\n"
        "        JinkakuAutoVoice(vm, chatVisible = screen == ModernScreen.CHAT && !showVoiceDialog)\n",
        "Auto voice lifecycle",
    )

    UI.write_text(text, encoding="utf-8")
    print("Applied AUTO_VOICE_V088: auto playback composition")


if __name__ == "__main__":
    main()
