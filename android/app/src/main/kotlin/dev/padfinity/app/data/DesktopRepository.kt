package dev.padfinity.app.data

import android.content.Context
import dev.padfinity.engine.DesktopCodec
import dev.padfinity.engine.DesktopSnapshot

/**
 * Persistence for the desktop layout.
 *
 * Uses SharedPreferences rather than DataStore deliberately: one small string,
 * synchronous read at startup, no coroutine plumbing, no extra dependency. Writes
 * are atomic at the platform level (a single `apply()`), and a corrupt value is
 * quarantined rather than allowed to crash the desktop on boot.
 */
class DesktopRepository(context: Context) {

    private val prefs = context.applicationContext
        .getSharedPreferences("padfinity.desktop", Context.MODE_PRIVATE)

    fun load(): DesktopSnapshot? {
        val raw = prefs.getString(KEY_LAYOUT, null) ?: return null
        val decoded = runCatching { DesktopCodec.decode(raw) }.getOrNull()
        if (decoded == null) {
            // Keep the bad payload for diagnostics instead of silently discarding it.
            prefs.edit().putString(KEY_CORRUPT, raw).remove(KEY_LAYOUT).apply()
        }
        return decoded
    }

    fun save(snapshot: DesktopSnapshot) {
        prefs.edit().putString(KEY_LAYOUT, DesktopCodec.encode(snapshot)).apply()
    }

    fun clear() {
        prefs.edit().remove(KEY_LAYOUT).remove(KEY_PINNED).apply()
    }

    fun pinnedPackages(): List<String> =
        prefs.getString(KEY_PINNED, "")?.split("\n")?.filter { it.isNotBlank() }.orEmpty()

    fun savePinned(packages: List<String>) {
        prefs.edit().putString(KEY_PINNED, packages.joinToString("\n")).apply()
    }

    private companion object {
        const val KEY_LAYOUT = "layout"
        const val KEY_PINNED = "pinned"
        const val KEY_CORRUPT = "corrupt_layout"
    }
}
