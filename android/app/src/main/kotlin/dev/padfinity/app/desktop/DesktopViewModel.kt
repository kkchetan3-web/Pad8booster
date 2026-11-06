package dev.padfinity.app.desktop

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import dev.padfinity.app.data.DesktopRepository
import dev.padfinity.engine.Rect
import dev.padfinity.engine.DesktopSnapshot
import dev.padfinity.engine.SnapZone
import dev.padfinity.engine.TileLayout
import dev.padfinity.engine.Window
import dev.padfinity.engine.WindowKind
import dev.padfinity.engine.WindowManager
import dev.padfinity.engine.WorkspaceManager
import dev.padfinity.engine.WorkspaceMeta
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Bridges the pure-Kotlin engine to Compose state.
 *
 * All geometry is in **pixels**; the UI converts with `LocalDensity`. Persistence
 * is debounced so a drag gesture does not write on every frame.
 */
class DesktopViewModel(application: Application) : AndroidViewModel(application) {

    private val repository = DesktopRepository(application)

    /** Engine is created lazily once the real workspace size is known. */
    private var sessions: WorkspaceManager? = null
    private var bounds: Rect = Rect.of(0, 0, 1600, 1068)
    private var persistJob: Job? = null

    var windows by mutableStateOf<List<Window>>(emptyList())
        private set
    var focusedId by mutableStateOf<String?>(null)
        private set
    var workspaceIds by mutableStateOf<List<String>>(emptyList())
        private set
    var activeWorkspace by mutableStateOf("")
        private set
    var workspaceName by mutableStateOf("")
        private set
    var snapPreview by mutableStateOf<Rect?>(null)
        private set

    val engine: WindowManager? get() = sessions?.active

    // ------------------------------------------------------------------ setup

    /** Called on first layout and on every rotation / resize. */
    fun onWorkspaceBounds(newBounds: Rect) {
        if (newBounds.isEmpty) return
        bounds = newBounds
        val existing = sessions
        if (existing == null) {
            sessions = WorkspaceManager(bounds).also { manager ->
                val snapshot: DesktopSnapshot? = repository.load()
                if (snapshot != null) {
                    manager.restore(snapshot, bounds)
                } else {
                    seedFirstRun(manager)
                }
            }
        } else {
            existing.resizeAll(bounds)
        }
        refresh()
    }

    private fun seedFirstRun(manager: WorkspaceManager) {
        // A useful default beats an empty desktop.
        manager.active.open("padfinity.notes", "Notes", surfaceRoute = "notes")
        manager.active.open("padfinity.insights", "Insights", surfaceRoute = "insights")
        manager.active.snap("padfinity.notes", SnapZone.LEFT)
        manager.active.snap("padfinity.insights", SnapZone.RIGHT)
    }

    // -------------------------------------------------------------- commands

    fun openInternal(id: String, title: String, route: String) {
        sessions?.active?.open(id, title, WindowKind.INTERNAL, surfaceRoute = route)
        refresh(); schedulePersist()
    }

    fun openSystemApp(packageName: String, label: String) {
        sessions?.active?.open(
            id = "sys.$packageName",
            title = label,
            kind = WindowKind.SYSTEM_APP,
            packageName = packageName,
            surfaceRoute = null
        )
        refresh(); schedulePersist()
    }

    fun close(id: String) { sessions?.active?.close(id); refresh(); schedulePersist() }
    fun focus(id: String) { sessions?.active?.focus(id); refresh() }

    fun moveBy(id: String, dx: Int, dy: Int) {
        sessions?.active?.moveBy(id, dx, dy); refresh()
    }

    fun resizeBy(id: String, dx: Int, dy: Int) {
        sessions?.active?.resizeBy(id, dx, dy); refresh()
    }

    fun updateSnapPreview(dragged: Rect?) {
        val manager = sessions?.active ?: return
        snapPreview = dragged?.let { manager.snapZoneFor(it) }?.let { manager.snappedBounds(it) }
    }

    fun clearSnapPreview() { snapPreview = null }

    fun snap(id: String, zone: SnapZone) {
        sessions?.active?.snap(id, zone); snapPreview = null; refresh(); schedulePersist()
    }

    /** End a drag: snap if the window's edges are near a zone, otherwise just settle. */
    fun endDrag(id: String) {
        val manager = sessions?.active ?: return
        val window = manager.window(id)
        if (window != null) {
            manager.snapZoneFor(window.bounds)?.let { manager.snap(id, it) }
        }
        snapPreview = null
        refresh(); schedulePersist()
    }

    fun minimize(id: String) { sessions?.active?.minimize(id); refresh(); schedulePersist() }
    fun maximize(id: String) { sessions?.active?.maximize(id); refresh(); schedulePersist() }
    fun restore(id: String) { sessions?.active?.restore(id); refresh(); schedulePersist() }
    fun toggleMaximize(id: String) { sessions?.active?.toggleMaximize(id); refresh(); schedulePersist() }
    fun cycleFocus() { sessions?.active?.cycleFocus(); refresh() }
    fun tile(layout: TileLayout) { sessions?.active?.tile(layout); refresh(); schedulePersist() }

    // ------------------------------------------------------------ workspaces

    fun switchWorkspace(id: String) {
        sessions?.switchTo(id); refresh(); schedulePersist()
    }

    fun addWorkspace(name: String) {
        val manager = sessions ?: return
        val id = "workspace.${name.lowercase().replace(' ', '.')}.${manager.ids().size}"
        manager.add(WorkspaceMeta(id = id, name = name))
        manager.switchTo(id)
        refresh(); schedulePersist()
    }

    fun renameActiveWorkspace(name: String) {
        val manager = sessions ?: return
        manager.updateMeta(manager.activeMeta.copy(name = name))
        refresh(); schedulePersist()
    }

    // ----------------------------------------------------------- persistence

    private fun refresh() {
        val manager = sessions ?: return
        windows = manager.active.windows
        focusedId = manager.active.focusedId
        workspaceIds = manager.ids()
        activeWorkspace = manager.activeId
        workspaceName = manager.activeMeta.name
    }

    private fun schedulePersist() {
        persistJob?.cancel()
        persistJob = viewModelScope.launch {
            delay(600) // idle debounce: never write mid-gesture
            sessions?.let { repository.save(it.snapshot()) }
        }
    }

    /** Used by the Recovery screen: drop layout and rebuild defaults. */
    fun resetEverything() {
        repository.clear()
        sessions = null
        onWorkspaceBounds(bounds)
    }

    override fun onCleared() {
        sessions?.let { repository.save(it.snapshot()) }
        super.onCleared()
    }
}
