from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "WORDMARK_PNG_V041" in text:
        print("WORDMARK_PNG_V041 already applied")
        return
    if "VISUAL_THEME_V031" not in text:
        raise RuntimeError("VISUAL_THEME_V031 must run before WORDMARK_PNG_V041")

    if "import android.graphics.BitmapFactory\n" not in text:
        text = replace_once(
            text,
            "import android.content.Intent\n",
            "import android.content.Intent\nimport android.graphics.BitmapFactory\n",
            "BitmapFactory import",
        )
    if "import androidx.compose.foundation.Image\n" not in text:
        text = replace_once(
            text,
            "import androidx.compose.foundation.background\n",
            "import androidx.compose.foundation.Image\nimport androidx.compose.foundation.background\n",
            "Image import",
        )
    if "import androidx.compose.runtime.produceState\n" not in text:
        text = replace_once(
            text,
            "import androidx.compose.runtime.mutableStateOf\n",
            "import androidx.compose.runtime.mutableStateOf\nimport androidx.compose.runtime.produceState\n",
            "produceState import",
        )
    if "import androidx.compose.ui.graphics.asImageBitmap\n" not in text:
        text = replace_once(
            text,
            "import androidx.compose.ui.graphics.Color\n",
            "import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.graphics.asImageBitmap\n",
            "asImageBitmap import",
        )
    if "import com.ikegami99.jinkaku.R\n" not in text:
        text = replace_once(
            text,
            "import com.ikegami99.jinkaku.JinkakuViewModel\n",
            "import com.ikegami99.jinkaku.JinkakuViewModel\nimport com.ikegami99.jinkaku.R\n",
            "R import",
        )

    old = '                                Text("Jinkaku", fontWeight = FontWeight.Bold)\n'
    new = '''                                // WORDMARK_PNG_V041: PNG decode with fallback.
                                val wordmarkContext = LocalContext.current
                                val wordmarkBitmap by produceState<androidx.compose.ui.graphics.ImageBitmap?>(initialValue = null) {
                                    value = runCatching {
                                        BitmapFactory.decodeResource(
                                            wordmarkContext.resources,
                                            R.drawable.jinkaku_wordmark_png
                                        )?.asImageBitmap()
                                    }.getOrNull()
                                }
                                if (wordmarkBitmap != null) {
                                    Image(
                                        bitmap = wordmarkBitmap!!,
                                        contentDescription = "Jinkaku",
                                        modifier = Modifier.width(142.dp).height(23.dp)
                                    )
                                } else {
                                    Text("JINKAKU", fontWeight = FontWeight.Bold)
                                }
'''
    text = replace_once(text, old, new, "PNG top app bar wordmark")

    path.write_text(text, encoding="utf-8")
    print("Applied WORDMARK_PNG_V041: PNG wordmark with safe fallback")


if __name__ == "__main__":
    main()
