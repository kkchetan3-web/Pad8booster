package dev.padfinity.engine

/**
 * PADFINITY's internal window manager.
 *
 * This is a real window manager for *our own* surfaces: it owns z-order, focus,
 * geometry, snapping, tiling and window lifecycle. It does not, and cannot,
 * manage other applications' windows — Android gives third-party apps no such
 * API. External apps are represented as [WindowKind.SYSTEM_APP] entries in the
 * taskbar and are launched through the OS (see the Shizuku path in the docs).
 *
 * Invariants maintained by every mutator:
 *  - z-order is `windows` order, last element on top;
 *  - [focusedId] is always a live, non-minimised window or null;
 *  - no window is ever left entirely outside [workspaceBounds].
 */
class WindowManager(workspaceBounds: Rect) {

    var workspaceBounds: Rect = workspaceBounds
        private set

    private val _windows = mutableListOf<Window>()
    private val focusHistory = ArrayDeque<String>()

    val windows: List<Window> get() = _windows.toList()

    val focusedId: String? get() = focusHistory.firstOrNull { id -> _windows.any { it.id == id } }

    val focused: Window? get() = focusedId?.let { id -> _windows.firstOrNull { it.id == id } }

    val visibleWindows: List<Window> get() = _windows.filter { it.isVisible }

    fun window(id: String): Window? = _windows.firstOrNull { it.id == id }

    fun resizeWorkspace(bounds: Rect) {
        workspaceBounds = bounds
        for (i in _windows.indices) {
            val w = _windows[i]
            val target = if (w.mode == WindowMode.MAXIMIZED) {
                bounds
            } else {
                // Keep proportional position, then guarantee reachability.
                w.bounds.clampedInto(reachableBounds())
            }
            _windows[i] = w.copy(bounds = target)
        }
    }

    // ----------------------------------------------------------------- open

    fun open(
        id: String,
        title: String,
        kind: WindowKind = WindowKind.INTERNAL,
        bounds: Rect? = null,
        surfaceRoute: String? = null,
        packageName: String? = null,
        minWidth: Int = 320,
        minHeight: Int = 220
    ): Window {
        _windows.firstOrNull { it.id == id }?.let { existing ->
            focus(id)
            return existing
        }
        val placed = (bounds ?: cascadeSlot(_windows.size)).clampedInto(reachableBounds())
        val created = Window(
            id = id,
            title = title,
            kind = kind,
            bounds = placed,
            minWidth = minWidth,
            minHeight = minHeight,
            surfaceRoute = surfaceRoute,
            packageName = packageName
        )
        _windows.add(created)
        pushFocus(id)
        return created
    }

    fun close(id: String): Boolean {
        val removed = _windows.removeAll { it.id == id }
        focusHistory.removeAll { it == id }
        return removed
    }

    // ---------------------------------------------------------------- focus

    fun focus(id: String): Boolean {
        val w = window(id) ?: return false
        if (!w.isVisible) return false
        // Raising is part of focusing: a focused window must be on top.
        _windows.removeAll { it.id == id }
        _windows.add(w)
        pushFocus(id)
        return true
    }

    fun raise(id: String): Boolean = focus(id)

    /** MRU list of live windows, most recently focused first. */
    fun mru(): List<String> =
        focusHistory.filter { id -> _windows.any { it.id == id && it.isVisible } }

    /** Alt-Tab: move focus to the next window in MRU order (wrapping). */
    fun cycleFocus(reverse: Boolean = false): String? {
        val order = mru()
        if (order.size < 2) return order.firstOrNull()
        val next = if (reverse) order[order.size - 1] else order[1]
        focus(next)
        return next
    }

    private fun pushFocus(id: String) {
        focusHistory.removeAll { it == id }
        focusHistory.addFirst(id)
    }

    private fun nextFocusCandidate(excluding: String): String? =
        mru().firstOrNull { it != excluding }

    // ------------------------------------------------------------- geometry

    private fun reachableBounds(): Rect = workspaceBounds

    /**
     * Guarantee the window can always be grabbed again: its title bar must stay
     * inside the workspace and at least [MIN_VISIBLE_W] px of the window must
     * remain horizontally reachable.
     */
    private fun clampPosition(rect: Rect): Rect {
        val w = workspaceBounds
        val minVisibleW = minOf(MIN_VISIBLE_W, rect.width)
        val x = rect.left.coerceIn(w.left - rect.width + minVisibleW, w.right - minVisibleW)
        val y = rect.top.coerceIn(w.top, w.bottom - MIN_VISIBLE_TITLEBAR)
        return rect.offset(x - rect.left, y - rect.top)
    }

    fun setBounds(id: String, bounds: Rect): Boolean {
        val index = _windows.indexOfFirst { it.id == id }
        if (index < 0) return false
        val current = _windows[index]
        val sized = Rect(
            bounds.left,
            bounds.top,
            maxOf(bounds.left + current.minWidth, bounds.right),
            maxOf(bounds.top + current.minHeight, bounds.bottom)
        )
        _windows[index] = current.copy(bounds = sized.clampedInto(workspaceBounds))
        return true
    }

