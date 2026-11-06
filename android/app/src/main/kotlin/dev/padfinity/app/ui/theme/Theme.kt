package dev.padfinity.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * PADFINITY design system.
 *
 * Identity: "quiet instrument" — graphite surfaces, one living accent, hairline
 * borders, generous spacing, numbers in a tabular monospace. It should read as a
 * tool, not a toy: no gradients-for-decoration, no glow, no rounded-everything.
 *
 * The accent is per-workspace (see [PadfinityAccent]) so switching workspace is
 * felt as well as seen.
 */
data class PadfinityAccent(val primary: Color, val soft: Color)

val defaultAccent = PadfinityAccent(
    primary = Color(0xFF4ADE80),
    soft = Color(0xFF1B3A2A)
)

val LocalAccent = staticCompositionLocalOf { defaultAccent }

private val Graphite = Color(0xFF0B0D0F)
private val Panel = Color(0xFF13171A)
private val PanelHigh = Color(0xFF181D21)
private val Hairline = Color(0xFF242B30)
private val Ink = Color(0xFFE6ECEF)
private val InkMuted = Color(0xFF8A9AA3)

val PadfinityTypography = Typography(
    displayLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 34.sp),
    titleLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.SemiBold, fontSize = 20.sp),
    titleMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontWeight = FontWeight.Medium, fontSize = 15.sp),
    bodyLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 14.sp),
    bodyMedium = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 13.sp),
    labelLarge = TextStyle(fontFamily = FontFamily.SansSerif, fontSize = 12.sp, letterSpacing = 0.4.sp),
    // Numeric readouts: tabular monospace prevents jitter while values change.
    labelSmall = TextStyle(fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = InkMuted)
)

private val darkScheme = darkColorScheme(
    primary = defaultAccent.primary,
    onPrimary = Color(0xFF04120A),
    primaryContainer = defaultAccent.soft,
    background = Graphite,
    onBackground = Ink,
    surface = Panel,
    onSurface = Ink,
    surfaceVariant = PanelHigh,
    onSurfaceVariant = InkMuted,
    outline = Hairline,
    outlineVariant = Hairline,
    error = Color(0xFFF87171)
)

private val lightScheme = lightColorScheme(
    primary = Color(0xFF16653A),
    background = Color(0xFFF7F8F7),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF101413),
    outline = Color(0xFFDDE2DF)
)

@Composable
fun PadfinityTheme(
    darkTheme: Boolean = true,
    accent: PadfinityAccent = defaultAccent,
    content: @Composable () -> Unit
) {
    androidx.compose.runtime.CompositionLocalProvider(LocalAccent provides accent) {
        MaterialTheme(
            colorScheme = if (darkTheme) darkScheme.copy(primary = accent.primary, primaryContainer = accent.soft)
            else lightScheme.copy(primary = accent.primary),
            typography = PadfinityTypography,
            content = content
        )
    }
}

/** Accent palettes available per workspace. All chosen to survive an LCD at low brightness. */
object Accents {
    val mint = PadfinityAccent(Color(0xFF4ADE80), Color(0xFF1B3A2A))
    val amber = PadfinityAccent(Color(0xFFFBBF24), Color(0xFF3A2E0B))
    val azure = PadfinityAccent(Color(0xFF60A5FA), Color(0xFF12233A))
    val magenta = PadfinityAccent(Color(0xFFF472B6), Color(0xFF3A1226))
    val all = listOf(mint, amber, azure, magenta)
}
