package dev.padfinity.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import dev.padfinity.app.data.DesktopRepository
import dev.padfinity.app.ui.theme.PadfinityTheme

/**
 * Emergency recovery.
 *
 * Reachable two ways, both documented in SECURITY.md §4:
 *   1. Cold start: `adb shell am start -n dev.padfinity/.RecoveryActivity`
 *   2. Deep link: `padfinity://recovery`
 *
 * It clears the desktop layout and any app-level tuning state. It deliberately
 * does NOT try to "restore system settings" here: system-level changes made via
 * Shizuku are journalled and reverted by the host-side tool
 * (`pad8booster revert`) or from Settings → Advanced, because doing shell work
 * from a recovery screen without an authorised session would be exactly the kind
 * of silent mutation this project refuses to do.
 */
class RecoveryActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val repository = DesktopRepository(this)
        setContent {
            PadfinityTheme(darkTheme = true) {
                RecoveryScreen(
                    onReset = {
                        repository.clear()
                        finish()
                    },
                    onCancel = { finish() }
                )
            }
        }
    }
}

@Composable
private fun RecoveryScreen(onReset: () -> Unit, onCancel: () -> Unit) {
    MaterialTheme {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(32.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Text("PADFINITY recovery", style = MaterialTheme.typography.titleLarge)
            Text(
                "Resetting clears your desktop layout (windows, workspaces, pinned apps). " +
                    "Your documents and other apps are untouched.",
                style = MaterialTheme.typography.bodyLarge
            )
            Text(
                "If a system-level change (density, animation scale, refresh rate) needs " +
                    "reverting, use Settings → Advanced → Restore system settings, or run " +
                    "'pad8booster revert' from a computer.",
                style = MaterialTheme.typography.bodyMedium
            )
            Button(onClick = onReset) { Text("Reset desktop layout") }
            Button(onClick = onCancel) { Text("Cancel") }
        }
    }
}