    fun moveBy(id: String, dx: Int, dy: Int): Boolean {
        val w = window(id) ?: return false
        if (w.mode == WindowMode.MAXIMIZED) return false
        val moved = clampPosition(w.bounds.offset(dx, dy))
        return setBounds(id, moved)
    }

    fun resizeBy(id: String, dx: Int, dy: Int): Boolean {
        val w = window(id) ?: return false
        if (w.mode == WindowMode.MAXIMIZED) return false
        val target = Rect(
            w.bounds.left, w.bounds.top,
            (w.bounds.right + dx).coerceAtLeast(w.bounds.left + w.minWidth),
            (w.bounds.bottom + dy).coerceAtLeast(w.bounds.top + w.minHeight)
        )
        return setBounds(id, target.clampedInto(workspaceBounds))
    }

    // -------------------------------------------------------------- lifecycle

    fun minimize(id: String): Boolean {
        val index = _windows.indexOfFirst { it.id == id }
        if (index < 0) return false
        val w = _windows[index]
        if (!w.isVisible) return false
        _windows[index] = w.copy(
            mode = WindowMode.MINIMIZED,
            restoreBounds = if (w.mode == WindowMode.MAXIMIZED) w.restoreBounds else w.bounds
        )
        val next = nextFocusCandidate(id)
        focusHistory.removeAll { it == id }
        if (next != null) focus(next)
        return true
    }

    fun maximize(id: String): Boolean {
        val index = _windows.indexOfFirst { it.id == id }
        if (index < 0) return false
        val w = _windows[index]
        if (w.mode == WindowMode.MAXIMIZED) return false
        _windows[index] = w.copy(
            bounds = workspaceBounds,
            mode = WindowMode.MAXIMIZED,
            restoreBounds = if (w.mode == WindowMode.NORMAL) w.bounds else w.restoreBounds
        )
        focus(id)
        return true
    }

    fun toggleMaximize(id: String): Boolean {
        val w = window(id) ?: return false
        return if (w.mode == WindowMode.MAXIMIZED) restore(id) else maximize(id)
    }

    fun restore(id: String): Boolean {
        val index = _windows.indexOfFirst { it.id == id }
        if (index < 0) return false
        val w = _windows[index]
        val target = (w.restoreBounds ?: cascadeSlot(_windows.size)).clampedInto(workspaceBounds)
        _windows[index] = w.copy(bounds = target, mode = WindowMode.NORMAL, restoreBounds = null)
        focus(id)
        return true
    }

    // ---------------------------------------------------------------- snapping

    /**
     * Compute snapped bounds for [zone] inside the workspace.
     * [ratio] is the share given to the first side of a split, constrained to
     * 0.2..0.8 so a snapped window is always usable.
     */
    fun snappedBounds(zone: SnapZone, ratio: Float = 0.5f): Rect {
        val b = workspaceBounds
        val r = ratio.coerceIn(0.2f, 0.8f)
        val splitX = b.left + (b.width * r).toInt()
        val splitY = b.top + (b.height * r).toInt()
        val halfX = b.left + b.width / 2
        val halfY = b.top + b.height / 2
        return when (zone) {
            SnapZone.LEFT -> Rect(b.left, b.top, splitX, b.bottom)
            SnapZone.RIGHT -> Rect(b.right - (b.width * r).toInt(), b.top, b.right, b.bottom)
            SnapZone.TOP -> Rect(b.left, b.top, b.right, splitY)
            SnapZone.BOTTOM -> Rect(b.left, b.bottom - (b.height * r).toInt(), b.right, b.bottom)
            SnapZone.TOP_LEFT -> Rect(b.left, b.top, halfX, halfY)
            SnapZone.TOP_RIGHT -> Rect(halfX, b.top, b.right, halfY)
            SnapZone.BOTTOM_LEFT -> Rect(b.left, halfY, halfX, b.bottom)
            SnapZone.BOTTOM_RIGHT -> Rect(halfX, halfY, b.right, b.bottom)
        }
    }

    fun snap(id: String, zone: SnapZone, ratio: Float = 0.5f): Boolean {
        val index = _windows.indexOfFirst { it.id == id }
        if (index < 0) return false
        val w = _windows[index]
        val previousNormal = if (w.mode == WindowMode.MAXIMIZED) w.restoreBounds else w.bounds
        _windows[index] = w.copy(
            bounds = snappedBounds(zone, ratio),
            mode = WindowMode.NORMAL,
            restoreBounds = previousNormal,
            snapZone = zone
        )
        focus(id)
        return true
    }

