package dev.padfinity.app.capability

/**
 * Uniform surface for everything PADFINITY can only do with elevated access.
 *
 * Design rules:
 *  - the UI renders [status], never a button that fails silently;
 *  - every write is read back and journalled so it can be undone;
 *  - absence of Shizuku degrades features, never crashes the app.
 */
enum class CapabilityStatus { AVAILABLE, NEEDS_SHIZUKU, UNAVAILABLE }

data class CapabilityResult(
    val ok: Boolean,
    val status: CapabilityStatus,
    val detail: String = ""
)

interface CapabilityGateway {
    fun status(): CapabilityStatus
    fun canExecute(): Boolean = status() == CapabilityStatus.AVAILABLE
    suspend fun run(command: String): CapabilityResult
    suspend fun read(command: String): String?
}

/**
 * Fallback used when Shizuku is not installed or not authorised: everything
 * reports [CapabilityStatus.NEEDS_SHIZUKU] and no command is executed.
 */
class UnavailableGateway(private val reason: String = "Shizuku not available") : CapabilityGateway {
    override fun status(): CapabilityStatus = CapabilityStatus.NEEDS_SHIZUKU
    override suspend fun run(command: String): CapabilityResult =
        CapabilityResult(false, CapabilityStatus.NEEDS_SHIZUKU, reason)

    override suspend fun read(command: String): String? = null
}

/**
 * Shizuku-backed shell executor.
 *
 * Uses **reflection** on purpose: the Shizuku API artifacts are not present in the
 * environment where this project was authored, and a hard compile/runtime
 * dependency on them would make the app crash (NoClassDefFoundError) whenever the
 * user has not installed Shizuku. Reflection keeps the app installable and honest:
 * if the classes are missing, status is NEEDS_SHIZUKU and nothing runs.
 *
 * The measured command set for the Pad 8 is documented in DEVICE_RESEARCH.md §2.3:
 * `am start --windowingMode 5` works; bounds are not accepted by this firmware.
 */
class ShizukuGateway : CapabilityGateway {

    override fun status(): CapabilityStatus = when {
        !classesPresent() -> CapabilityStatus.NEEDS_SHIZUKU
        !isGranted() -> CapabilityStatus.NEEDS_SHIZUKU
        !isServiceAlive() -> CapabilityStatus.NEEDS_SHIZUKU
        else -> CapabilityStatus.AVAILABLE
    }

    override suspend fun run(command: String): CapabilityResult {
        if (!canExecute()) {
            return CapabilityResult(false, status(), "Shizuku shell is not available")
        }
        return try {
            // Shizuku.newProcess(String[] cmd, String[] env, String dir) returns a Process.
            val shizuku = Class.forName("rikka.shizuku.Shizuku")
            val newProcess = shizuku.getMethod(
                "newProcess",
                Array<String>::class.java,
                Array<String>::class.java,
                String::class.java
            )
            val process = newProcess.invoke(null, arrayOf("sh", "-c", command), null, null) as Process
            val exit = process.waitFor()
            val err = process.errorStream.bufferedReader().readText()
            CapabilityResult(exit == 0, CapabilityStatus.AVAILABLE, err.take(300))
        } catch (t: Throwable) {
            CapabilityResult(false, CapabilityStatus.NEEDS_SHIZUKU, t.message ?: "shell failed")
        }
    }

    override suspend fun read(command: String): String? = null // see ShellReadback in roadmap

    /** Freeform launch of another app — the one genuinely useful shell call on this device. */
    suspend fun launchFreeform(packageName: String, activity: String): CapabilityResult =
        run("am start --windowingMode 5 -n $packageName/$activity")

    private fun classesPresent(): Boolean = try {
        Class.forName("rikka.shizuku.Shizuku"); true
    } catch (t: Throwable) {
        false
    }

    private fun isGranted(): Boolean = try {
        Class.forName("rikka.shizuku.Shizuku")
            .getMethod("checkSelfPermission")
            .invoke(null) == 0
    } catch (t: Throwable) {
        false
    }

    private fun isServiceAlive(): Boolean = try {
        Class.forName("rikka.shizuku.Shizuku")
            .getMethod("pingBinder")
            .invoke(null) as Boolean
    } catch (t: Throwable) {
        false
    }
}

/** Commands the app may issue, enumerated so nothing is built from user text. */
object ShellCommands {
    fun freeformLaunch(pkg: String, activity: String) =
        "am start --windowingMode 5 -n $pkg/$activity"

    fun setDensity(dpi: Int) = "wm density ${dpi.coerceIn(220, 420)}"
    fun resetDensity() = "wm density reset"
    fun setStandbyBucket(pkg: String, bucket: String) =
        "am set-standby-bucket $pkg ${bucket.lowercase()}"
    fun animationScale(key: String, scale: String) =
        "settings put global $key ${scale.toFloatOrNull()?.coerceIn(0f, 1f) ?: 1f}"
    fun readDensity() = "wm density"
}
