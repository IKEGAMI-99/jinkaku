from pathlib import Path
import re

UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
APP = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuApplication.kt")
MARKER = "MODEL_IMPORT_ROUTER_V071"


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


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to UI")
        return

    text = replace_picker(text, "e4bPicker", "importE4B")
    text = replace_picker(text, "e2bPicker", "importE2B")
    text = replace_picker(text, "embeddingPicker", "importEmbedding")

    text = force_model_local(text, "Gemma 4 E4B HauhauCS", "e4bPicker")
    text = force_model_local(text, "Gemma 4 E2B LiteRT-LM", "e2bPicker")
    text = force_model_local(text, "EmbeddingGemma 300M Q4_0", "embeddingPicker")

    # Keep the version footer in Settings, and also put the build number directly
    # below the drawer brand header so it is visible without scrolling.
    spacer = '        item { Spacer(Modifier.height(30.dp)) }\n'
    if spacer not in text:
        raise RuntimeError("final Settings spacer anchor not found")
    version_footer = f'''        // {MARKER}: visible build identity for update/debug checks.\n        item {{\n            Text(\n                "Jinkaku v${{com.ikegami99.jinkaku.BuildConfig.VERSION_NAME}} · build ${{com.ikegami99.jinkaku.BuildConfig.VERSION_CODE}}",\n                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),\n                style = MaterialTheme.typography.labelMedium,\n                color = MaterialTheme.colorScheme.onSurfaceVariant\n            )\n        }}\n'''
    text = text.replace(spacer, version_footer + spacer, 1)

    brand_pattern = re.compile(r'(?m)^(?P<indent>[ \t]*)BrandHeader\([^\n]*\)\s*$')
    match = brand_pattern.search(text)
    if match is None:
        raise RuntimeError("drawer BrandHeader call not found")
    indent = match.group("indent")
    brand_line = match.group(0)
    drawer_version = (
        brand_line
        + "\n"
        + indent
        + 'Text("v${com.ikegami99.jinkaku.BuildConfig.VERSION_NAME} · b${com.ikegami99.jinkaku.BuildConfig.VERSION_CODE}", '
        + 'modifier = Modifier.padding(start = 20.dp, end = 20.dp, bottom = 10.dp), '
        + 'style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)'
    )
    text = text[:match.start()] + drawer_version + text[match.end():]

    UI.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to UI: dedicated pickers + drawer/settings version")


def patch_view_model() -> None:
    text = VM.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to ViewModel")
        return

    helper_anchor = "    fun importE4B(uri: Uri) {\n"
    if helper_anchor not in text:
        raise RuntimeError("importE4B anchor not found")

    helper = f'''    // {MARKER}: do not trust the UI route alone. Detect LiteRT files at the ViewModel boundary.\n    private fun selectedImportName(uri: Uri): String {{\n        return runCatching {{\n            getApplication<Application>().contentResolver.query(\n                uri,\n                arrayOf(android.provider.OpenableColumns.DISPLAY_NAME),\n                null,\n                null,\n                null\n            )?.use {{ cursor ->\n                if (!cursor.moveToFirst()) return@use null\n                val index = cursor.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)\n                if (index >= 0) cursor.getString(index) else null\n            }}\n        }}.getOrNull() ?: uri.lastPathSegment.orEmpty()\n    }}\n\n'''
    text = text.replace(helper_anchor, helper + helper_anchor, 1)

    e4b_anchor = "    fun importE4B(uri: Uri) {\n        if (_ui.value.busy || anyModelImporting())"
    if e4b_anchor not in text:
        raise RuntimeError("importE4B body anchor not found")
    e4b_replacement = '''    fun importE4B(uri: Uri) {\n        val selectedName = selectedImportName(uri)\n        if (selectedName.endsWith(".litertlm", ignoreCase = true)) {\n            logger.w("MODEL", "Import router E4B->E2B source=$selectedName")\n            importE2B(uri)\n            return\n        }\n        logger.i("MODEL", "Import request route=E4B source=$selectedName")\n        if (_ui.value.busy || anyModelImporting())'''
    text = text.replace(e4b_anchor, e4b_replacement, 1)

    e2b_anchor = "    fun importE2B(uri: Uri) {\n        if (_ui.value.busy || anyModelImporting())"
    if e2b_anchor not in text:
        raise RuntimeError("importE2B body anchor not found")
    e2b_replacement = '''    fun importE2B(uri: Uri) {\n        val selectedName = selectedImportName(uri)\n        logger.i("MODEL", "Import request route=E2B source=$selectedName")\n        if (_ui.value.busy || anyModelImporting())'''
    text = text.replace(e2b_anchor, e2b_replacement, 1)

    emb_anchor = "    fun importEmbedding(uri: Uri) {\n        if (_ui.value.busy || anyModelImporting())"
    if emb_anchor in text:
        emb_replacement = '''    fun importEmbedding(uri: Uri) {\n        val selectedName = selectedImportName(uri)\n        logger.i("MODEL", "Import request route=EMBEDDING source=$selectedName")\n        if (_ui.value.busy || anyModelImporting())'''
        text = text.replace(emb_anchor, emb_replacement, 1)

    VM.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to ViewModel: LiteRT auto-reroute + route diagnostics")


def patch_application() -> None:
    text = APP.read_text(encoding="utf-8")
    old = '        logger.i("APP", "Application started")\n'
    if old not in text:
        if "Application started version=" in text:
            print(f"{MARKER} already applied to Application")
            return
        raise RuntimeError("Application started log anchor not found")
    new = '        logger.i("APP", "Application started version=${BuildConfig.VERSION_NAME} code=${BuildConfig.VERSION_CODE}")\n'
    text = text.replace(old, new, 1)
    APP.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to Application: startup build identity")


def main() -> None:
    patch_ui()
    patch_view_model()
    patch_application()
    print(f"Applied {MARKER}: model import routing is now defensive at both UI and ViewModel layers")


if __name__ == "__main__":
    main()
