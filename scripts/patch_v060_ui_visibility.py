from pathlib import Path

P = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")


def section(text: str, start_marker: str, end_marker: str, label: str) -> tuple[int, int, str]:
    try:
        start = text.index(start_marker)
        end = text.index(end_marker, start)
    except ValueError as exc:
        raise RuntimeError(f"section anchor not found: {label}") from exc
    return start, end, text[start:end]


def main() -> None:
    text = P.read_text(encoding="utf-8")

    if "UI_VISIBILITY_V060" in text:
        print("UI_VISIBILITY_V060 already applied")
        return
    if "AVATAR_CROP_V058" not in text:
        raise RuntimeError("v058 avatar crop patch must run before v060")

    # Drawer brand icon: v056 made primaryContainer equal to primary, so the
    # old primary tint can disappear into the tile. Use the scheme's computed
    # contrasting foreground instead.
    start, end, brand = section(
        text,
        "@Composable\nprivate fun BrandHeader(",
        "@Composable\nprivate fun StatusDot(",
        "BrandHeader",
    )
    old_tint = "tint = MaterialTheme.colorScheme.primary"
    if brand.count(old_tint) != 1:
        raise RuntimeError(f"expected one BrandHeader primary tint, found {brand.count(old_tint)}")
    brand = brand.replace(old_tint, "tint = MaterialTheme.colorScheme.onPrimaryContainer", 1)

    signature = "private fun BrandHeader(modifier: Modifier = Modifier) {\n"
    if signature not in brand:
        raise RuntimeError("BrandHeader signature anchor not found")
    brand = brand.replace(
        signature,
        signature + "    // UI_VISIBILITY_V060: keep the drawer logo visible for any custom accent.\n",
        1,
    )
    text = text[:start] + brand + text[end:]

    # The compact context meter already communicates its meaning through the
    # numeric used/max display. Remove only the leading CTX label and let the
    # progress bar consume the reclaimed width.
    start, end, context = section(
        text,
        "@Composable\nprivate fun ModernContextCard(",
        "@Composable\nprivate fun ModernMemoryScreen(",
        "ModernContextCard",
    )
    lines = context.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines) if 'Text("CTX"' in line]
    if len(matches) != 1:
        raise RuntimeError(f"expected one CTX label, found {len(matches)}")
    del lines[matches[0]]
    context = "".join(lines)
    text = text[:start] + context + text[end:]

    P.write_text(text, encoding="utf-8")
    print("Applied UI_VISIBILITY_V060: contrasting drawer logo + CTX label removed")


if __name__ == "__main__":
    main()
