from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "WORDMARK_ONLY_V039" in text:
        print("WORDMARK_ONLY_V039 already applied")
        return
    if "VISUAL_THEME_V031" not in text:
        raise RuntimeError("VISUAL_THEME_V031 must run before WORDMARK_ONLY_V039")

    if "import androidx.compose.foundation.Image\n" not in text:
        text = replace_once(
            text,
            "import androidx.compose.foundation.background\n",
            "import androidx.compose.foundation.Image\nimport androidx.compose.foundation.background\n",
            "Image import",
        )
    if "import androidx.compose.ui.layout.ContentScale\n" not in text:
        text = replace_once(
            text,
            "import androidx.compose.ui.graphics.Color\n",
            "import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.layout.ContentScale\n",
            "ContentScale import",
        )
    if "import androidx.compose.ui.res.painterResource\n" not in text:
        text = replace_once(
            text,
            "import androidx.compose.ui.platform.LocalSoftwareKeyboardController\n",
            "import androidx.compose.ui.platform.LocalSoftwareKeyboardController\nimport androidx.compose.ui.res.painterResource\n",
            "painterResource import",
        )
    if "import com.ikegami99.jinkaku.R\n" not in text:
        text = replace_once(
            text,
            "import com.ikegami99.jinkaku.JinkakuViewModel\n",
            "import com.ikegami99.jinkaku.JinkakuViewModel\nimport com.ikegami99.jinkaku.R\n",
            "R import",
        )

    old = '                                Text("Jinkaku", fontWeight = FontWeight.Bold)\n'
    new = '''                                // WORDMARK_ONLY_V039\n                                Image(\n                                    painter = painterResource(R.drawable.jinkaku_wordmark),\n                                    contentDescription = "Jinkaku",\n                                    contentScale = ContentScale.Fit,\n                                    modifier = Modifier.width(142.dp).height(23.dp)\n                                )\n'''
    text = replace_once(text, old, new, "top app bar wordmark")

    path.write_text(text, encoding="utf-8")
    print("Applied WORDMARK_ONLY_V039: top app bar wordmark only")


if __name__ == "__main__":
    main()
