package dev.padfinity.engine

/** Ranking criteria, in the priority order the product spec requires. */
enum class Criterion(val weight: Double) {
    COMPATIBILITY(1.60),
    USEFULNESS(1.40),
    RELIABILITY(1.30),
    TABLET_FIT(1.20),
    PERFORMANCE(0.90),
    PRIVACY(0.90),
    EASE(0.70),
    COST(0.60)
}

/** Permission tier an app needs beyond ordinary install-time grants. */
enum class AccessTier { NONE, ACCESSIBILITY, SHIZUKU, ROOT }

/**
 * A catalogue candidate. Scores are 0..10 editorial judgements, deliberately
 * separated from the weights so the ranking stays explainable: the UI shows
 * *why* something ranked where it did.
 */
data class CandidateApp(
    val id: String,
    val name: String,
    val developer: String,
    val category: String,
    val accessTier: AccessTier = AccessTier.NONE,
    val free: Boolean = true,
    val duplicatesBuiltIn: Boolean = false,
    val scores: Map<Criterion, Int>,
    val note: String,
    val distributionNote: String? = null
) {
    fun scoreFor(c: Criterion): Int = scores[c] ?: 0
}

data class ScoredApp(
    val app: CandidateApp,
    val total: Double,
    val excludedReason: String? = null
) {
    val included: Boolean get() = excludedReason == null
}

/**
 * Transparent weighted ranking.
 *
 * Filters exist because the product must not recommend something the user's
 * device or their stated policy forbids: no root-dependent apps by default, no
 * Accessibility-heavy apps unless the user opted in, and — importantly — nothing
 * that duplicates PADFINITY's own built-in capability.
 */
object Recommender {

    data class Policy(
        val allowShizuku: Boolean = true,
        val allowAccessibility: Boolean = false,
        val allowRoot: Boolean = false,
        val allowDuplicates: Boolean = false
    )

    fun rank(
        candidates: List<CandidateApp>,
        policy: Policy = Policy()
    ): List<ScoredApp> {
        val scored = candidates.map { app ->
            val reason = when {
                app.accessTier == AccessTier.ROOT && !policy.allowRoot ->
                    "needs root; not permitted by current policy"
                app.accessTier == AccessTier.SHIZUKU && !policy.allowShizuku ->
                    "needs Shizuku; enable advanced access to see this"
                app.accessTier == AccessTier.ACCESSIBILITY && !policy.allowAccessibility ->
                    "needs an Accessibility service; opt in to evaluate it"
                app.duplicatesBuiltIn && !policy.allowDuplicates ->
                    "duplicates a capability PADFINITY already provides"
                else -> null
            }
            val total = Criterion.entries.sumOf { c ->
                app.scoreFor(c) * c.weight
            }
            ScoredApp(app, total, reason)
        }
        return scored.sortedWith(
            compareBy({ it.excludedReason != null }, { -it.total })
        )
    }

    fun included(ranked: List<ScoredApp>): List<ScoredApp> = ranked.filter { it.included }

    /** Best single recommendation per category, for the "Recommended Setup" view. */
    fun recommendedSetup(ranked: List<ScoredApp>, maxCategories: Int = 6): List<ScoredApp> {
        val seen = mutableSetOf<String>()
        val out = mutableListOf<ScoredApp>()
        for (item in included(ranked)) {
            if (seen.add(item.app.category)) out += item
            if (out.size >= maxCategories) break
        }
        return out
    }
}

/**
 * Seed catalogue — deliberately small and conservative.
 *
 * Entries describe capabilities I can state with confidence. Anything requiring
 * a claim I could not verify (exact pricing tiers, Play Store availability by
 * region) is qualified in `note`/`distributionNote` or left out entirely.
 * The long-form evaluation table lives in docs/APP_DISCOVERY.md.
 */
object SeedCatalogue {

