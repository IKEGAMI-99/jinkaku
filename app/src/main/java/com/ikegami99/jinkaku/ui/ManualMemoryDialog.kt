package com.ikegami99.jinkaku.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
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

private data class ManualMemoryType(val key: String, val label: String)

private val manualMemoryTypes = listOf(
    ManualMemoryType("PERSONA", "PERSONA（人格）"),
    ManualMemoryType("USER", "USER（ユーザー情報）"),
    ManualMemoryType("EPISODIC", "EPISODIC（出来事・思い出）"),
    ManualMemoryType("PREFERENCE", "PREFERENCE（好み・傾向）"),
    ManualMemoryType("PROJECT", "PROJECT（プロジェクト）"),
    ManualMemoryType("SELF", "SELF（AI自身の記憶）"),
    ManualMemoryType("RELATIONSHIP", "RELATIONSHIP（関係性）")
)

private fun typeLabel(key: String): String = manualMemoryTypes.firstOrNull { it.key == key }?.label ?: key

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
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(max = 560.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text(
                    "過去の出来事、Persona、好み、関係性などを手動で長期Memoryへ登録できます。",
                    style = MaterialTheme.typography.bodyMedium
                )

                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it },
                    modifier = Modifier.fillMaxWidth().heightIn(min = 130.dp),
                    label = { Text("Memory本文") },
                    minLines = 4,
                    maxLines = 10,
                    enabled = !saving
                )

                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Memory種別", style = MaterialTheme.typography.labelMedium)
                    Box(Modifier.fillMaxWidth()) {
                        OutlinedButton(
                            onClick = { typeMenu = true },
                            enabled = !saving,
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Text(typeLabel(type))
                        }
                        DropdownMenu(
                            expanded = typeMenu,
                            onDismissRequest = { typeMenu = false }
                        ) {
                            manualMemoryTypes.forEach { candidate ->
                                DropdownMenuItem(
                                    text = { Text(candidate.label) },
                                    onClick = {
                                        type = candidate.key
                                        typeMenu = false
                                    }
                                )
                            }
                        }
                    }
                    OutlinedButton(
                        onClick = {
                            type = "PERSONA"
                            text = vm.currentPersona()
                            importance = 3
                        },
                        enabled = !saving,
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("現在のPersonaを読み込む")
                    }
                }

                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("重要度", style = MaterialTheme.typography.labelMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        (1..3).forEach { value ->
                            FilterChip(
                                selected = importance == value,
                                onClick = { importance = value },
                                label = { Text(value.toString()) },
                                enabled = !saving
                            )
                        }
                    }
                    Text(
                        "1 = 補助情報 / 2 = 通常 / 3 = 人格や重要な事実など、優先して参照したいMemory",
                        style = MaterialTheme.typography.labelSmall
                    )
                }

                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    OutlinedTextField(
                        value = tags,
                        onValueChange = { tags = it },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("タグ（任意、カンマ区切り）") },
                        placeholder = { Text("例: jinkaku, android, local-ai") },
                        singleLine = true,
                        enabled = !saving
                    )
                    Text(
                        "タグはMemoryを後から検索・分類しやすくする補助キーワードです。必須ではありません。プロジェクト名、端末名、人物名、用途などを入れると検索の手掛かりになります。",
                        style = MaterialTheme.typography.labelSmall
                    )
                }

                if (saving) LinearProgressIndicator(Modifier.fillMaxWidth())
                if (error != null) Text(error!!, color = MaterialTheme.colorScheme.error)

                if (embeddingInstalled) {
                    Text(
                        "登録後、EmbeddingGemmaで自動再索引します。",
                        style = MaterialTheme.typography.labelSmall
                    )
                } else {
                    Text(
                        "現在はHashing-256で登録します。EmbeddingGemma導入後に再索引できます。",
                        style = MaterialTheme.typography.labelSmall
                    )
                }
                Spacer(Modifier.height(2.dp))
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
