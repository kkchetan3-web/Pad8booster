package dev.padfinity.engine

/** Thermal status as reported by `PowerManager.getCurrentThermalStatus()`. */
enum class ThermalStatus { NONE, LIGHT, MODERATE, SEVERE, CRITICAL, UNKNOWN }

enum class Severity { INFO, SUGGESTION, WARNING }

/**
 * Metrics actually obtainable by an ordinary Android app on the Pad 8.
 *
 * Fields are nullable where a value is genuinely unavailable on some builds —
 * `null` means "we could not read this", never zero. That distinction is the
 * difference between an insights engine and a placebo generator.
 */
data class DeviceMetrics(
    val totalRamMb: Int? = null,
    val availableRamMb: Int? = null,
    val storageTotalGb: Double? = null,
    val storageUsedGb: Double? = null,
    val batteryLevel: Int? = null,
    val batteryTempC: Double? = null,
    val thermalStatus: ThermalStatus = ThermalStatus.UNKNOWN,
    val refreshRateHz: Float? = null,
    val enabledPackageCount: Int? = null,
    val jankyFramePct: Double? = null
) {
    val storageUsedPct: Double?
        get() {
            val total = storageTotalGb ?: return null
            val used = storageUsedGb ?: return null
            if (total <= 0.0) return null
            return (used / total * 100.0)
        }

    val availableRamPct: Int?
        get() {
            val total = totalRamMb ?: return null
            val avail = availableRamMb ?: return null
            if (total <= 0) return null
            return (avail.toLong() * 100 / total).toInt()
        }
}

data class Insight(
    val id: String,
    val title: String,
    val detail: String,
    val severity: Severity,
    val confidence: String
)

/**
 * Rule-based insights with an explicit anti-placebo policy.
 *
 * The engine will never emit "free up RAM", "kill background apps" or "boost
 * memory" advice: Android's page cache exists to make launches fast, and
 * flushing it is measurably counter-productive. [InsightEngine.PLACEBO_TERMS]
 * is asserted against in the test suite so this cannot regress quietly.
 */
object InsightEngine {

    val PLACEBO_TERMS = listOf(
        "ram cleaner", "free up ram", "free ram", "boost memory", "kill background",
        "task killer", "memory booster", "speed up your device"
    )

    fun evaluate(m: DeviceMetrics): List<Insight> {
        val out = mutableListOf<Insight>()

        m.storageUsedPct?.let { used ->
            if (used >= 90.0) {
                out += Insight(
                    id = "storage.critical",
                    title = "Storage is nearly full (${used.toInt()}%)",
                    detail = "UFS write performance and file fragmentation degrade once a " +
                        "volume is this full, and Android needs headroom for OTA staging. " +
                        "Move media off-device (the Pad 8 has no microSD slot) or remove " +
                        "the largest unused apps. PADFINITY can list them by size.",
                    severity = Severity.WARNING,
                    confidence = "measured"
                )
            } else if (used >= 80.0) {
                out += Insight(
                    id = "storage.high",
                    title = "Storage is filling up (${used.toInt()}%)",
                    detail = "Leaving ~20% free keeps UFS garbage collection and system " +
                        "updates comfortable.",
                    severity = Severity.SUGGESTION,
                    confidence = "measured"
                )
            }
        }

        when (m.thermalStatus) {
            ThermalStatus.SEVERE, ThermalStatus.CRITICAL -> out += Insight(
                id = "thermal.high",
                title = "Device is thermally throttled",
                detail = "The 5.75 mm chassis cannot sustain peak clocks. Close the heaviest " +
                    "foreground app rather than enabling any 'performance' mode — pinning " +
                    "clocks here increases heat and reduces sustained performance.",
                severity = Severity.WARNING,
                confidence = "measured"
            )
            ThermalStatus.MODERATE -> out += Insight(
                id = "thermal.moderate",
                title = "Warm under load",
                detail = "Normal for sustained gaming or video export. Avoid charging while " +
                    "under heavy load; it stacks two heat sources.",
                severity = Severity.INFO,
                confidence = "measured"
            )
            else -> Unit
        }

        m.batteryTempC?.let { temp ->
            if (temp >= 42.0) {
                out += Insight(
                    id = "battery.hot",
                    title = "Battery at ${temp.toInt()} °C",
                    detail = "Sustained temperatures above ~40 °C accelerate cell ageing. " +
                        "Unplug and let it idle to cool.",
                    severity = Severity.WARNING,
                    confidence = "measured"
                )
            }
        }

        m.availableRamPct?.let { pct ->
            if (pct <= 10) {
                out += Insight(
                    id = "memory.pressure",
                    title = "Memory pressure (${pct}% available)",
                    detail = "On a 12 GB device this usually means a few apps are holding " +
                        "large caches, not that the system needs 'cleaning'. Check which " +
                        "apps dominate usage in Insights → Memory and restart only those.",
                    severity = Severity.SUGGESTION,
                    confidence = "measured"
                )
            }
        }

        m.jankyFramePct?.let { jank ->
            if (jank >= 8.0) {
                out += Insight(
                    id = "render.jank",
                    title = "${jank.toInt()}% janky frames",
                    detail = "Frame pacing is suffering. On a 144 Hz panel this is usually a " +
                        "single misbehaving surface rather than the whole system; check the " +
                        "top window's rendering rather than lowering global refresh rate.",
                    severity = Severity.SUGGESTION,
                    confidence = "measured"
                )
            }
        }

        m.enabledPackageCount?.let { count ->
            if (count >= 240) {
                out += Insight(
                    id = "packages.many",
                    title = "$count enabled packages",
                    detail = "A large enabled-package count increases background wakeups and " +
                        "storage pressure. Review it deliberately — removing the wrong system " +
                        "package breaks notifications or OTA. PADFINITY only suggests the " +
                        "ad/telemetry tier and marks everything reversible.",
                    severity = Severity.INFO,
                    confidence = "measured"
                )
            }
        }

        val level = m.batteryLevel
        val hz = m.refreshRateHz
        if (level != null && hz != null && level <= 25 && hz >= 120f) {
            out += Insight(
                id = "power.refresh",
                title = "Consider capping refresh rate on low battery",
                detail = "At ${level}% with a ${hz.toInt()} Hz panel, capping to 60 Hz extends " +
                    "runtime measurably for reading and writing. PADFINITY can switch this " +
                    "per workspace.",
                severity = Severity.SUGGESTION,
                confidence = "measured"
            )
        }

        return out
    }
}
