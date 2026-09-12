from pathlib import Path

p = Path("scripts/patch_v047_ui_refine.py")
t = p.read_text(encoding="utf-8")
marker = "    text = replace_once(\n        text,\n        '''                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {"
s = t.find(marker)
if s >= 0:
    e = t.find("    path.write_text", s)
    if e < 0:
        raise RuntimeError("v047 path.write_text anchor not found")
    replacement = "    text = text.replace('Text(\"Context window\", fontWeight = FontWeight.SemiBold)', 'Text(\"Context\", fontWeight = FontWeight.SemiBold)', 1)\n\n"
    t = t[:s] + replacement + t[e:]
    p.write_text(t, encoding="utf-8")
print("Prepared v047 patch anchors")
