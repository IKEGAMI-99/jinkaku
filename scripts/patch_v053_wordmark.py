"""Fit the replacement 3:1 wordmark after the existing UI patches."""

from pathlib import Path


def main() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")
    marker = "// WORDMARK_V053: preserve the supplied artwork's 3:1 aspect ratio."
    if marker in text:
        print("WORDMARK_V053 already applied")
        return
    if "SPARKLE_BACK_V052" not in text:
        raise RuntimeError("v052 UI patch must run before v053")

    old = '''                                        bitmap = wordmarkBitmap!!,
                                        contentDescription = "Jinkaku",
                                        modifier = Modifier.width(142.dp).height(23.dp)'''
    new = '''                                        bitmap = wordmarkBitmap!!,
                                        contentDescription = "Jinkaku",
                                        // WORDMARK_V053: preserve the supplied artwork's 3:1 aspect ratio.
                                        contentScale = androidx.compose.ui.layout.ContentScale.Fit,
                                        modifier = Modifier.width(144.dp).height(48.dp)'''
    if text.count(old) != 1:
        raise RuntimeError("Expected exactly one wordmark image layout")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Applied WORDMARK_V053: 144 x 48 dp wordmark, existing decode fallback retained")


if __name__ == "__main__":
    main()
