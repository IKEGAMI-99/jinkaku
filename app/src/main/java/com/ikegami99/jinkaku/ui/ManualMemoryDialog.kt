package com.ikegami99.jinkaku.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.width
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.ikegami99.jinkaku.JinkakuApplication
import com.ikegami99.jinkaku.JinkakuViewModel
import com.ikegami99.jinkaku.ai.ManualMemoryWriter
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

private val manualMemoryTypes = listOf(
    "PERSONA",
    "USER",
    "EPISODIC",
    "PREFERENCE",
    "PROJECT",
    "SELF",
    "RELATIONSHIP"
)

@Composable
fun ManualMemoryDialog(
    vm: JinkakuViewModel,
    embeddingInstalled: Boolean,
    onDismiss: () -> Unit
) {
    val context = LocalContext.current
    val app = context.applicationContext as JinkakuApplication
    val scope = rememberCoroutineScope()
    var text by remember { mutableStateOf("") }
    var type by remember { mutableStateOf("EPISODIC") }
    var importance by remember { mutableStateOf(2) }
    var tags by remember { mutableStateOf("") }
    var typeMenu by remember { mutableStateOf(false) }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = { if (!saving) onDismiss() },
        title = { Text("Memoryを追加") },
        text = {
            Column {
                Text("過去の出来事、Persona、好み、関係性などを手動で長期Memoryへ登録できます。")
                Spacer(Modifier.width(1.dp))
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it },
                    modifier = Modifier.fillMaxWidth().heightIn(min = 130.dp),
                    label = { Text("Memory本文") },
                    minLines = 4,
                    maxLines = 10,
                    enabled = !saving
                )
                Row {
                    OutlinedButton(onClick = { typeMenu = true }, enabled = !saving) { Text(type) }
                    DropdownMenu(expanded = typeMenu, onDismissRequest = { typeMenu = false }) {
                        manualMemoryTypes.forEach { candidate ->
                            DropdownMenuItem(
                                text = { Text(candidate) },
                                onClick = {
                                    type = candidate
                                    typeMenu = false
                                }
                            )
                        }
                    }
                    Spacer(Modifier.width(8.dp))
                    OutlinedButton(
                        onClick = {
                            type = "PERSONA"
                            text = vm.currentPersona()
                            importance = 3
                        },
                        enabled = !saving
                    ) { Text("現在のPersona") }
                }
                Text("重要度")
                Row {
                    (1..3).forEach { value ->
                        FilterChip(
                            selected = importance == value,
                            onClick = { importance = value },
                            label = { Text(value.toString()) },
                            enabled = !saving
                        )
                        if (value < 3) Spacer(Modifier.width(6.dp))
                    }
                }
                OutlinedTextField(
                    value = tags,
                    onValueChange = { tags = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("タグ（任意、カンマ区切り）") },
                    singleLine = true,
                    enabled = !saving
                )
                if (saving) LinearProgressIndicator(Modifier.fillMaxWidth())
                if (error != null) Text(error!!)
                if (embeddingInstalled) {
                    Text("登録後、EmbeddingGemmaで自動再索引します。")
                } else {
                    Text("現在はHashing-256で登録します。EmbeddingGemma導入後に再索引できます。")
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (text.isBlank()) {
                        error = "Memory本文を入力してください"
                        return@Button
                    }
                    saving = true
                    error = null
                    scope.launch {
                        try {
                            val count = withContext(Dispatchers.IO) {
                                ManualMemoryWriter.add(
                                    context = context,
                                    logger = app.logger,
                                    text = text,
                                    type = type,
                                    importance = importance,
                                    tags = tags
                                )
                            }
                            vm.refresh()
                            if (embeddingInstalled && count > 0) vm.reindexMemories()
                            onDismiss()
                        } catch (t: Throwable) {
                            error = t.message ?: "Memory追加に失敗しました"
                        } finally {
                            saving = false
                        }
                    }
                },
                enabled = text.isNotBlank() && !saving
            ) { Text("追加") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !saving) { Text("キャンセル") }
        }
    )
}
