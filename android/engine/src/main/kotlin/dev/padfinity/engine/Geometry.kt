package dev.padfinity.engine

/**
 * Pixel geometry for the PADFINITY desktop surface.
 *
 * Deliberately dependency-free: no `android.graphics.Rect`, so the entire window
 * engine compiles and runs on a plain JVM and can be unit-tested without an
 * emulator. The Compose layer converts these to `Dp`/`Rect` at the boundary.
 */
data class Rect(val left: Int, val top: Int, val right: Int, val bottom: Int) {

    val width: Int get() = right - left
    val height: Int get() = bottom - top

    val isEmpty: Boolean get() = width <= 0 || height <= 0

    fun offset(dx: Int, dy: Int): Rect =
        Rect(left + dx, top + dy, right + dx, bottom + dy)

    /** Translate this rect so it sits fully inside [container] without resizing. */
    fun clampedInto(container: Rect): Rect {
        val w = width.coerceAtMost(container.width)
        val h = height.coerceAtMost(container.height)
        val x = left.coerceIn(container.left, container.right - w)
        val y = top.coerceIn(container.top, container.bottom - h)
        return Rect(x, y, x + w, y + h)
    }

    /** Fraction of this rect's area that overlaps [other]. 0.0 .. 1.0 */
    fun overlapFractionOf(other: Rect): Float {
        val ix = maxOf(0, minOf(right, other.right) - maxOf(left, other.left))
        val iy = maxOf(0, minOf(bottom, other.bottom) - maxOf(top, other.top))
        val otherArea = other.width.toLong() * other.height
        if (otherArea <= 0L) return 0f
        return ((ix.toLong() * iy).toFloat() / otherArea).coerceIn(0f, 1f)
    }

    fun contains(px: Int, py: Int): Boolean =
        px >= left && px < right && py >= top && py < bottom

    override fun toString(): String = "Rect($left,$top ${width}x$height)"

    companion object {
        fun of(x: Int, y: Int, w: Int, h: Int): Rect = Rect(x, y, x + w, y + h)
    }
}

/** Snapping target for drag-to-edge behaviour. */
enum class SnapZone {
    LEFT, RIGHT, TOP, BOTTOM,
    TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT;

    val isQuadrant: Boolean
        get() = this == TOP_LEFT || this == TOP_RIGHT ||
            this == BOTTOM_LEFT || this == BOTTOM_RIGHT
}

/** Tiling strategies for "arrange windows" commands. */
enum class TileLayout {
    TWO_COLUMNS, THREE_COLUMNS, GRID_2X2, MAIN_AND_STACK, CASCADE
}
