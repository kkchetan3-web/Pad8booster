package dev.padfinity.engine

/** One entry rendered on the PADFINITY taskbar. */
data class TaskbarItem(
    val key: String,
    val label: String,
    val pinned: Boolean,
    val running: Boolean,
    val focused: Boolean
)

/**
 * Taskbar composition rules.
 *
 * Order is: focused window, then pinned entries in user order, then running
 * entries not already shown, then recents. This mirrors Windows/macOS behaviour
 * closely enough to feel familiar while keeping pinned order stable (a pinned
 * item never moves because an app was launched).
 */
class TaskbarModel(private val maxItems: Int = 9) {

    private val pinned = mutableListOf<String>()

    val pinnedKeys: List<String> get() = pinned.toList()

    fun pin(key: String): Boolean =
        if (pinned.contains(key)) false else pinned.add(key)

    fun unpin(key: String): Boolean = pinned.remove(key)

    fun reorder(fromIndex: Int, toIndex: Int): Boolean {
        if (fromIndex !in pinned.indices || toIndex !in pinned.indices) return false
        val item = pinned.removeAt(fromIndex)
        pinned.add(toIndex, item)
        return true
    }

    fun build(
        labels: Map<String, String>,
        running: List<String>,
        focused: String?,
        recents: List<String>
    ): List<TaskbarItem> {
        val seen = LinkedHashSet<String>()
        val out = mutableListOf<TaskbarItem>()

        fun add(key: String) {
            if (!seen.add(key)) return
            out += TaskbarItem(
                key = key,
                label = labels[key] ?: key,
                pinned = pinned.contains(key),
                running = running.contains(key),
                focused = key == focused
            )
        }

        focused?.let { add(it) }
        pinned.forEach { add(it) }
        running.forEach { add(it) }
        recents.forEach { add(it) }

        // Overflow is reported by the caller via overflowCount(), so trim here.
        return out.take(maxItems)
    }

    fun overflowCount(totalDistinct: Int): Int = (totalDistinct - maxItems).coerceAtLeast(0)
}
