package dev.padfinity.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import dev.padfinity.app.desktop.DesktopScreen
import dev.padfinity.app.desktop.DesktopViewModel
import dev.padfinity.app.ui.theme.PadfinityTheme

class MainActivity : ComponentActivity() {

    private val viewModel: DesktopViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // Edge-to-edge: the desktop owns the whole panel, including under the
        // system bars. Insets are applied inside the taskbar, not around it.
        enableEdgeToEdge()
        setContent {
            PadfinityTheme(darkTheme = true) {
                Surface(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(MaterialTheme.colorScheme.background),
                    color = MaterialTheme.colorScheme.background
                ) {
                    DesktopScreen(viewModel = viewModel)
                }
            }
        }
    }
}
