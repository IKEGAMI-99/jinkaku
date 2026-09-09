from pathlib import Path


def main() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    # calculateTopPadding() is a PaddingValues member in the Compose version used here;
    # importing it as a top-level extension breaks compilation.
    text = text.replace("import androidx.compose.foundation.layout.calculateTopPadding\n", "")

    old = '''                        if (ui.updateDownloadProgress != null) {
                            val updateProgress = ui.updateDownloadProgress.coerceIn(0, 100)
'''
    new = '''                        val updateProgressRaw = ui.updateDownloadProgress
                        if (updateProgressRaw != null) {
                            val updateProgress = updateProgressRaw.coerceIn(0, 100)
'''
    if old not in text:
        if "val updateProgressRaw = ui.updateDownloadProgress" not in text:
            raise RuntimeError("v046 progress anchor not found")
    else:
        text = text.replace(old, new, 1)

    path.write_text(text, encoding="utf-8")
    print("Applied V046_COMPILE_FIX: PaddingValues import + nullable progress smart-cast")


if __name__ == "__main__":
    main()
