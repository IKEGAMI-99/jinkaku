# v0.1.56 Appearance controls

- Two accent colours are independently editable from an HSV colour wheel plus brightness slider.
- Existing preset selection is used only to seed the new custom colour values on first launch after upgrade.
- Foreground text on custom accent roles and chat bubbles switches automatically between black and white using relative luminance.
- Assistant messages and the typing bubble show a configurable avatar icon. Built-in choices: Sparkle, Brain, Chat, Memory.
- Text size can be switched between 88%, 100%, 116%, and 128%. The selected scale is persisted in SharedPreferences.
- New settings keys: `accent_primary_argb`, `accent_secondary_argb`, `ai_bubble_icon`, `font_scale`.
