package com.ikegami99.jinkaku.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Memory
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.ikegami99.jinkaku.ai.BackendPreferences
import com.ikegami99.jinkaku.ai.InferenceBackend
import com.ikegami99.jinkaku.ai.InferenceTelemetry

@Composable
fun BackendControlOverlay() {
    val context = LocalContext.current
    val prefs = remember(context) { BackendPreferences(context) }
    val initial = remember { prefs.get() }
    var selected by remember { mutableStateOf(initial.mode) }
    var gpuLayers by remember { mutableIntStateOf(initial.gpuLayers) }
    var dialog by remember { mutableStateOf(false) }
    val telemetry by InferenceTelemetry.state.collectAsStateWithLifecycle()

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(top = 58.dp, end = 12.dp),
        contentAlignment = Alignment.TopEnd
    ) {
        AssistChip(
            onClick = { dialog = true },
            label = {
                Text(
                    if (telemetry.phase == "IDLE" || telemetry.phase == "LOADING") selected.label else telemetry.backend,
                    style = MaterialTheme.typography.labelSmall
                )
            },
            leadingIcon = { Icon(Icons.Rounded.Memory, null) }
        )
    }

    if (dialog) {
        AlertDialog(
            onDismissRequest = { dialog = false },
            title = { Text("推論Backend") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(
                        "Vulkanは使用しません。GPUはAdreno OpenCLを使い、失敗した場合は自動でCPUへ戻ります。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        InferenceBackend.entries.forEach { mode ->
                            FilterChip(
                                selected = selected == mode,
                                onClick = {
                                    selected = mode
                                    prefs.setMode(mode)
                                },
                                label = { Text(mode.label) }
                            )
                        }
                    }
                    if (selected == InferenceBackend.AUTO || selected == InferenceBackend.HYBRID) {
                        Text("GPU offload layers", fontWeight = FontWeight.SemiBold)
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            listOf(8, 16, 20, 24, 32, 42).forEach { layers ->
                                FilterChip(
                                    selected = gpuLayers == layers,
                                    onClick = {
                                        gpuLayers = layers
                                        prefs.setGpuLayers(layers)
                                    },
                                    label = { Text(layers.toString()) }
                                )
                            }
                        }
                    }
                    Text(
                        when (selected) {
                            InferenceBackend.AUTO -> "Auto: OpenCLが使えれば指定layersをGPUへ、使えなければCPU。"
                            InferenceBackend.CPU -> "CPU: 最も安定。GPUを一切使いません。"
                            InferenceBackend.GPU -> "GPU: 全レイヤーをOpenCLへoffloadします。VRAM不足時はCPUへfallbackします。"
                            InferenceBackend.HYBRID -> "CPU + GPU: 指定したレイヤーだけAdrenoへoffloadします。"
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Spacer(Modifier.width(1.dp))
                    Text("現在の実行Backend: ${telemetry.backend}", style = MaterialTheme.typography.labelMedium)
                }
            },
            confirmButton = { TextButton(onClick = { dialog = false }) { Text("閉じる") } }
        )
    }
}
