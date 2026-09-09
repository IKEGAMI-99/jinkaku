from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "BRANDING_V037" in text:
        print("BRANDING_V037 already applied")
        return
    if "VISUAL_THEME_V031" not in text:
        raise RuntimeError("VISUAL_THEME_V031 must run before BRANDING_V037")

    if "import androidx.compose.foundation.Image\n" not in text:
        text = replace_once(text, "import androidx.compose.foundation.background\n", "import androidx.compose.foundation.Image\nimport androidx.compose.foundation.background\n", "Image import")
    if "import androidx.compose.ui.layout.ContentScale\n" not in text:
        text = replace_once(text, "import androidx.compose.ui.graphics.Color\n", "import androidx.compose.ui.graphics.Color\nimport androidx.compose.ui.layout.ContentScale\n", "ContentScale import")
    if "import androidx.compose.ui.res.painterResource\n" not in text:
        text = replace_once(text, "import androidx.compose.ui.platform.LocalSoftwareKeyboardController\n", "import androidx.compose.ui.platform.LocalSoftwareKeyboardController\nimport androidx.compose.ui.res.painterResource\n", "painterResource import")
    if "import com.ikegami99.jinkaku.R\n" not in text:
        text = replace_once(text, "import com.ikegami99.jinkaku.JinkakuViewModel\n", "import com.ikegami99.jinkaku.JinkakuViewModel\nimport com.ikegami99.jinkaku.R\n", "R import")

    old_title = '''                        title = {\n                            Column {\n                                Text("Jinkaku", fontWeight = FontWeight.Bold)\n                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                                    StatusDot(ui.busy)\n                                    Text(\n                                        "$statusText  ·  Memory ${ui.memoryCount}",\n                                        style = MaterialTheme.typography.labelMedium,\n                                        color = MaterialTheme.colorScheme.onSurfaceVariant\n                                    )\n                                }\n                            }\n                        },\n'''
    new_title = '''                        title = {\n                            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {\n                                Image(\n                                    painter = painterResource(R.drawable.jinkaku_wordmark),\n                                    contentDescription = "Jinkaku",\n                                    contentScale = ContentScale.Fit,\n                                    modifier = Modifier.width(142.dp).height(23.dp)\n                                )\n                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {\n                                    StatusDot(ui.busy)\n                                    Text(\n                                        "$statusText  ·  Memory ${ui.memoryCount}",\n                                        style = MaterialTheme.typography.labelMedium,\n                                        color = MaterialTheme.colorScheme.onSurfaceVariant\n                                    )\n                                }\n                            }\n                        },\n'''
    text = replace_once(text, old_title, new_title, "top app bar wordmark")

    old_header = '''@Composable\nprivate fun BrandHeader(modifier: Modifier = Modifier) {\n    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {\n        Surface(\n            shape = RoundedCornerShape(18.dp),\n            color = MaterialTheme.colorScheme.primaryContainer,\n            modifier = Modifier.size(48.dp)\n        ) {\n            Box(contentAlignment = Alignment.Center) {\n                Icon(Icons.Rounded.Psychology, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(28.dp))\n            }\n        }\n        Column {\n            Text("Jinkaku", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)\n            Text("Local persona AI", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)\n        }\n    }\n}\n'''
    new_header = '''@Composable\nprivate fun BrandHeader(modifier: Modifier = Modifier) {\n    // BRANDING_V037\n    Row(modifier, verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {\n        Surface(\n            shape = RoundedCornerShape(18.dp),\n            color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.72f),\n            modifier = Modifier.size(48.dp)\n        ) {\n            Box(contentAlignment = Alignment.Center) {\n                Icon(Icons.Rounded.Psychology, null, tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(28.dp))\n            }\n        }\n        Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {\n            Image(\n                painter = painterResource(R.drawable.jinkaku_wordmark),\n                contentDescription = "Jinkaku",\n                contentScale = ContentScale.Fit,\n                modifier = Modifier.width(156.dp).height(25.dp)\n            )\n            Text("Local persona AI", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)\n        }\n    }\n}\n'''
    text = replace_once(text, old_header, new_header, "drawer wordmark")

    replacements = {
        "Color(0xFF071019)": "Color(0xFF071522)",
        "Color(0xFF0D1118)": "Color(0xFF101224)",
        "Color(0xFF160B1C)": "Color(0xFF190D20)",
        "Color(0xFFE7F6FF)": "Color(0xFFE5F7FF)",
        "Color(0xFFF5F1FF)": "Color(0xFFF4F0FF)",
        "Color(0xFFFFF0F8)": "Color(0xFFFFF1F8)",
        "MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.38f else 0.30f)": "MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.31f else 0.24f)",
        "center = Offset(120f, 100f)": "center = Offset(80f, 40f)",
        "radius = 1150f": "radius = 1480f",
        "Color(0xFF20D6C7).copy(alpha = if (darkMode) 0.24f else 0.20f)": "Color(0xFF25D9E6).copy(alpha = if (darkMode) 0.27f else 0.20f)",
        "center = Offset(1040f, 650f)": "center = Offset(980f, 330f)",
        "radius = 1250f": "radius = 1500f",
        "Color(0xFF8B5CF6).copy(alpha = if (darkMode) 0.27f else 0.21f)": "Color(0xFF7A5CFF).copy(alpha = if (darkMode) 0.31f else 0.23f)",
        "center = Offset(180f, 1450f)": "center = Offset(140f, 1260f)",
        "radius = 1450f": "radius = 1640f",
        "Color(0xFFFF5FA2).copy(alpha = if (darkMode) 0.16f else 0.14f)": "Color(0xFFFF4FA8).copy(alpha = if (darkMode) 0.18f else 0.14f)",
        "center = Offset(980f, 1850f)": "center = Offset(1040f, 1740f)",
        "radius = 1350f": "radius = 1540f",
    }
    for old, new in replacements.items():
        if old not in text:
            raise RuntimeError(f"aurora anchor not found: {old}")
        text = text.replace(old, new, 1)

    path.write_text(text, encoding="utf-8")
    print("Applied BRANDING_V037: wordmark + refined aurora")


if __name__ == "__main__":
    main()
