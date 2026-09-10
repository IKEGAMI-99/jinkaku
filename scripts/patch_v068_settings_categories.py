from pathlib import Path
import re

UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")


def one(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = UI.read_text(encoding="utf-8")
    if "SETTINGS_CATEGORIES_V068" in text:
        print("SETTINGS_CATEGORIES_V068 already applied")
        return
    if "REPLY_STYLE_UI_V067" not in text:
        raise RuntimeError("v067 settings UI must run before v068")

    # Category chevrons.
    if "import androidx.compose.material.icons.rounded.KeyboardArrowDown\n" not in text:
        text = one(
            text,
            "import androidx.compose.material.icons.rounded.History\n",
            "import androidx.compose.material.icons.rounded.History\n"
            "import androidx.compose.material.icons.rounded.KeyboardArrowDown\n"
            "import androidx.compose.material.icons.rounded.KeyboardArrowUp\n",
            "settings category icon imports",
        )

    # The drawer already contains Settings. Remove the duplicate chat-screen
    # shortcut so New becomes the right-most action in the app bar.
    gear_pattern = re.compile(
        r'''\n(?P<indent>[ \t]*)IconButton\(onClick = \{\s*\n'''
        r'''[ \t]*dismissIme\(\); screen = if \(screen == ModernScreen\.SETTINGS\) ModernScreen\.CHAT else ModernScreen\.SETTINGS\s*\n'''
        r'''[ \t]*\}\) \{\s*\n'''
        r'''[ \t]*Icon\(if \(screen == ModernScreen\.SETTINGS\) Icons\.Rounded\.ChatBubbleOutline else Icons\.Rounded\.Settings, null\)\s*\n'''
        r'''[ \t]*\}\s*\n'''
    )
    text, removed = gear_pattern.subn("\n", text, count=1)
    if removed != 1:
        raise RuntimeError(f"expected one top-bar Settings shortcut, removed {removed}")

    settings_start = text.index("@Composable\nprivate fun ModernSettingsScreen(")
    settings_end = text.index("\n@Composable\nprivate fun ModernSectionTitle(", settings_start)
    settings = text[settings_start:settings_end]

    state_anchor = "    var personaDraft by remember { mutableStateOf(vm.currentPersona()) }\n"
    settings = one(
        settings,
        state_anchor,
        state_anchor
        + "    // SETTINGS_CATEGORIES_V068: keep the long Settings screen compact; only one category is open at a time.\n"
        + "    var expandedSettingsCategory by remember { mutableStateOf<String?>(null) }\n",
        "expanded settings category state",
    )

    heading_pattern = re.compile(
        r'''(?m)^(?P<indent>[ \t]*)item \{ ModernSectionTitle\("(?P<title>[^"]+)", (?P<icon>[A-Za-z0-9_.]+)\) \}[ \t]*$'''
    )
    headings = list(heading_pattern.finditer(settings))
    if len(headings) < 5:
        raise RuntimeError(f"expected Settings sections to categorize, found {len(headings)}")

    tail_match = re.search(
        r'''(?m)^        item \{ Spacer\(Modifier\.height\(30\.dp\)\) \}[ \t]*$''',
        settings[headings[-1].end():],
    )
    if tail_match is None:
        raise RuntimeError("final Settings spacer anchor not found")
    tail_start = headings[-1].end() + tail_match.start()

    prefix = settings[:headings[0].start()]
    rebuilt = [prefix]
    for index, heading in enumerate(headings):
        indent = heading.group("indent")
        title = heading.group("title")
        icon = heading.group("icon")
        content_end = headings[index + 1].start() if index + 1 < len(headings) else tail_start
        content = settings[heading.end():content_end]
        rebuilt.append(
            f'{indent}item {{\n'
            f'{indent}    ModernSettingsCategoryHeader(\n'
            f'{indent}        text = "{title}",\n'
            f'{indent}        icon = {icon},\n'
            f'{indent}        expanded = expandedSettingsCategory == "{title}",\n'
            f'{indent}        onClick = {{ expandedSettingsCategory = if (expandedSettingsCategory == "{title}") null else "{title}" }}\n'
            f'{indent}    )\n'
            f'{indent}}}\n'
            f'{indent}if (expandedSettingsCategory == "{title}") {{'
        )
        rebuilt.append(content)
        rebuilt.append(f'{indent}}}\n\n')

    rebuilt.append(settings[tail_start:])
    settings = "".join(rebuilt)
    text = text[:settings_start] + settings + text[settings_end:]

    category_header = r'''
@Composable
private fun ModernSettingsCategoryHeader(
    text: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    expanded: Boolean,
    onClick: () -> Unit
) {
    Card(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(20.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (expanded) {
                MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.42f)
            } else {
                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.46f)
            },
            contentColor = if (expanded) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurface
        )
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Surface(
                shape = RoundedCornerShape(12.dp),
                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.14f),
                modifier = Modifier.size(38.dp)
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Icon(icon, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(20.dp))
                }
            }
            Text(text, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.weight(1f))
            Icon(
                if (expanded) Icons.Rounded.KeyboardArrowUp else Icons.Rounded.KeyboardArrowDown,
                contentDescription = if (expanded) "閉じる" else "開く",
                tint = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

'''
    text = one(
        text,
        "@Composable\nprivate fun ModernSectionTitle(",
        category_header + "@Composable\nprivate fun ModernSectionTitle(",
        "settings category header composable",
    )

    UI.write_text(text, encoding="utf-8")
    print(f"Applied SETTINGS_CATEGORIES_V068: {len(headings)} collapsible categories + right-most New button")


if __name__ == "__main__":
    main()
