package dev.padfinity.engine

/** User-facing metadata for one workspace. */
data class WorkspaceMeta(
    val id: String,
    val name: String,
    val wallpaperId: String = "wallpaper.default",
    val accentArgb: Long = 0xFF4ADE80,
    val pinnedPackages: List<String> = emptyList(),
    val surfaceRoutes: List<String> = emptyList()
)

/**
 * Owns one [WindowManager] per workspace so switching workspaces preserves each
 * one's window layout independently — the "remember my last configuration"
 * requirement. A workspace is never created empty: [WorkspaceManager] refuses to
 * remove the last one.
 */
class WorkspaceManager(workspaceBounds: Rect) {

    private val managers = LinkedHashMap<String, WindowManager>()
    private val metas = LinkedHashMap<String, WorkspaceMeta>()

    var activeId: String = ""
        private set

    init {
        val first = WorkspaceMeta(id = "workspace.personal", name = "Personal")
        metas[first.id] = first
        managers[first.id] = WindowManager(workspaceBounds)
        activeId = first.id
    }

    val active: WindowManager get() = managers.getValue(activeId)
    val activeMeta: WorkspaceMeta get() = metas.getValue(activeId)

    fun ids(): List<String> = metas.keys.toList()
    fun meta(id: String): WorkspaceMeta? = metas[id]
    fun managerOf(id: String): WindowManager? = managers[id]

    fun add(meta: WorkspaceMeta): Boolean {
        if (metas.containsKey(meta.id)) return false
        metas[meta.id] = meta
        managers[meta.id] = WindowManager(active.workspaceBounds)
        return true
    }

    fun updateMeta(meta: WorkspaceMeta): Boolean {
        if (!metas.containsKey(meta.id)) return false
        metas[meta.id] = meta
        return true
    }

    /** Removing the active workspace activates its neighbour. Never removes the last. */
    fun remove(id: String): Boolean {
        if (metas.size <= 1 || !metas.containsKey(id)) return false
        val wasActive = id == activeId
        metas.remove(id)
        managers.remove(id)
        if (wasActive) activeId = metas.keys.first()
        return true
    }

    fun switchTo(id: String): Boolean {
        if (!metas.containsKey(id)) return false
        activeId = id
        return true
    }

    fun resizeAll(bounds: Rect) {
        managers.values.forEach { it.resizeWorkspace(bounds) }
    }

    /** Total open windows across every workspace — used by the taskbar badge. */
    fun totalOpenWindows(): Int = managers.values.sumOf { it.visibleWindows.size }

    fun snapshot(): DesktopSnapshot = DesktopSnapshot(
        activeId = activeId,
        workspaces = metas.values.toList(),
        windows = managers.entries.associate { (id, wm) -> id to wm.windows }
    )

    fun restore(snapshot: DesktopSnapshot, bounds: Rect): Boolean {
        if (snapshot.workspaces.isEmpty()) return false
        metas.clear()
        managers.clear()
        snapshot.workspaces.forEach { meta ->
            metas[meta.id] = meta
            val wm = WindowManager(bounds)
            snapshot.windows[meta.id]?.forEach { w ->
                wm.open(
                    id = w.id,
                    title = w.title,
                    kind = w.kind,
                    bounds = w.bounds,
                    surfaceRoute = w.surfaceRoute,
                    packageName = w.packageName,
                    minWidth = w.minWidth,
                    minHeight = w.minHeight
                )
                when (w.mode) {
                    WindowMode.MAXIMIZED -> wm.maximize(w.id)
                    WindowMode.MINIMIZED -> wm.minimize(w.id)
                    WindowMode.NORMAL -> Unit
                }
            }
            managers[meta.id] = wm
        }
        activeId = if (metas.containsKey(snapshot.activeId)) snapshot.activeId else metas.keys.first()
        return true
    }
}

/** Serializable state of the whole desktop. */
data class DesktopSnapshot(
    val activeId: String,
    val workspaces: List<WorkspaceMeta>,
    val windows: Map<String, List<Window>>
)

/**
 * Deterministic line-oriented persistence.
 *
 * Hand-rolled rather than kotlinx.serialization because the engine module must
 * have **zero** dependencies so it can be compiled and tested on a bare JVM.
 * Values are escaped, so titles containing separators or newlines round-trip.
 */
object DesktopCodec {

    private const val HEADER = "PADFINITY-DESKTOP v1"

