package dev.padfinity.app.launcher

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import dev.padfinity.app.ui.theme.LocalAccent

data class LaunchableApp(val packageName: String, val label: String)

/**
 * Searchable launcher.
 *
 * Uses the `<queries>` element from the manifest, not `QUERY_ALL_PACKAGES`: we
 * only resolve apps that declare a launcher activity, which is exactly what a
 * launcher needs and nothing more.
 */
@Composable
fun LauncherOverlay(
    onDismiss: () -> Unit,
    onOpenApp: (String, String) -> Unit
) {
    val context = LocalContext.current
    val accent = LocalAccent.current
    var query by remember { mutableStateOf("") }
    val apps = remember { loadLaunchableApps(context) }
    val filtered = remember(query, apps) {
        if (query.isBlank()) apps
        else apps.filter {
            it.label.contains(query, ignoreCase = true) ||
                it.packageName.contains(query, ignoreCase = true)
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background.copy(alpha = 0.97f))
            .clickable(onClick = onDismiss)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(28.dp)
                .clickable(enabled = false) { }
        ) {
            Text("All apps", style = MaterialTheme.typography.titleLarge)
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 14.dp)
                    .clip(RoundedCornerShape(9.dp))
                    .background(MaterialTheme.colorScheme.surface)
                    .border(1.dp, accent.primary.copy(alpha = 0.5f), RoundedCornerShape(9.dp))
                    .padding(12.dp)
            ) {
                BasicTextField(
                    value = query,
                    onValueChange = { query = it },
                    textStyle = MaterialTheme.typography.bodyLarge.copy(
                        color = MaterialTheme.colorScheme.onSurface
                    ),
                    decorationBox = { inner ->
                        if (query.isEmpty()) {
                            Text("Search apps…", style = MaterialTheme.typography.bodyMedium)
                        }
                        inner()
                    }
                )
            }
            LazyVerticalGrid(
                columns = GridCells.Adaptive(minSize = 168.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(filtered, key = { it.packageName }) { app ->
                    Column(
                        modifier = Modifier
                            .clip(RoundedCornerShape(9.dp))
                            .background(MaterialTheme.colorScheme.surface)
                            .clickable {
                                // Two things happen: the app joins the taskbar as a
                                // SYSTEM_APP entry, and the OS actually launches it.
                                onOpenApp(app.packageName, app.label)
                                launchApp(context, app.packageName)
                            }
                            .padding(12.dp)
                    ) {
                        Text(app.label, style = MaterialTheme.typography.bodyLarge)
                        Text(
                            app.packageName,
                            style = MaterialTheme.typography.labelSmall,
                            maxLines = 1
                        )
                    }
                }
            }
        }
    }
}

private fun loadLaunchableApps(context: Context): List<LaunchableApp> {
    val pm = context.packageManager
    val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
    val resolved = pm.queryIntentActivities(intent, PackageManager.MATCH_DEFAULT_ONLY)
    return resolved
        .map { it.activityInfo.applicationInfo.packageName to it.loadLabel(pm).toString() }
        .distinctBy { it.first }
        .map { (pkg, label) -> LaunchableApp(pkg, label) }
        .sortedBy { it.label.lowercase() }
}

private fun launchApp(context: Context, packageName: String) {
    val intent = context.packageManager.getLaunchIntentForPackage(packageName) ?: return
    intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    runCatching { context.startActivity(intent) }
    // A failure here means the app vanished between query and tap; harmless.
}
