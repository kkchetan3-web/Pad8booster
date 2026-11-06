package dev.padfinity.engine

/** Lifecycle state of a PADFINITY window. */
enum class WindowMode { NORMAL, MINIMIZED, MAXIMIZED }

/**
 * How a window's content is provided.
 *
 * This distinction is load-bearing for honesty: the app must never present a
 * simulated surface as a real Android system window.
 *
 * - [INTERNAL]  A PADFINITY surface (notes, files, insights, settings…). Fully
 *               controlled by our own window engine.
 * - [SYSTEM_APP] A real installed Android application, shown as a taskbar entry
 *               and optionally launched into a real freeform window via Shizuku.
 *               It is *not* rendered inside our engine.
 */
enum class WindowKind { INTERNAL, SYSTEM_APP }

/**
 * An immutable window record. All mutations go through [WindowManager], which
 * returns new state — no hidden mutation, no observer races.
 */
data class Window(
    val id: String,
    val title: String,
    val kind: WindowKind = WindowKind.INTERNAL,
    val bounds: Rect,
    val mode: WindowMode = WindowMode.NORMAL,
    val restoreBounds: Rect? = null,
    val snapZone: SnapZone? = null,
    val minWidth: Int = 320,
    val minHeight: Int = 220,
    /** Package name for [WindowKind.SYSTEM_APP] entries. */
    val packageName: String? = null,
    /** Fixed so a restart restores the same surface. */
    val surfaceRoute: String? = null
) {
    val isVisible: Boolean get() = mode != WindowMode.MINIMIZED
}

/** Result of a drag/resize gesture that may have entered a snap zone. */
data class DragResult(
    val windows: List<Window>,
    val previewBounds: Rect?,
    val previewZone: SnapZone?
)