    fun encode(snapshot: DesktopSnapshot): String = buildString {
        appendLine(HEADER)
        appendLine("active=${escape(snapshot.activeId)}")
        snapshot.workspaces.forEach { meta ->
            appendLine(
                "ws=${escape(meta.id)}|${escape(meta.name)}|${escape(meta.wallpaperId)}|" +
                    "${meta.accentArgb}|${meta.pinnedPackages.joinToString(",") { escape(it) }}|" +
                    meta.surfaceRoutes.joinToString(",") { escape(it) }
            )
            snapshot.windows[meta.id].orEmpty().forEach { w ->
                appendLine(
                    "win=${escape(meta.id)}|${escape(w.id)}|${escape(w.title)}|${w.kind.name}|" +
                        "${w.bounds.left},${w.bounds.top},${w.bounds.right},${w.bounds.bottom}|" +
                        "${w.mode.name}|${w.snapZone?.name ?: "-"}|${escape(w.packageName ?: "-")}|" +
                        "${escape(w.surfaceRoute ?: "-")}|${w.minWidth}|${w.minHeight}"
                )
            }
        }
    }

    fun decode(text: String): DesktopSnapshot? {
        val lines = text.lines().filter { it.isNotBlank() }
        if (lines.firstOrNull()?.trim() != HEADER) return null
        var activeId = ""
        val metas = mutableListOf<WorkspaceMeta>()
        val windows = mutableMapOf<String, MutableList<Window>>()
        for (line in lines.drop(1)) {
            when {
                line.startsWith("active=") -> activeId = unescape(line.removePrefix("active="))
                line.startsWith("ws=") -> {
                    val f = splitEscaped(line.removePrefix("ws="))
                    if (f.size < 6) return null
                    metas += WorkspaceMeta(
                        id = f[0],
                        name = f[1],
                        wallpaperId = f[2],
                        accentArgb = f[3].toLongOrNull() ?: 0xFF4ADE80,
                        pinnedPackages = if (f[4].isBlank()) emptyList()
                        else f[4].split(",").filter { it.isNotBlank() },
                        surfaceRoutes = if (f[5].isBlank()) emptyList()
                        else f[5].split(",").filter { it.isNotBlank() }
                    )
                }
                line.startsWith("win=") -> {
                    val f = splitEscaped(line.removePrefix("win="))
                    if (f.size < 10) return null
                    val rectParts = f[4].split(",").mapNotNull { it.toIntOrNull() }
                    if (rectParts.size != 4) return null
                    val window = Window(
                        id = f[1],
                        title = f[2],
                        kind = runCatching { WindowKind.valueOf(f[3]) }.getOrDefault(WindowKind.INTERNAL),
                        bounds = Rect(rectParts[0], rectParts[1], rectParts[2], rectParts[3]),
                        mode = runCatching { WindowMode.valueOf(f[5]) }.getOrDefault(WindowMode.NORMAL),
                        snapZone = f[6].takeIf { it != "-" }?.let {
                            runCatching { SnapZone.valueOf(it) }.getOrNull()
                        },
                        packageName = f[7].takeIf { it != "-" },
                        surfaceRoute = f[8].takeIf { it != "-" },
                        minWidth = f[9].toIntOrNull() ?: 320,
                        minHeight = f.getOrNull(10)?.toIntOrNull() ?: 220
                    )
                    windows.getOrPut(f[0]) { mutableListOf() } += window
                }
            }
        }
        if (metas.isEmpty()) return null
        if (activeId.isBlank() || metas.none { it.id == activeId }) activeId = metas.first().id
        // Guarantee an entry for every declared workspace so consumers never have
        // to distinguish "no windows" from "unknown workspace".
        metas.forEach { meta -> windows.getOrPut(meta.id) { mutableListOf() } }
        return DesktopSnapshot(activeId, metas, windows)
    }

    private fun escape(value: String): String = value
        .replace("\\", "\\\\")
        .replace("|", "\\p")
        .replace("\n", "\\n")
        .replace(",", "\\c")

    private fun unescape(value: String): String = buildString {
        var i = 0
        while (i < value.length) {
            val c = value[i]
            if (c == '\\' && i + 1 < value.length) {
                when (value[i + 1]) {
                    'p' -> append('|')
                    'n' -> append('\n')
                    'c' -> append(',')
                    '\\' -> append('\\')
                    else -> append(value[i + 1])
                }
                i += 2
            } else {
                append(c)
                i++
            }
        }
    }

    /** Split on unescaped pipes. */
    private fun splitEscaped(value: String): List<String> {
        val out = mutableListOf<String>()
        val current = StringBuilder()
        var i = 0
        while (i < value.length) {
            val c = value[i]
            if (c == '\\' && i + 1 < value.length) {
                current.append(c).append(value[i + 1])
                i += 2
                continue
            }
            if (c == '|') {
                out += unescape(current.toString())
                current.clear()
            } else {
                current.append(c)
            }
            i++
        }
        out += unescape(current.toString())
        return out
    }
}
