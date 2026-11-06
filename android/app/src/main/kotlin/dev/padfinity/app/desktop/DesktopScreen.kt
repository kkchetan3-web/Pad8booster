package dev.padfinity.app.desktop

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import dev.padfinity.app.launcher.LauncherOverlay
import dev.padfinity.app.taskbar.PadfinityTaskbar
import dev.padfinity.app.ui.theme.LocalAccent
import dev.padfinity.engine.Rect
import dev.padfinity.engine.Window
import dev.padfinity.engine.WindowMode
import kotlin.math.roundToInt

/**
 * The desktop surface.
 *
 * Coordinate systems: the engine works in pixels, Compose in dp. Conversion
 * happens exactly once here, at the boundary, so the engine never needs a
 * `Density` and stays unit-testable on a plain JVM.
 */
@Composable
fun DesktopScreen(viewModel: DesktopViewModel) {
    val density = LocalDensity.current
    val accent = LocalAccent.current
    var launcherOpen by remember { mutableStateOf(false) }

    BoxWithConstraints(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(
                        MaterialTheme.colorScheme.background,
                        MaterialTheme.colorScheme.surfaceVariant
                    )
                )
            )
    ) {
        val widthPx = with(density) { maxWidth.toPx().roundToInt() }
        val heightPx = with(density) { maxHeight.toPx().roundToInt() }

        LaunchedEffect(widthPx, heightPx) {
            viewModel.onWorkspaceBounds(Rect.of(0, 0, widthPx, heightPx))
        }

        // Windows, bottom of z-order first.
        viewModel.windows.forEach { window ->
            key(window.id) {
                if (window.mode != WindowMode.MINIMIZED) {
                    WindowSurface(
                        window = window,
                        focused = window.id == viewModel.focusedId,
                        onFocus = { viewModel.focus(window.id) },
                        onDrag = { dx, dy -> viewModel.moveBy(window.id, dx, dy) },
                        onDragStart = { viewModel.updateSnapPreview(window.bounds) },
                        onDragEnd = { viewModel.endDrag(window.id) },
                        onResize = { dx, dy -> viewModel.resizeBy(window.id, dx, dy) },
                        onClose = { viewModel.close(window.id) },
                        onMinimize = { viewModel.minimize(window.id) },
                        onMaximize = { viewModel.toggleMaximize(window.id) }
                    )
                }
            }
        }

        // Snap preview: shown while dragging near an edge, before release.
        viewModel.snapPreview?.let { preview ->
            Box(
                modifier = Modifier
                    .offsetPx(preview, density)
                    .size(
                        with(density) { preview.width.toDp() },
                        with(density) { preview.height.toDp() }
                    )
                    .clip(RoundedCornerShape(10.dp))
                    .background(accent.primary.copy(alpha = 0.10f))
                    .border(1.dp, accent.primary.copy(alpha = 0.45f), RoundedCornerShape(10.dp))
            )
        }

        PadfinityTaskbar(
            viewModel = viewModel,
            modifier = Modifier.align(Alignment.BottomCenter),
            onOpenLauncher = { launcherOpen = true }
        )

        if (launcherOpen) {
            LauncherOverlay(
                onDismiss = { launcherOpen = false },
                onOpenApp = { pkg, label ->
                    viewModel.openSystemApp(pkg, label)
                    launcherOpen = false
                }
            )
        }
    }
}

@Composable
private fun WindowSurface(
    window: Window,
    focused: Boolean,
    onFocus: () -> Unit,
    onDrag: (Int, Int) -> Unit,
    onDragStart: () -> Unit,
    onDragEnd: () -> Unit,
    onResize: (Int, Int) -> Unit,
    onClose: () -> Unit,
    onMinimize: () -> Unit,
    onMaximize: () -> Unit
) {
    val density = LocalDensity.current
    val accent = LocalAccent.current
    val shape = RoundedCornerShape(10.dp)

    Column(
        modifier = Modifier
            .offsetPx(window.bounds, density)
            .size(
                with(density) { window.bounds.width.toDp() },
                with(density) { window.bounds.height.toDp() }
            )
            .clip(shape)
            .background(MaterialTheme.colorScheme.surface)
            .border(
                width = if (focused) 1.dp else 1.dp,
                color = if (focused) accent.primary.copy(alpha = 0.55f)
                else MaterialTheme.colorScheme.outline,
                shape = shape
            )
    ) {
        // ---- title bar: drag handle, double-tap to maximise -----------------
        Row(
            modifier = Modifier
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .pointerInput(window.id, window.mode) {
                    detectDragGestures(
                        onDragStart = { onFocus(); onDragStart() },
                        onDragEnd = { onDragEnd() },
                        onDrag = { change, delta ->
                            change.consume()
                            onDrag(delta.x.roundToInt(), delta.y.roundToInt())
                        }
                    )
                }
                .padding(horizontal = 10.dp, vertical = 7.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = window.title,
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f)
            )
            WindowButton("–", onMinimize)
            WindowButton(if (window.mode == WindowMode.MAXIMIZED) "❐" else "□", onMaximize)
            WindowButton("×", onClose)
        }

        // ---- content ---------------------------------------------------------
        Box(modifier = Modifier.weight(1f).fillMaxSize()) {
            WindowContent(window)
            // resize grip
            Box(
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .size(18.dp)
                    .pointerInput(window.id, window.mode) {
                        detectDragGestures { change, delta ->
                            change.consume()
                            onResize(delta.x.roundToInt(), delta.y.roundToInt())
                        }
                    }
                    .background(accent.primary.copy(alpha = 0.18f))
            )
        }
    }
}

@Composable
private fun WindowButton(label: String, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .size(22.dp)
            .clip(RoundedCornerShape(5.dp))
            .background(MaterialTheme.colorScheme.surface)
            .androidxClickable(onClick),
        contentAlignment = Alignment.Center
    ) {
        Text(label, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
private fun WindowContent(window: Window) {
    when (window.surfaceRoute) {
        "notes" -> NoteSurface()
        "insights" -> InsightsSurface()
        null -> Text(
            text = "System app: ${window.packageName ?: "unknown"}\n" +
                "Opened as a taskbar entry. PADFINITY does not render other apps' " +
                "windows — it launches them (see DEVICE_RESEARCH.md §2.3).",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(14.dp)
        )
        else -> Text(
            text = "Surface '${window.surfaceRoute}' is not implemented yet.",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.padding(14.dp)
        )
    }
}
