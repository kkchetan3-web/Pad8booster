package dev.padfinity.app.desktop

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import dev.padfinity.engine.DeviceMetrics
import dev.padfinity.engine.InsightEngine
import dev.padfinity.engine.Rect
import dev.padfinity.engine.ThermalStatus

/** Pixel→dp positioning. Single conversion point for the whole desktop. */
fun Modifier.offsetPx(bounds: Rect, density: Density): Modifier {
    val x = with(density) { bounds.left.toDp() }
    val y = with(density) { bounds.top.toDp() }
    return this.then(Modifier.offset { IntOffset(x.roundToPx(), y.roundToPx()) })
}

/** Clickable without pulling in the experimental combinedClickable API. */
fun Modifier.androidxClickable(onClick: () -> Unit): Modifier =
    this.then(androidx.compose.foundation.clickable(onClick = onClick))

@Composable
fun NoteSurface() {
    var text by remember { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(14.dp)) {
        Text("Notes", style = MaterialTheme.typography.titleLarge)
        BasicTextField(
            value = text,
            onValueChange = { text = it },
            modifier = Modifier.fillMaxWidth().padding(top = 10.dp),
            textStyle = MaterialTheme.typography.bodyLarge.copy(
                color = MaterialTheme.colorScheme.onSurface
            )
        )
    }
}

/**
 * Insights surface. Metrics are placeholders wired to the real engine; the
 * Collection layer reads them from public Android APIs only (see PERMISSIONS.md).
 */
@Composable
fun InsightsSurface() {
    val sample = DeviceMetrics(
        totalRamMb = 12000,
        availableRamMb = 4200,
        storageTotalGb = 256.0,
        storageUsedGb = 172.0,
        batteryLevel = 82,
        batteryTempC = 29.1,
        thermalStatus = ThermalStatus.NONE,
        refreshRateHz = 144f,
        enabledPackageCount = 214
    )
    val insights = remember(sample) { InsightEngine.evaluate(sample) }
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surface).padding(14.dp)) {
        Text("Insights", style = MaterialTheme.typography.titleLarge)
        Text(
            "Sample values — real collection is wired in DeviceMetricsCollector.",
            style = MaterialTheme.typography.labelSmall
        )
        insights.forEach { insight ->
            Text(
                text = "• ${insight.title}",
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.padding(top = 10.dp)
            )
            Text(insight.detail, style = MaterialTheme.typography.bodyMedium)
        }
        if (insights.isEmpty()) {
            Text("Nothing needs attention on this device.", style = MaterialTheme.typography.bodyMedium)
        }
    }
}
