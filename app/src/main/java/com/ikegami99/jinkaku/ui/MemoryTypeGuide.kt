package com.ikegami99.jinkaku.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ExpandLess
import androidx.compose.material.icons.rounded.ExpandMore
import androidx.compose.material.icons.rounded.LocalOffer
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

private data class MemoryGuideItem(
    val key: String,
    val japanese: String,
    val meaning: String,
    val example: String
)

private val memoryGuideItems = listOf(
    MemoryGuideItem(
        "PERSONA", "人格",
        "AIの性格・価値観・話し方など、Jinkaku自身の基本的な人格情報。",
        "技術の話では率直で、少し皮肉を交えて答える。"
    ),
    MemoryGuideItem(
        "USER", "ユーザー情報",
        "ユーザーについての比較的変わりにくい事実。",
        "POCO F7 Ultra 16GBモデルを使っている。"
    ),
    MemoryGuideItem(
        "EPISODIC", "出来事・思い出",
        "過去に起きた出来事や、一緒に経験したこと。",
        "2026年9月にJinkakuのAndroidアプリ開発を始めた。"
    ),
    MemoryGuideItem(
        "PREFERENCE", "好み・傾向",
        "ユーザーの好み、優先順位、会話や判断の傾向。",
        "ローカルLLMは多少精度が落ちても速度を優先する。"
    ),
    MemoryGuideItem(
        "PROJECT", "プロジェクト",
        "進行中・過去の制作物や、その目的・仕様・決定事項。",
        "Jinkakuは長期MemoryとPersonaを持つ完全ローカルAIアプリ。"
    ),
    MemoryGuideItem(
        "SELF", "AI自身の記憶",
        "Jinkaku自身が以前どう考えたか、何を選んだかという自己記憶。",
        "以前、スマホでは4K Contextを標準にする案を選んだ。"
    ),
    MemoryGuideItem(
        "RELATIONSHIP", "関係性",
        "ユーザーとJinkakuの関係や、二人のやり取りのスタイル。",
        "技術的な議論では遠慮せず問題点を指摘する関係。"
    )
)

@Composable
fun MemoryTypeGuide(modifier: Modifier = Modifier) {
    var expanded by remember { mutableStateOf(false) }

    Column(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        Surface(
            onClick = { expanded = !expanded },
            shape = MaterialTheme.shapes.large,
            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.7f)
        ) {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(Modifier.weight(1f)) {
                    Text("Memory種別と入力例", fontWeight = FontWeight.SemiBold)
                    Text(
                        "PERSONA / USER / EPISODIC / PREFERENCE / PROJECT / SELF / RELATIONSHIP",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Icon(
                    imageVector = if (expanded) Icons.Rounded.ExpandLess else Icons.Rounded.ExpandMore,
                    contentDescription = null
                )
            }
        }

        if (expanded) {
            Text(
                "どの種類に入れるか迷った時の目安です。意味が近いものを選べば十分です。7種類すべて表示しています。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(horizontal = 4.dp)
            )

            memoryGuideItems.forEach { item ->
                Surface(
                    shape = MaterialTheme.shapes.medium,
                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.52f)
                ) {
                    Column(
                        Modifier.fillMaxWidth().padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(5.dp)
                    ) {
                        Text("${item.key}  ·  ${item.japanese}", fontWeight = FontWeight.SemiBold)
                        Text(
                            item.meaning,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(
                            "入力例  ${item.example}",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary
                        )
                    }
                }
            }

            Surface(
                shape = MaterialTheme.shapes.medium,
                color = MaterialTheme.colorScheme.tertiaryContainer.copy(alpha = 0.55f)
            ) {
                Row(
                    Modifier.fillMaxWidth().padding(14.dp),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                    verticalAlignment = Alignment.Top
                ) {
                    Icon(
                        Icons.Rounded.LocalOffer,
                        contentDescription = null,
                        modifier = Modifier.size(20.dp),
                        tint = MaterialTheme.colorScheme.tertiary
                    )
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("タグについて", fontWeight = FontWeight.SemiBold)
                        Text(
                            "タグはMemoryを後から検索・分類しやすくする補助キーワードです。必須ではありません。プロジェクト名、端末名、人物名、用途などをカンマ区切りで付けます。",
                            style = MaterialTheme.typography.bodySmall
                        )
                        Text(
                            "例  jinkaku, android, local-ai, speed",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.tertiary
                        )
                    }
                }
            }
        }
    }
}
