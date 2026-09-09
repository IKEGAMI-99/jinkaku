from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_ui() -> None:
    path = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
    text = path.read_text(encoding="utf-8")

    if "DIAGONAL_GLASS_V054" in text:
        print("DIAGONAL_GLASS_V054 already applied")
        return
    if "WORDMARK_V053" not in text:
        raise RuntimeError("v053 wordmark patch must run before v054")

    old_top = '''                        // CANDY_GLASS_V048: liquid-glass style. The aurora stays visible
                        // through the bar; white highlights and color refraction provide
                        // the glass edge instead of an opaque dark strip.
                        // KAWAII_GLASS_V049: clearer glass with a brighter specular sheen.
                        // EDGE_GLOSS_V050: only the chat-facing bottom edge is drawn.
                        modifier = Modifier
                            .background(
                                Brush.horizontalGradient(
                                    listOf(
                                        MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.055f else 0.045f),
                                        Color.Transparent,
                                        MaterialTheme.colorScheme.secondary.copy(alpha = if (darkMode) 0.050f else 0.040f),
                                        Color.Transparent
                                    )
                                )
                            )
                            .background(
                                Brush.verticalGradient(
                                    listOf(
                                        Color.White.copy(alpha = if (darkMode) 0.38f else 0.52f),
                                        Color.White.copy(alpha = if (darkMode) 0.14f else 0.21f),
                                        Color.Transparent,
                                        Color.White.copy(alpha = if (darkMode) 0.035f else 0.055f)
                                    )
                                )
                            )
                            .background(
                                Brush.radialGradient(
                                    colors = listOf(
                                        Color.White.copy(alpha = if (darkMode) 0.23f else 0.34f),
                                        Color.Transparent
                                    ),
                                    center = Offset(170f, -30f),
                                    radius = 650f
                                )
                            )
                            .drawBehind {
                                drawLine(
                                    color = Color.White.copy(alpha = if (darkMode) 0.34f else 0.55f),
                                    start = Offset(0f, size.height - 0.5.dp.toPx()),
                                    end = Offset(size.width, size.height - 0.5.dp.toPx()),
                                    strokeWidth = 0.7.dp.toPx()
                                )
                            },
'''

    new_top = '''                        // CANDY_GLASS_V048: liquid-glass style. The aurora stays visible
                        // through the bar; white highlights and color refraction provide
                        // the glass edge instead of an opaque dark strip.
                        // KAWAII_GLASS_V049: clearer glass with a brighter specular sheen.
                        // EDGE_GLOSS_V050: only the chat-facing bottom edge is drawn.
                        // DIAGONAL_GLASS_V054: lens-like diagonal illumination, as if a
                        // soft source is grazing the glass from the upper-left.
                        modifier = Modifier
                            .background(
                                Brush.horizontalGradient(
                                    listOf(
                                        MaterialTheme.colorScheme.primary.copy(alpha = if (darkMode) 0.045f else 0.040f),
                                        Color.Transparent,
                                        MaterialTheme.colorScheme.secondary.copy(alpha = if (darkMode) 0.040f else 0.035f),
                                        Color.Transparent
                                    )
                                )
                            )
                            .background(
                                Brush.linearGradient(
                                    colors = listOf(
                                        Color.White.copy(alpha = if (darkMode) 0.34f else 0.48f),
                                        Color.White.copy(alpha = if (darkMode) 0.16f else 0.24f),
                                        Color.Transparent,
                                        Color.White.copy(alpha = if (darkMode) 0.035f else 0.055f)
                                    ),
                                    start = Offset(0f, -90f),
                                    end = Offset(1180f, 330f)
                                )
                            )
                            .background(
                                Brush.linearGradient(
                                    colors = listOf(
                                        Color.Transparent,
                                        Color.White.copy(alpha = if (darkMode) 0.04f else 0.07f),
                                        Color.White.copy(alpha = if (darkMode) 0.22f else 0.30f),
                                        Color.White.copy(alpha = if (darkMode) 0.07f else 0.11f),
                                        Color.Transparent
                                    ),
                                    start = Offset(80f, 250f),
                                    end = Offset(1320f, -90f)
                                )
                            )
                            .drawBehind {
                                drawLine(
                                    color = Color.White.copy(alpha = if (darkMode) 0.42f else 0.62f),
                                    start = Offset(0f, size.height - 0.5.dp.toPx()),
                                    end = Offset(size.width, size.height - 0.5.dp.toPx()),
                                    strokeWidth = 0.8.dp.toPx()
                                )
                            },
'''
    text = replace_once(text, old_top, new_top, "diagonal glass top bar")

    old_bottom = '''        Surface(
            // FINISH_V046: continuous composer band through the gesture/navigation area.
            // CANDY_GLASS_V048: transparent liquid-glass composer instead of a black slab.
            // KAWAII_GLASS_V049: more transparent with a glossy top highlight.
            // EDGE_GLOSS_V050: no side/bottom hairline; only the edge facing chat remains.
            color = Color.Transparent,
            contentColor = MaterialTheme.colorScheme.onSurface,
            tonalElevation = 0.dp,
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    Brush.horizontalGradient(
                        listOf(
                            MaterialTheme.colorScheme.primary.copy(alpha = 0.032f),
                            Color.Transparent,
                            MaterialTheme.colorScheme.secondary.copy(alpha = 0.030f)
                        )
                    )
                )
                .background(
                    Brush.verticalGradient(
                        listOf(
                            Color.White.copy(alpha = if (MaterialTheme.colorScheme.background.luminance() < 0.5f) 0.30f else 0.42f),
                            Color.White.copy(alpha = if (MaterialTheme.colorScheme.background.luminance() < 0.5f) 0.11f else 0.16f),
                            Color.Transparent,
                            Color.White.copy(alpha = 0.018f)
                        )
                    )
                )
                .background(
                    Brush.radialGradient(
                        colors = listOf(
                            Color.White.copy(alpha = if (MaterialTheme.colorScheme.background.luminance() < 0.5f) 0.20f else 0.30f),
                            Color.Transparent
                        ),
                        center = Offset(180f, -20f),
                        radius = 720f
                    )
                )
                .drawBehind {
                    drawLine(
                        color = Color.White.copy(alpha = 0.52f),
                        start = Offset(0f, 0.5.dp.toPx()),
                        end = Offset(size.width, 0.5.dp.toPx()),
                        strokeWidth = 0.7.dp.toPx()
                    )
                }
        ) {
'''

    new_bottom = '''        Surface(
            // FINISH_V046: continuous composer band through the gesture/navigation area.
            // CANDY_GLASS_V048: transparent liquid-glass composer instead of a black slab.
            // KAWAII_GLASS_V049: more transparent with a glossy top highlight.
            // EDGE_GLOSS_V050: no side/bottom hairline; only the edge facing chat remains.
            // DIAGONAL_GLASS_V054: diagonal lens sheen matching the top glass band.
            color = Color.Transparent,
            contentColor = MaterialTheme.colorScheme.onSurface,
            tonalElevation = 0.dp,
            modifier = Modifier
                .fillMaxWidth()
                .background(
                    Brush.horizontalGradient(
                        listOf(
                            MaterialTheme.colorScheme.primary.copy(alpha = 0.026f),
                            Color.Transparent,
                            MaterialTheme.colorScheme.secondary.copy(alpha = 0.024f)
                        )
                    )
                )
                .background(
                    Brush.linearGradient(
                        colors = listOf(
                            Color.White.copy(alpha = if (MaterialTheme.colorScheme.background.luminance() < 0.5f) 0.31f else 0.44f),
                            Color.White.copy(alpha = if (MaterialTheme.colorScheme.background.luminance() < 0.5f) 0.13f else 0.19f),
                            Color.Transparent,
                            Color.White.copy(alpha = 0.018f)
                        ),
                        start = Offset(0f, -60f),
                        end = Offset(1180f, 280f)
                    )
                )
                .background(
                    Brush.linearGradient(
                        colors = listOf(
                            Color.Transparent,
                            Color.White.copy(alpha = 0.035f),
                            Color.White.copy(alpha = if (MaterialTheme.colorScheme.background.luminance() < 0.5f) 0.18f else 0.27f),
                            Color.White.copy(alpha = 0.055f),
                            Color.Transparent
                        ),
                        start = Offset(70f, 240f),
                        end = Offset(1310f, -70f)
                    )
                )
                .drawBehind {
                    drawLine(
                        color = Color.White.copy(alpha = 0.58f),
                        start = Offset(0f, 0.5.dp.toPx()),
                        end = Offset(size.width, 0.5.dp.toPx()),
                        strokeWidth = 0.8.dp.toPx()
                    )
                }
        ) {
'''
    text = replace_once(text, old_bottom, new_bottom, "diagonal glass bottom bar")

    path.write_text(text, encoding="utf-8")
    print("Applied DIAGONAL_GLASS_V054: diagonal illuminated glass top/bottom bands")


if __name__ == "__main__":
    patch_ui()
