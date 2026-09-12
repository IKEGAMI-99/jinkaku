from pathlib import Path
import re

UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
MARKER = "E2B_IMPORT_VERSION_V070"


def replace_picker(text: str, name: str, vm_method: str) -> str:
    pattern = re.compile(
        rf"(?m)^    val {re.escape(name)} = rememberLauncherForActivityResult\(ActivityResultContracts\.OpenDocument\(\)\) \{{.*$"
    )
    replacement = (
        f"    val {name} = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) "
        f"{{ if (it != null) vm.{vm_method}(it) }}"
    )
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"picker anchor not found: {name}")
    return text


def force_model_local(text: str, title: str, picker: str) -> str:
    pattern = re.compile(
        rf'(title\s*=\s*"{re.escape(title)}",.*?onLocal\s*=\s*)\{{[^{{}}\n]*\}}',
        re.S,
    )
    replacement = rf'\1{{ {picker}.launch(arrayOf("*/*")) }}'
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"model Local anchor not found: {title}")
    return text


def main() -> None:
    text = UI.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied")
        return

    # Keep every model card wired to its own picker. This runs last in CI so later
    # UI transformations cannot accidentally make the E2B Local button call importE4B().
    text = replace_picker(text, "e4bPicker", "importE4B")
    text = replace_picker(text, "e2bPicker", "importE2B")
    text = replace_picker(text, "embeddingPicker", "importEmbedding")

    text = force_model_local(text, "Gemma 4 E4B HauhauCS", "e4bPicker")
    text = force_model_local(text, "Gemma 4 E2B LiteRT-LM", "e2bPicker")
    text = force_model_local(text, "EmbeddingGemma 300M Q4_0", "embeddingPicker")

    spacer = '        item { Spacer(Modifier.height(30.dp)) }\n'
    if spacer not in text:
        raise RuntimeError("final Settings spacer anchor not found")

    version_footer = f'''        // {MARKER}: visible build identity for update/debug checks.\n        item {{\n            Text(\n                "Jinkaku v${{com.ikegami99.jinkaku.BuildConfig.VERSION_NAME}} · build ${{com.ikegami99.jinkaku.BuildConfig.VERSION_CODE}}",\n                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),\n                style = MaterialTheme.typography.labelMedium,\n                color = MaterialTheme.colorScheme.onSurfaceVariant\n            )\n        }}\n'''
    text = text.replace(spacer, version_footer + spacer, 1)

    UI.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER}: E2B picker routing + Settings version footer")


if __name__ == "__main__":
    main()
