from pathlib import Path

PATCH = Path("scripts/patch_v070_e2b_import_version.py")

text = PATCH.read_text(encoding="utf-8")

old = '''    text = one(
        text,
        '                        runtimeStatus = "E4B READY"\\n',
        '                        runtimeStatus = if (activeMainEngine == "E2B") "E2B GPU READY" else "E4B READY"\\n',
        "dynamic ready status",
    )
'''

new = '''    ready_anchor = '                        runtimeStatus = "E4B READY"\\n'
    if ready_anchor not in text:
        raise RuntimeError("normal ready status anchor not found")
    # Normal send() appears before monologue generation. Only patch the first READY state;
    # the later E4B READY belongs to the independent monologue path.
    text = text.replace(
        ready_anchor,
        '                        runtimeStatus = if (activeMainEngine == "E2B") "E2B GPU READY" else "E4B READY"\\n',
        1,
    )
'''

if old not in text:
    if "normal ready status anchor not found" in text:
        print("V072 main-chat patch fix already applied")
    else:
        raise RuntimeError("V072 ready-status patch anchor not found")
else:
    PATCH.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Applied V072 patch fix: normal chat READY replacement is now first-match only")