    val apps: List<CandidateApp> = listOf(
        CandidateApp(
            id = "app.shizuku",
            name = "Shizuku",
            developer = "RikkaApps",
            category = "Advanced access",
            accessTier = AccessTier.NONE,
            free = true,
            scores = mapOf(
                Criterion.COMPATIBILITY to 9,
                Criterion.USEFULNESS to 10,
                Criterion.RELIABILITY to 9,
                Criterion.TABLET_FIT to 8,
                Criterion.PERFORMANCE to 10,
                Criterion.PRIVACY to 8,
                Criterion.EASE to 6,
                Criterion.COST to 10
            ),
            note = "Grants shell-level APIs without root. This is what makes real " +
                "freeform launches and system-level tuning reachable on a locked " +
                "Pad 8. Open source; service must be restarted after reboot.",
            distributionNote = "Open source on GitHub; verify the release you install."
        ),
        CandidateApp(
            id = "app.niagara",
            name = "Niagara Launcher",
            developer = "Peter Huber",
            category = "Launcher",
            free = true,
            scores = mapOf(
                Criterion.COMPATIBILITY to 8,
                Criterion.USEFULNESS to 8,
                Criterion.RELIABILITY to 8,
                Criterion.TABLET_FIT to 6,
                Criterion.PERFORMANCE to 9,
                Criterion.PRIVACY to 7,
                Criterion.EASE to 8,
                Criterion.COST to 7
            ),
            note = "Excellent on phones; on an 11.2\" 3:2 panel its vertical list " +
                "wastes horizontal space. Evaluate carefully — replacing " +
                "com.miui.home also loses the HyperOS dock and 1:9 split."
        ),
        CandidateApp(
            id = "app.kwgt",
            name = "KWGT",
            developer = "Kustom Industries",
            category = "Widgets",
            free = true,
            scores = mapOf(
                Criterion.COMPATIBILITY to 8,
                Criterion.USEFULNESS to 9,
                Criterion.RELIABILITY to 7,
                Criterion.TABLET_FIT to 9,
                Criterion.PERFORMANCE to 6,
                Criterion.PRIVACY to 7,
                Criterion.EASE to 5,
                Criterion.COST to 7
            ),
            note = "Custom widgets with per-widget sizing, which matters far more on a " +
                "tablet grid than on a phone. Heavier widgets cost battery."
        ),
        CandidateApp(
            id = "app.tasker",
            name = "Tasker",
            developer = "João Dias",
            category = "Automation",
            accessTier = AccessTier.ACCESSIBILITY,
            free = false,
            scores = mapOf(
                Criterion.COMPATIBILITY to 7,
                Criterion.USEFULNESS to 9,
                Criterion.RELIABILITY to 8,
                Criterion.TABLET_FIT to 7,
                Criterion.PERFORMANCE to 7,
                Criterion.PRIVACY to 6,
                Criterion.EASE to 4,
                Criterion.COST to 5
            ),
            note = "Maximum automation power; steep learning curve. Requires several " +
                "special permissions. PADFINITY's built-in profiles cover the common " +
                "cases first — add Tasker only for what they cannot do."
        ),
        CandidateApp(
            id = "app.macrodroid",
            name = "MacroDroid",
            developer = "ArloSoft",
            category = "Automation",
            accessTier = AccessTier.ACCESSIBILITY,
            free = true,
            scores = mapOf(
                Criterion.COMPATIBILITY to 8,
                Criterion.USEFULNESS to 8,
                Criterion.RELIABILITY to 8,
                Criterion.TABLET_FIT to 7,
                Criterion.PERFORMANCE to 8,
                Criterion.PRIVACY to 6,
                Criterion.EASE to 7,
                Criterion.COST to 8
            ),
            note = "Far easier than Tasker for trigger→action macros. A sensible starting " +
                "point for 'keyboard connected → open Work workspace'."
        ),
        CandidateApp(
            id = "app.mixplorer",
            name = "MiXplorer",
            developer = "Hootan Parsa",
            category = "Files",
            free = true,
            scores = mapOf(
                Criterion.COMPATIBILITY to 8,
                Criterion.USEFULNESS to 9,
                Criterion.RELIABILITY to 8,
                Criterion.TABLET_FIT to 9,
                Criterion.PERFORMANCE to 8,
                Criterion.PRIVACY to 7,
                Criterion.EASE to 6,
                Criterion.COST to 8
            ),
            note = "Genuine dual-pane file management with SMB/SFTP — the closest thing to " +
                "a desktop Explorer on Android. Note that scoped storage still limits " +
                "writes to other apps' private directories."
        ),
        CandidateApp(
            id = "app.termux",
            name = "Termux",
            developer = "Termux project",
            category = "Developer",
            free = true,
            scores = mapOf(
                Criterion.COMPATIBILITY to 8,
                Criterion.USEFULNESS to 10,
                Criterion.RELIABILITY to 8,
                Criterion.TABLET_FIT to 10,
                Criterion.PERFORMANCE to 9,
                Criterion.PRIVACY to 9,
                Criterion.EASE to 4,
                Criterion.COST to 10
            ),
            note = "A real Linux userland: git, Python, Node, SSH, proot-distro Debian. With " +
                "a keyboard this is what turns the tablet into a development machine.",
            distributionNote = "Current releases ship via F-Droid/GitHub, not the Play Store."
        ),
        CandidateApp(
            id = "app.keymapper",
            name = "Key Mapper",
            developer = "Key Mapper contributors",
            category = "Input",
            accessTier = AccessTier.SHIZUKU,
            free = true,
            scores = mapOf(
                Criterion.COMPATIBILITY to 7,
                Criterion.USEFULNESS to 8,
                Criterion.RELIABILITY to 7,
                Criterion.TABLET_FIT to 8,
                Criterion.PERFORMANCE to 9,
                Criterion.PRIVACY to 8,
                Criterion.EASE to 6,
                Criterion.COST to 9
            ),
            note = "Remaps keyboard/mouse buttons. Uses an Accessibility service, and " +
                "Shizuku helps with injected input. Open source.",
            distributionNote = "Open source; available via F-Droid/GitHub."
        ),
        CandidateApp(
            id = "app.panels",
            name = "Panels",
            developer = "Panels",
            category = "Edge panel",
            accessTier = AccessTier.ACCESSIBILITY,
            free = true,
            duplicatesBuiltIn = false,
            scores = mapOf(
                Criterion.COMPATIBILITY to 7,
                Criterion.USEFULNESS to 7,
                Criterion.RELIABILITY to 7,
                Criterion.TABLET_FIT to 8,
                Criterion.PERFORMANCE to 8,
                Criterion.PRIVACY to 6,
                Criterion.EASE to 7,
                Criterion.COST to 7
            ),
            note = "Edge-panel launcher. HyperOS already ships a sidebar; only worth adding " +
                "if you need multi-app freeform launch from the panel."
        )
    )
}
