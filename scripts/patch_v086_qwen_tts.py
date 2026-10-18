"""QWEN_TTS_V086: inject a voice-dialog entry after all legacy UI patches."""
from pathlib import Path

UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
MARKER = "QWEN_TTS_V086"


def main():
    text = UI.read_text(encoding="utf-8")
    if MARKER in text:
        print("QWEN_TTS_V086 already applied")
        return

    def one(old, new, label):
        global text
        count = text.count(old)
        if count != 1:
            raise RuntimeError(f"{label}: expected one anchor, found {count}")
        text = text.replace(old, new, 1)

    one(
        "import com.ikegami99.jinkaku.JinkakuViewModel\n",
        "import com.ikegami99.jinkaku.JinkakuViewModel\n"
        "import com.ikegami99.jinkaku.voice.JinkakuVoiceDialog\n"
        "import androidx.compose.material.icons.rounded.VolumeUp\n",
        "Qwen voice UI imports",
    )
    one(
        "    var screen by remember { mutableStateOf(ModernScreen.CHAT) }",
        "    var screen by remember { mutableStateOf(ModernScreen.CHAT) }\n"
        "    var showVoiceDialog by remember { mutableStateOf(false) } // QWEN_TTS_V086",
        "Qwen voice dialog state",
    )
    one(
        "        if (confirmClearChats) {",
        "        if (showVoiceDialog) {\n"
        "            JinkakuVoiceDialog(vm) { showVoiceDialog = false }\n"
        "        }\n"
        "        if (confirmClearChats) {",
        "Qwen voice dialog insertion",
    )
    one(
        "                        actions = {\n                            if (screen == ModernScreen.CHAT) {",
        "                        actions = {\n"
        "                            if (screen == ModernScreen.CHAT) {\n"
        "                                IconButton(onClick = { dismissIme(); showVoiceDialog = true }) {\n"
        "                                    Icon(Icons.Rounded.VolumeUp, contentDescription = \"Qwen3-TTS音声\")\n"
        "                                }\n"
        "                            }\n"
        "                            if (screen == ModernScreen.CHAT) {",
        "Qwen voice top-bar button",
    )
    UI.write_text(text, encoding="utf-8")
    print("Applied QWEN_TTS_V086: voice UI entry point")


if __name__ == "__main__":
    main()
