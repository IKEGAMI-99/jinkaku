package com.ikegami99.jinkaku

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ikegami99.jinkaku.ui.BackendControlOverlay
import com.ikegami99.jinkaku.ui.ModernJinkakuApp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            val vm: JinkakuViewModel = viewModel(factory = JinkakuViewModel.factory(application))
            Box(Modifier.fillMaxSize()) {
                ModernJinkakuApp(vm)
                BackendControlOverlay()
            }
        }
    }
}
