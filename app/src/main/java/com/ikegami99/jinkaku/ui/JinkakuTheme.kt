package com.ikegami99.jinkaku.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

private val JinkakuLightColors = lightColorScheme(
    primary = Color(0xFF6E5AE6),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFEAE5FF),
    onPrimaryContainer = Color(0xFF24194F),
    secondary = Color(0xFF4F6478),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE7EDF3),
    onSecondaryContainer = Color(0xFF17232E),
    tertiary = Color(0xFF147D70),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFBDF3E8),
    onTertiaryContainer = Color(0xFF00201B),
    background = Color(0xFFF7F7FA),
    onBackground = Color(0xFF19191F),
    surface = Color(0xFFF7F7FA),
    onSurface = Color(0xFF19191F),
    surfaceVariant = Color(0xFFECECF2),
    onSurfaceVariant = Color(0xFF60606A),
    outline = Color(0xFFC8C7D0),
    outlineVariant = Color(0xFFE1E0E7)
)

private val JinkakuDarkColors = darkColorScheme(
    primary = Color(0xFFB9A7FF),
    onPrimary = Color(0xFF2D1F78),
    primaryContainer = Color(0xFF3C2E82),
    onPrimaryContainer = Color(0xFFE9E3FF),
    secondary = Color(0xFFBCC9D6),
    onSecondary = Color(0xFF25313D),
    secondaryContainer = Color(0xFF303B47),
    onSecondaryContainer = Color(0xFFD8E4F0),
    tertiary = Color(0xFF79D8C8),
    onTertiary = Color(0xFF00382F),
    tertiaryContainer = Color(0xFF005044),
    onTertiaryContainer = Color(0xFF9AF4E2),
    background = Color(0xFF0F1014),
    onBackground = Color(0xFFE8E7EE),
    surface = Color(0xFF0F1014),
    onSurface = Color(0xFFE8E7EE),
    surfaceVariant = Color(0xFF1B1C22),
    onSurfaceVariant = Color(0xFFB9B8C2),
    outline = Color(0xFF55545D),
    outlineVariant = Color(0xFF2A2B31)
)

private val JinkakuShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(18.dp),
    large = RoundedCornerShape(24.dp),
    extraLarge = RoundedCornerShape(32.dp)
)

@Composable
fun JinkakuTheme(darkMode: Boolean, content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (darkMode) JinkakuDarkColors else JinkakuLightColors,
        shapes = JinkakuShapes,
        content = content
    )
}
