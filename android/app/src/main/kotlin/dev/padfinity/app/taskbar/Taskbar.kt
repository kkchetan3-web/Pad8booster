package dev.padfinity.app.taskbar

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import dev.padfinity.app.desktop.DesktopViewModel
import dev.padfinity.app.ui.theme.LocalAccent
import dev.padfinity.engine.TaskbarModel

/**
 * Bottom taskbar: launcher, running windows, workspace switcher, clock.
 *
 * Item composition rules live in the engine's [TaskbarModel] (pinned order is
 * stable, focused first, deduped) so they are unit-tested rather than untested UI
 * logic. This composable only renders.
 */
@Composable
fun PadfinityTaskbar(
    viewModel: DesktopViewModel,
    modifier: Modifier = Modifier,
    onOpenLauncher: () -> Unit
) {
    val accent = LocalAccent.current
    val model = remember { TaskbarModel(maxItems = 8) }
    var showWorkspaces by remember { mutableStateOf(false) }

    val labels = viewModel.windows.associate { it.id to it.title }
    val items = model.build(
        labels = labels,
        running = viewModel.windows.map { it.id },
        focused = viewModel.focusedId,
        recents = emptyList()
    )

    Row(
        modifier = modifier
            .padding(horizontal = 14.dp, vertical = 12.dp)
            .height(52.dp)
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.94f))
            .border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(14.dp))
            .padding(horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        // Launcher
        Box(
            modifier = Modifier
                .size(38.dp)
                .clip(RoundedCornerShape(9.dp))
                .background(accent.primary.copy(alpha = 0.16f))
                .clickable(onClick = onOpenLauncher),
            contentAlignment = Alignment.Center
        ) { Text("⌘", style = MaterialTheme.typography.titleLarge) }

        // Workspace switcher
        Box(
            modifier = Modifier
                .height(32.dp)
                .clip(RoundedCornerShape(8.dp))
                .background(MaterialTheme.colorScheme.surface)
                .clickable { showWorkspaces = !showWorkspaces }
                .padding(horizontal = 10.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(viewModel.workspaceName, style = MaterialTheme.typography.labelLarge)
        }

        if (showWorkspaces) {
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                viewModel.workspaceIds.forEach { id ->
                    val name = id.substringAfterLast('.')
                    Box(
                        modifier = Modifier
                            .height(32.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(
                                if (id == viewModel.activeWorkspace) accent.soft
                                else MaterialTheme.colorScheme.surface
                            )
                            .clickable {
                                viewModel.switchWorkspace(id)
                                showWorkspaces = false
                            }
                            .padding(horizontal = 9.dp),
                        contentAlignment = Alignment.Center
                    ) { Text(name, style = MaterialTheme.typography.labelSmall) }
                }
            }
        }

        // Running windows
        Row(
            modifier = Modifier.weight(1f),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            items.forEach { item ->
                val window = viewModel.windows.firstOrNull { it.id == item.key }
                if (window?.surfaceRoute != null || window != null) {
                    Box(
                        modifier = Modifier
                            .height(34.dp)
                            .clip(RoundedCornerShape(8.dp))
                            .background(
                                if (item.focused) accent.primary.copy(alpha = 0.18f)
                                else MaterialTheme.colorScheme.surface
                            )
                            .clickable {
                                if (item.focused) viewModel.minimize(item.key)
                                else viewModel.focus(item.key)
                            }
                            .padding(horizontal = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            item.label,
                            style = MaterialTheme.typography.labelLarge,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }
            }
        }

        // Clock
        Text(
            text = rememberClockText(),
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 8.dp)
        )
    }
}

@Composable
private fun rememberClockText(): String {
    val time = remember {
        java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault())
            .format(java.util.Date())
    }
    return time
}
