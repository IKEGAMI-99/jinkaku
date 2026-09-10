from pathlib import Path

path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
text = path.read_text(encoding="utf-8")

if "import androidx.compose.foundation.Canvas\n" not in text:
    anchor = "import androidx.compose.foundation.Image\n"
    if anchor not in text:
        raise RuntimeError("Canvas import anchor not found")
    text = text.replace(anchor, "import androidx.compose.foundation.Canvas\n" + anchor, 1)
    path.write_text(text, encoding="utf-8")
    print("Applied V056_CANVAS_FIX: Compose Canvas import")
else:
    print("V056_CANVAS_FIX already applied")
