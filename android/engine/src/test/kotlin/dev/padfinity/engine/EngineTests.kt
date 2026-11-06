package dev.padfinity.engine

import kotlin.system.exitProcess

/**
 * Self-contained test harness.
 *
 * JUnit is not used because this module is compiled here with a bare kotlinc and
 * a JDK — no Maven/Gradle repository access — and the engine is intended to stay
 * dependency-free. The harness is intentionally tiny so it cannot hide failures:
 * every check prints, and the process exits non-zero if anything fails.
 */
private var passed = 0
private var failed = 0
private val failures = mutableListOf<String>()

private fun check(name: String, condition: Boolean) {
    if (condition) {
        passed++
    } else {
        failed++
        failures += name
        println("  FAIL  $name")
    }
}

private fun checkEq(name: String, expected: Any?, actual: Any?) =
    check("$name (expected=$expected, actual=$actual)", expected == actual)

private fun group(title: String) = println("\n[$title]")

// The Pad 8 test surface: 11.2" 3200x2136 at 320 dpi ≈ 1600x1068 dp landscape.
private val WS = Rect.of(0, 0, 1600, 1068)

fun main() {
    println("PADFINITY engine tests — Kotlin ${KotlinVersion.CURRENT}")

    // ---------------------------------------------------------------- windows
    group("window lifecycle")
    run {
        val wm = WindowManager(WS)
        val a = wm.open("a", "Notes")
        checkEq("open returns window id", "a", a.id)
        checkEq("first window focused", "a", wm.focusedId)
        check("opened bounds inside workspace", WS.overlapFractionOf(a.bounds) == 1f)

        wm.open("b", "Files")
        checkEq("second window focused", "b", wm.focusedId)
        checkEq("two windows", 2, wm.windows.size)
        check("cascade offsets second window", wm.window("b")!!.bounds.left > wm.window("a")!!.bounds.left)

        val reopened = wm.open("a", "Notes")
        checkEq("re-open does not duplicate", 2, wm.windows.size)
        checkEq("re-open focuses existing", "a", wm.focusedId)
        checkEq("re-open returns same bounds", a.bounds, reopened.bounds)

        checkEq("topmost is focused window", "a", wm.windows.last().id)
        check("close returns true", wm.close("a"))
        check("close clears window", wm.window("a") == null)
        check("close drops focus", wm.focusedId != "a")
        check("closing unknown id is false", !wm.close("nope"))
    }

    group("focus and MRU")
    run {
        val wm = WindowManager(WS)
        listOf("a", "b", "c").forEach { wm.open(it, it.uppercase()) }
        checkEq("MRU head is newest", listOf("c", "b", "a"), wm.mru())
        wm.focus("a")
        checkEq("focus moves to MRU head", listOf("a", "c", "b"), wm.mru())
        checkEq("cycleFocus goes to previous", "c", wm.cycleFocus())
        wm.focus("a")
        checkEq("reverse cycle goes to oldest", "b", wm.cycleFocus(reverse = true))
        wm.minimize("b")
        check("minimised window leaves MRU", !wm.mru().contains("b"))
        check("focus on minimised window fails", !wm.focus("b"))
    }

    group("geometry constraints")
    run {
        val wm = WindowManager(WS)
        wm.open("a", "Notes", bounds = Rect.of(100, 100, 600, 400))
        wm.moveBy("a", 10_000, 10_000)
        val moved = wm.window("a")!!
        check("cannot drag fully off right edge",
            moved.bounds.left <= WS.right - WindowManager.MIN_VISIBLE_W)
        check("title bar stays inside vertically",
            moved.bounds.top <= WS.bottom - WindowManager.MIN_VISIBLE_TITLEBAR)

        wm.moveBy("a", -20_000, -20_000)
        check("cannot drag fully off left edge",
            wm.window("a")!!.bounds.right >= WS.left + WindowManager.MIN_VISIBLE_W)
        check("cannot drag above top", wm.window("a")!!.bounds.top >= WS.top)

        wm.open("tiny", "Tiny", bounds = Rect.of(0, 0, 100, 100), minWidth = 340, minHeight = 260)
        wm.resizeBy("tiny", -5_000, -5_000)
        check("resize honours minimum width", wm.window("tiny")!!.bounds.width >= 340)
        check("resize honours minimum height", wm.window("tiny")!!.bounds.height >= 260)

        wm.resizeBy("tiny", 50_000, 50_000)
        check("resize cannot exceed workspace", wm.window("tiny")!!.bounds.right <= WS.right)
    }

    group("minimise / maximise / restore")
    run {
        val wm = WindowManager(WS)
        val original = Rect.of(120, 90, 700, 500)
        wm.open("a", "Notes", bounds = original)

        check("maximize returns true", wm.maximize("a"))
        checkEq("maximised fills workspace", WS, wm.window("a")!!.bounds)
        checkEq("maximised mode", WindowMode.MAXIMIZED, wm.window("a")!!.mode)
        check("move refused when maximised", !wm.moveBy("a", 50, 50))
        check("resize refused when maximised", !wm.resizeBy("a", 50, 50))
        wm.restore("a")
        checkEq("restore returns to original bounds", original, wm.window("a")!!.bounds)
        checkEq("restore clears mode", WindowMode.NORMAL, wm.window("a")!!.mode)
        check("toggleMaximize maximises", wm.toggleMaximize("a"))
        check("toggleMaximize restores", wm.toggleMaximize("a"))

        wm.open("b", "Files")
        wm.minimize("b")
        checkEq("minimise mode", WindowMode.MINIMIZED, wm.window("b")!!.mode)
        check("minimised window is not visible", !wm.window("b")!!.isVisible)
        checkEq("focus moves away from minimised", "a", wm.focusedId)
        wm.restore("b")
        checkEq("restored window is visible again", WindowMode.NORMAL, wm.window("b")!!.mode)
    }

    group("snapping")
    run {
        val wm = WindowManager(WS)
        wm.open("a", "Notes")
        wm.snap("a", SnapZone.LEFT)
        checkEq("left snap = half width", WS.width / 2, wm.window("a")!!.bounds.width)
        checkEq("left snap anchored left", WS.left, wm.window("a")!!.bounds.left)
        checkEq("left snap full height", WS.height, wm.window("a")!!.bounds.height)

        wm.snap("a", SnapZone.RIGHT, ratio = 0.6f)
        val right = wm.window("a")!!.bounds
        checkEq("right snap 60% width", (WS.width * 0.6f).toInt(), right.width)
        checkEq("right snap anchored right", WS.right, right.right)

        wm.snap("a", SnapZone.LEFT, ratio = 0.05f)
        check("ratio clamped to sane minimum", wm.window("a")!!.bounds.width >= (WS.width * 0.2f).toInt())

        wm.snap("a", SnapZone.BOTTOM_RIGHT)
        val q = wm.window("a")!!.bounds
        checkEq("quadrant width is half", WS.width / 2, q.width)
        checkEq("quadrant height is half", WS.height / 2, q.height)
        checkEq("quadrant anchored bottom-right", WS.right, q.right)
        checkEq("snap records zone", SnapZone.BOTTOM_RIGHT, wm.window("a")!!.snapZone)

        val maximisedRestore = WindowManager(WS).let { m ->
            m.open("x", "X", bounds = Rect.of(80, 80, 500, 400))
            m.maximize("x")
            m.snap("x", SnapZone.LEFT)
            m.window("x")!!.restoreBounds
        }
        checkEq("snapping a maximised window keeps its pre-maximise bounds",
            Rect.of(80, 80, 500, 400), maximisedRestore)
    }

    group("snap detection while dragging")
    run {
        val wm = WindowManager(WS)
        checkEq("centre drag is not a snap", null, wm.snapZoneFor(Rect.of(600, 400, 400, 300)))
        checkEq("left edge triggers LEFT", SnapZone.LEFT, wm.snapZoneFor(Rect.of(0, 400, 400, 300)))
        checkEq("top-left corner wins over edge",
            SnapZone.TOP_LEFT, wm.snapZoneFor(Rect.of(0, 0, 400, 300)))
        checkEq("bottom-right corner",
            SnapZone.BOTTOM_RIGHT, wm.snapZoneFor(Rect.of(1200, 768, 400, 300)))
        val preview = wm.snapPreview(Rect.of(0, 400, 400, 300))
        check("preview produced", preview != null)
        checkEq("preview zone", SnapZone.LEFT, preview!!.previewZone)
        checkEq("preview bounds match snap", wm.snappedBounds(SnapZone.LEFT), preview.previewBounds)
        checkEq("no preview in centre", null, wm.snapPreview(Rect.of(600, 400, 400, 300)))
    }

    group("tiling")
    run {
        val wm = WindowManager(WS)
        wm.open("a", "A"); wm.open("b", "B")
        checkEq("two-column tile count", 2, wm.tile(TileLayout.TWO_COLUMNS))
        val l = wm.window("a")!!.bounds
        val r = wm.window("b")!!.bounds
        checkEq("two columns cover full width", WS.width, l.width + r.width)
        checkEq("two columns full height", WS.height, l.height)
        checkEq("left window starts at left", WS.left, l.left)
        checkEq("right window ends at right", WS.right, r.right)

        val four = WindowManager(WS)
        listOf("a", "b", "c", "d").forEach { four.open(it, it) }
        four.tile(TileLayout.GRID_2X2)
        val area = four.windows.sumOf { it.bounds.width.toLong() * it.bounds.height }
        checkEq("2x2 grid covers the workspace", WS.width.toLong() * WS.height, area)

        val main = WindowManager(WS)
        main.open("main", "Main"); main.open("s1", "S1"); main.open("s2", "S2")
        main.focus("main")
        main.tile(TileLayout.MAIN_AND_STACK)
        checkEq("main window gets 62%", (WS.width * 0.62f).toInt(), main.window("main")!!.bounds.width)
        checkEq("stack starts where main ends",
            main.window("main")!!.bounds.right, main.window("s1")!!.bounds.left)
        check("stack right edge is workspace right", main.window("s2")!!.bounds.right == WS.right)

        val casc = WindowManager(WS)
        casc.open("a", "A", bounds = Rect.of(0, 0, 900, 600))
        casc.open("b", "B", bounds = Rect.of(0, 0, 900, 600))
        casc.tile(TileLayout.CASCADE)
        check("cascade offsets second window",
            casc.window("b")!!.bounds.left > casc.window("a")!!.bounds.left)
    }

    group("hit testing and workspace resize")
    run {
        val wm = WindowManager(WS)
        wm.open("a", "A", bounds = Rect.of(0, 0, 400, 400))
        wm.open("b", "B", bounds = Rect.of(0, 0, 400, 400))
        checkEq("topmost window receives the tap", "b", wm.topmostAt(100, 100)?.id)
        wm.minimize("b")
        checkEq("minimised window is skipped", "a", wm.topmostAt(100, 100)?.id)
        checkEq("empty area hits nothing", null, wm.topmostAt(1500, 1000))

        val resized = WindowManager(WS)
        resized.open("a", "A", bounds = Rect.of(1000, 700, 500, 300))
        resized.resizeWorkspace(Rect.of(0, 0, 800, 600))
        val b = resized.window("a")!!.bounds
        check("window kept inside shrunken workspace", b.right <= 800 && b.bottom <= 600)
        resized.open("m", "M", bounds = Rect.of(10, 10, 300, 200))
        resized.maximize("m")
        resized.resizeWorkspace(Rect.of(0, 0, 1280, 800))
        checkEq("maximised window tracks workspace resize",
            Rect.of(0, 0, 1280, 800), resized.window("m")!!.bounds)
    }

    // -------------------------------------------------------------- workspaces
    group("workspaces")
    run {
        val ws = WorkspaceManager(WS)
        val first = ws.activeId
        check("default workspace exists", ws.ids().contains(first))
        ws.active.open("note", "Notes")
        checkEq("window added to active workspace", 1, ws.active.visibleWindows.size)

        check("adds Study workspace", ws.add(WorkspaceMeta("study", "Study")))
        check("duplicate workspace rejected", !ws.add(WorkspaceMeta("study", "Study again")))
        check("switch to Study", ws.switchTo("study"))
        checkEq("Study starts with no windows", 0, ws.active.visibleWindows.size)
        ws.active.open("pdf", "PDF")

        check("switch back to Personal", ws.switchTo(first))
        checkEq("Personal kept its window", "note", ws.active.visibleWindows.single().id)
        checkEq("total windows across workspaces", 2, ws.totalOpenWindows())

        check("cannot remove the only workspace", {
            val single = WorkspaceManager(WS)
            single.remove(single.activeId)
        }.invoke().not())
        check("removes inactive workspace", ws.remove("study"))
        check("unknown workspace switch fails", !ws.switchTo("nope"))

        val a = ws.activeId
        ws.add(WorkspaceMeta("work", "Work"))
        ws.switchTo("work")
        check("removing the active workspace falls back", ws.remove("work"))
        checkEq("fell back to another live workspace", a, ws.activeId)
    }

    group("desktop persistence")
    run {
        val ws = WorkspaceManager(WS)
        ws.active.open("a", "Notes", bounds = Rect.of(10, 20, 400, 300))
        ws.active.open("b", "Files", bounds = Rect.of(500, 60, 520, 340))
        ws.active.maximize("b")
        ws.updateMeta(ws.activeMeta.copy(name = "Personal | main, v2"))

        val encoded = DesktopCodec.encode(ws.snapshot())
        val decoded = DesktopCodec.decode(encoded)
        check("decode succeeds", decoded != null)
        checkEq("window count survives round-trip", 2, decoded!!.windows[ws.activeId]!!.size)
        checkEq("metas survive round-trip", 1, decoded.workspaces.size)
        checkEq("separator inside a name survives", "Personal | main, v2",
            decoded.workspaces.first().name)
        val restoredMax = decoded.windows[ws.activeId]!!.first { it.id == "b" }
        checkEq("maximised mode survives", WindowMode.MAXIMIZED, restoredMax.mode)
        checkEq("geometry survives", Rect.of(10, 20, 400, 300),
            decoded.windows[ws.activeId]!!.first { it.id == "a" }.bounds)

        val restored = WorkspaceManager(WS)
        check("restore into a manager", restored.restore(decoded, WS))
        checkEq("restored active window count", 2, restored.active.windows.size)

        checkEq("garbage rejected", null, DesktopCodec.decode("not a desktop"))
        checkEq("empty rejected", null, DesktopCodec.decode("PADFINITY-DESKTOP v1\n"))
        checkEq("bad rect rejected", null,
            DesktopCodec.decode("PADFINITY-DESKTOP v1\nws=a|A|w|1||\nwin=a|x|X|INTERNAL|1,2|NORMAL|-|-|-|320|220"))
        // A workspace with no window lines yet is legitimate (fresh workspace), and
        // an unknown active id must fall back rather than dropping the whole desktop.
        val emptyWs = DesktopCodec.decode("PADFINITY-DESKTOP v1\nactive=zz\nws=a|A|w|1||")
        check("windowless workspace decodes", emptyWs != null)
        checkEq("unknown active id falls back to first workspace", "a", emptyWs!!.activeId)
        checkEq("windowless workspace has no windows", 0, emptyWs.windows["a"]!!.size)
    }

    // ---------------------------------------------------------------- taskbar
    group("taskbar")
    run {
        val labels = mapOf("notes" to "Notes", "files" to "Files", "chrome" to "Chrome", "calc" to "Calc")
        val tb = TaskbarModel(maxItems = 3)
        tb.pin("notes"); tb.pin("files"); tb.pin("chrome")
        checkEq("pinned order preserved", listOf("notes", "files", "chrome"), tb.pinnedKeys)
        check("reorder pinned", tb.reorder(0, 2))
        checkEq("reordered", listOf("files", "chrome", "notes"), tb.pinnedKeys)
        tb.reorder(0, 2) // back to notes, files, chrome

        val items = tb.build(labels, running = listOf("calc", "notes"), focused = "calc",
            recents = listOf("chrome", "notes"))
        checkEq("focused first", "calc", items.first().key)
        checkEq("focused flag set", true, items.first().focused)
        checkEq("dedupe: no repeated keys", items.size, items.map { it.key }.toSet().size)
        checkEq("trimmed to maxItems", 3, items.size)
        check("overflow reported", tb.overflowCount(5) == 2)
        check("unpin works", tb.unpin("chrome"))
        check("pinning twice is a no-op", !tb.pin("notes"))
    }

    // --------------------------------------------------------------- insights
    group("insights")
    run {
        checkEq("no metrics yields no insights", 0, InsightEngine.evaluate(DeviceMetrics()).size)

        val full = DeviceMetrics(
            totalRamMb = 12000, availableRamMb = 900,
            storageTotalGb = 256.0, storageUsedGb = 236.0,
            batteryLevel = 18, batteryTempC = 44.0,
            thermalStatus = ThermalStatus.SEVERE, refreshRateHz = 144f,
            enabledPackageCount = 260, jankyFramePct = 12.0
        )
        val insights = InsightEngine.evaluate(full)
        val ids = insights.map { it.id }.toSet()
        check("storage critical fired", ids.contains("storage.critical"))
        check("thermal fired", ids.contains("thermal.high"))
        check("battery heat fired", ids.contains("battery.hot"))
        check("memory pressure fired", ids.contains("memory.pressure"))
        check("jank fired", ids.contains("render.jank"))
        check("package count fired", ids.contains("packages.many"))
        check("refresh advice fired", ids.contains("power.refresh"))

        val text = insights.joinToString(" ") { (it.title + " " + it.detail).lowercase() }
        check("no placebo advice is ever emitted",
            InsightEngine.PLACEBO_TERMS.none { text.contains(it) })

        // Sweep a broad metric matrix for accidental placebo phrasing.
        var placeboFree = true
        for (storage in listOf(0.0, 50.0, 85.0, 95.0)) {
            for (level in listOf(5, 50, 100)) {
                for (thermal in ThermalStatus.entries) {
                    val m = DeviceMetrics(
                        totalRamMb = 12000, availableRamMb = 600,
                        storageTotalGb = 256.0, storageUsedGb = 256.0 * storage / 100.0,
                        batteryLevel = level, batteryTempC = 45.0, thermalStatus = thermal,
                        refreshRateHz = 144f, enabledPackageCount = 300, jankyFramePct = 20.0
                    )
                    val t = InsightEngine.evaluate(m).joinToString(" ") {
                        (it.title + " " + it.detail).lowercase()
                    }
                    if (InsightEngine.PLACEBO_TERMS.any { t.contains(it) }) placeboFree = false
                }
            }
        }
        check("placebo-free across the whole metric matrix", placeboFree)

        check("unmeasurable fields produce no false insight",
            InsightEngine.evaluate(DeviceMetrics(totalRamMb = null, availableRamMb = null)).isEmpty())
    }

    // ------------------------------------------------------------ recommender
    group("recommender")
    run {
        val all = SeedCatalogue.apps
        val ranked = Recommender.rank(all)
        checkEq("every candidate is scored", all.size, ranked.size)
        check("scores are descending among included",
            Recommender.included(ranked).zipWithNext().all { (a, b) -> a.total >= b.total })
        check("excluded entries sort last",
            ranked.dropWhile { it.included }.all { !it.included })

        val accApp = all.first { it.accessTier == AccessTier.ACCESSIBILITY }
        check("accessibility app excluded by default",
            ranked.first { it.app.id == accApp.id }.excludedReason != null)
        val opted = Recommender.rank(all, Recommender.Policy(allowAccessibility = true))
        check("accessibility app included when opted in",
            opted.first { it.app.id == accApp.id }.included)

        val shizukuApp = all.first { it.accessTier == AccessTier.SHIZUKU }
        check("shizuku app allowed by default policy",
            ranked.first { it.app.id == shizukuApp.id }.included)
        val noShizuku = Recommender.rank(all, Recommender.Policy(allowShizuku = false))
        check("shizuku app excluded when policy forbids",
            noShizuku.first { it.app.id == shizukuApp.id }.excludedReason != null)

        val setup = Recommender.recommendedSetup(ranked)
        checkEq("setup has one app per category", setup.size, setup.map { it.app.category }.toSet().size)
        check("setup respects exclusions",
            setup.all { it.app.accessTier != AccessTier.ACCESSIBILITY })

        val withRoot = all + CandidateApp(
            id = "app.fake", name = "Fake Root Tuner", developer = "n/a", category = "System",
            accessTier = AccessTier.ROOT,
            scores = Criterion.entries.associateWith { 10 },
            note = "test fixture"
        )
        val strict = Recommender.rank(withRoot)
        check("root app excluded by default",
            strict.first { it.app.id == "app.fake" }.excludedReason != null)
        val permissive = Recommender.rank(withRoot, Recommender.Policy(allowRoot = true))
        check("root app included when explicitly permitted",
            permissive.first { it.app.id == "app.fake" }.included)
        checkEq("highest scoring app ranks first under permissive policy",
            "app.fake", Recommender.included(permissive).first().app.id)
    }

    // ------------------------------------------------------------------ report
    println()
    println("=".repeat(64))
    println("PASSED: $passed   FAILED: $failed")
    if (failed > 0) {
        println("Failures:")
        failures.forEach { println("  - $it") }
        println("=".repeat(64))
        exitProcess(1)
    }
    println("All engine checks passed.")
    println("=".repeat(64))
}
