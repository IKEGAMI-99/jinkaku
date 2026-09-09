package com.ikegami99.jinkaku.ui

import android.content.Context
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.ikegami99.jinkaku.JinkakuViewModel
import com.ikegami99.jinkaku.R
import kotlinx.coroutines.delay

@Composable
fun BrandedJinkakuApp(vm: JinkakuViewModel) {
    val context = LocalContext.current
    val prefs = remember(context) {
        context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    }
    var darkMode by remember {
        mutableStateOf(prefs.getBoolean("dark_mode", false))
    }

    LaunchedEffect(prefs) {
        while (true) {
            val next = prefs.getBoolean("dark_mode", false)
            if (next != darkMode) darkMode = next
            delay(250)
        }
    }

    Box(Modifier.fillMaxSize()) {
        ModernJinkakuApp(vm)

        Box(
            modifier = Modifier
                .statusBarsPadding()
                .padding(start = 62.dp, top = 9.dp)
                .width(158.dp)
                .height(24.dp)
                .background(
                    if (darkMode) Color(0xFF0C0D12)
                    else Color(0xFFF8F7FC)
                )
        ) {
            Image(
                painter = painterResource(R.drawable.jinkaku_wordmark),
                contentDescription = "Jinkaku",
                contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxSize()
            )
        }
    }
}
