package com.ikegami99.jinkaku.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
    Column(modifier = modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Memory種別の意味と入力例", fontWeight = FontWeight.SemiBold)
        memoryGuideItems.forEach { item ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(10.dp)) {
                    Text("${item.key}（${item.japanese}）", fontWeight = FontWeight.SemiBold)
                    Text(item.meaning, style = MaterialTheme.typography.bodySmall)
                    Spacer(Modifier.height(2.dp))
                    Text("例: ${item.example}", style = MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
}