    /** Which snap zone (if any) a dragged rect is hovering over. */
    fun snapZoneFor(dragged: Rect, threshold: Int = 56): SnapZone? {
        val b = workspaceBounds
        val nearLeft = dragged.left <= b.left + threshold
        val nearRight = dragged.right >= b.right - threshold
        val nearTop = dragged.top <= b.top + threshold
        val nearBottom = dragged.bottom >= b.bottom - threshold
        return when {
            nearTop && nearLeft -> SnapZone.TOP_LEFT
            nearTop && nearRight -> SnapZone.TOP_RIGHT
            nearBottom && nearLeft -> SnapZone.BOTTOM_LEFT
            nearBottom && nearRight -> SnapZone.BOTTOM_RIGHT
            nearLeft -> SnapZone.LEFT
            nearRight -> SnapZone.RIGHT
            nearTop -> SnapZone.TOP
            nearBottom -> SnapZone.BOTTOM
            else -> null
        }
    }

    /** Live feedback while dragging: the bounds the window will land on. */
    fun snapPreview(dragged: Rect, threshold: Int = 56): DragResult? {
        val zone = snapZoneFor(dragged, threshold) ?: return null
        return DragResult(_windows.toList(), snappedBounds(zone), zone)
    }

    // --------------------------------------------------------------- tiling

    /**
     * Arrange visible windows. Returns the number of windows re-laid-out.
     * [focusedFirst] honours the common desktop convention that the active
     * window receives the dominant region (MAIN_AND_STACK).
     */
    fun tile(layout: TileLayout, ratio: Float = 0.5f): Int {
        val targets = visibleWindows
        if (targets.isEmpty()) return 0
        val b = workspaceBounds
        val r = ratio.coerceIn(0.2f, 0.8f)
        val ordered = if (layout == TileLayout.MAIN_AND_STACK) {
            val focus = focusedId
            targets.sortedByDescending { it.id == focus }
        } else targets

        when (layout) {
            TileLayout.CASCADE -> return cascade()
            TileLayout.TWO_COLUMNS, TileLayout.THREE_COLUMNS -> {
                val columns = if (layout == TileLayout.TWO_COLUMNS) 2 else 3
                val colWidth = b.width / columns
                ordered.forEachIndexed { index, w ->
                    val col = index % columns
                    val left = b.left + col * colWidth
                    val right = if (col == columns - 1) b.right else left + colWidth
                    setBounds(w.id, Rect(left, b.top, right, b.bottom))
                }
            }
            TileLayout.GRID_2X2 -> {
                val cells = 4
                val cw = b.width / 2
                val ch = b.height / 2
                ordered.forEachIndexed { index, w ->
                    val cell = index % cells
                    val cx = b.left + (cell % 2) * cw
                    val cy = b.top + (cell / 2) * ch
                    val right = if (cell % 2 == 1) b.right else cx + cw
                    val bottom = if (cell / 2 == 1) b.bottom else cy + ch
                    setBounds(w.id, Rect(cx, cy, right, bottom))
                }
            }
            TileLayout.MAIN_AND_STACK -> {
                val splitX = b.left + (b.width * 0.62f).toInt()
                val rest = ordered.drop(1)
                ordered.firstOrNull()?.let {
                    setBounds(it.id, Rect(b.left, b.top, splitX, b.bottom))
                }
                if (rest.isNotEmpty()) {
                    val slice = (b.bottom - b.top) / rest.size
                    rest.forEachIndexed { index, w ->
                        val top = b.top + index * slice
                        val bottom = if (index == rest.size - 1) b.bottom else top + slice
                        setBounds(w.id, Rect(splitX, top, b.right, bottom))
                    }
                }
            }
        }
        return ordered.size
    }

    /** Classic desktop cascade: each window offset from the previous. */
    fun cascade(step: Int = 48): Int {
        val b = workspaceBounds
        var count = 0
        visibleWindows.forEachIndexed { index, w ->
            val offset = step * index
            val target = Rect(
                b.left + offset,
                b.top + offset,
                minOf(b.right, b.left + offset + (b.width * 0.7f).toInt()),
                minOf(b.bottom, b.top + offset + (b.height * 0.7f).toInt())
            )
            if (setBounds(w.id, target)) count++
        }
        return count
    }

    private fun cascadeSlot(index: Int): Rect {
        val b = workspaceBounds
        val offset = (CASCADE_STEP * (index % 8))
        return Rect(
            b.left + offset,
            b.top + offset,
            minOf(b.right, b.left + offset + b.width * 2 / 3),
            minOf(b.bottom, b.top + offset + b.height * 2 / 3)
        )
    }

    /** Topmost visible window containing the point — hit testing for input. */
    fun topmostAt(x: Int, y: Int): Window? =
        _windows.lastOrNull { it.isVisible && it.bounds.contains(x, y) }

    /** Restore-on-launch support: snapshot every window's geometry. */
    fun snapshotGeometry(): Map<String, Rect> =
        _windows.associate { it.id to it.bounds }

    companion object {
        const val CASCADE_STEP = 48
        const val MIN_VISIBLE_W = 160
        const val MIN_VISIBLE_TITLEBAR = 56
    }
}
