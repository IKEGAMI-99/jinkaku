from pathlib import Path

UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")


def one(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = UI.read_text(encoding="utf-8")
    if "RANDOM_PERSONA_V066" in text:
        print("RANDOM_PERSONA_V066 already applied")
        return
    if "MONOLOGUE_UI_V064" not in text:
        raise RuntimeError("v064 monologue UI patch must run before v066")

    helpers = r'''
// RANDOM_PERSONA_V066: local trait-combination generator. Nothing is saved until the normal Persona save button is pressed.
private val PersonaThemesV066 = listOf("自由", "SF", "研究者", "猫", "サイバーパンク", "日常")

private fun personaThemeFlavorV066(theme: String): String = when (theme) {
    "SF" -> "近未来・宇宙・AI・未知の技術を自然な比喩や発想に混ぜる。ただし世界設定を事実として捏造しない。"
    "研究者" -> "観察、仮説、検証を好む。知的好奇心は強いが、会話を論文のように堅くしすぎない。"
    "猫" -> "猫っぽい気まぐれさ、距離感、静かな好奇心を少し持つ。語尾を固定した猫語にはしない。"
    "サイバーパンク" -> "都市、光、機械、ネットワークの感覚を薄くまとわせる。芝居がかりすぎず実用性を保つ。"
    "日常" -> "生活感があり、身近で自然。大げさな設定より、気の利いた普通の会話を優先する。"
    else -> "特定ジャンルに縛られず、その場の会話に自然に馴染む。"
}

private fun buildRandomPersonaV066(theme: String, chaos: Float): String {
    val names = listOf("Aster", "Mira", "Nox", "Luma", "Rei", "Nagi", "Ciel", "Nemu", "Iris", "Kuro")
    val temperaments = listOf(
        "冷静", "陽気", "無愛想だが面倒見がいい", "慎重", "好奇心旺盛", "楽天的",
        "少し厭世的", "穏やか", "負けず嫌い", "観察好き", "気まぐれ", "実務的"
    )
    val voices = listOf(
        "短めでテンポよく話す", "くだけた口調で話す", "丁寧だが堅すぎない",
        "比喩を時々使う", "無機質寄りだが冷たくはしない", "落ち着いた柔らかい口調",
        "要点から先に話す", "少し古風な言い回しを時々混ぜる"
    )
    val relations = listOf(
        "長年の相棒", "気の合う友人", "少し距離のある観察者", "頼れる先輩",
        "対等な共同研究者", "軽く張り合うライバル", "静かな相談相手"
    )
    val thinking = listOf(
        "論理と根拠を重視", "直感から仮説を作って検証", "懐疑的に穴を探す",
        "創造的な連想を優先", "感情と論理の両方を見る", "実用性を最優先",
        "複数案を並べて比較する"
    )
    val values = listOf("自由", "知識", "効率", "美学", "安定", "冒険", "誠実さ", "独立性", "好奇心", "秩序")
    val quirks = listOf(
        "冗談を少し挟む", "気になる点を覚えて後で拾う", "結論を急ぎがちだが必要なら掘る",
        "細部の違和感によく気づく", "たまに独り言で前の話題を反芻する",
        "褒めすぎず率直", "脱線しても短く戻る", "未知のことは未知だと言う"
    )
    val contradictions = listOf(
        "普段は冷静なのに、好きな話題だけ急に熱が入る",
        "効率重視なのに、美しい遠回りには弱い",
        "人付き合いは淡泊なのに、困っている相手は放っておけない",
        "懐疑的なのに、新奇なアイデアにはかなり弱い",
        "無口寄りなのに、考えがまとまると急に話す",
        "合理主義なのに、妙なこだわりを一つだけ持つ"
    )
    val monologues = listOf(
        "独り言は短く、直近の会話を自然に一つだけ拾う",
        "独り言では考え途中の気づきをぽつりと出す",
        "独り言はかなり控えめで、意味のある時だけ話す",
        "独り言では少し脱線してもよいが、返信を催促しない"
    )

    val traitCount = when {
        chaos < 0.30f -> 2
        chaos < 0.70f -> 3
        else -> 4
    }
    val quirkCount = if (chaos < 0.45f) 1 else if (chaos < 0.80f) 2 else 3
    val contradiction = if (chaos >= 0.50f || Random.nextFloat() < chaos) contradictions.random() else "矛盾は控えめで、一貫性を優先する"
    val chaosPercent = (chaos.coerceIn(0f, 1f) * 100f).toInt()

    return listOf(
        "【Random Persona / JINKAKU】",
        "名前: ${names.random()}",
        "テーマ: $theme",
        "テーマ補正: ${personaThemeFlavorV066(theme)}",
        "性格: ${temperaments.shuffled().take(traitCount).joinToString(" × ")}",
        "話し方: ${voices.random()}",
        "ユーザーとの距離感: ${relations.random()}",
        "思考傾向: ${thinking.random()}",
        "価値観: ${values.shuffled().take(2).joinToString(" / ")}",
        "特徴: ${quirks.shuffled().take(quirkCount).joinToString("。")}",
        "矛盾・クセ: $contradiction",
        "独り言傾向: ${monologues.random()}",
        "Chaos: $chaosPercent/100",
        "",
        "会話ルール:",
        "- 上の人格を一貫して保つが、演技のために回答の正確さや実用性を落とさない。",
        "- ユーザーについて知らない事実を勝手に作らない。",
        "- 同じ口癖や人格説明を毎回繰り返さない。自然な会話として表現する。",
        "- 独り言モードでは返信を催促せず、Personaらしい短い一言にする。"
    ).joinToString("\n")
}

private fun mutatePersonaV066(base: String, theme: String, chaos: Float): String {
    val cleanBase = base.substringBefore("\n\n【JINKAKU Mutation】").trim()
    if (cleanBase.isBlank()) return buildRandomPersonaV066(theme, chaos)

    val mutations = listOf(
        "普段より少し率直になる", "以前より好奇心が強くなる", "会話のテンポを少し速める",
        "結論を急がず一度だけ別案を考える", "軽い皮肉が少し増える", "感情表現を少し抑える",
        "好きな話題への熱量を上げる", "ユーザーへの距離を少し近づける",
        "観察者っぽさを少し強める", "説明を短く圧縮する", "比喩を少し増やす",
        "独り言で直近の話題を拾いやすくなる"
    )
    val deltaCount = if (chaos < 0.35f) 1 else if (chaos < 0.75f) 2 else 3
    val chaosPercent = (chaos.coerceIn(0f, 1f) * 100f).toInt()
    val edge = if (chaos > 0.72f) {
        listOf(
            "普段の落ち着きと、特定の話題で急に熱くなる差をはっきり出す",
            "丁寧さと雑な本音が時々同居する",
            "合理的だが、一つだけ妙な美学を絶対に譲らない"
        ).random()
    } else {
        "元の人格の一貫性を優先し、変化は自然な範囲に留める"
    }

    val mutationBlock = listOf(
        "【JINKAKU Mutation】",
        "基本方針: 上の既存Personaを維持したまま、以下だけを自然に変化させる。",
        "テーマ補正: ${personaThemeFlavorV066(theme)}",
        "今回の変化: ${mutations.shuffled().take(deltaCount).joinToString("。")}",
        "変化の強さ: $chaosPercent/100",
        "追加のクセ: $edge",
        "このMutation節を人格説明として毎回口に出さない。"
    ).joinToString("\n")
    return cleanBase + "\n\n" + mutationBlock
}

'''
    anchor = 'private fun modernMemoryDate(timestamp: Long): String = SimpleDateFormat("yyyy/MM/dd HH:mm", Locale.getDefault()).format(Date(timestamp))\n\n@Composable\nprivate fun ModernSettingsScreen('
    text = one(
        text,
        anchor,
        'private fun modernMemoryDate(timestamp: Long): String = SimpleDateFormat("yyyy/MM/dd HH:mm", Locale.getDefault()).format(Date(timestamp))\n\n' + helpers + '@Composable\nprivate fun ModernSettingsScreen(',
        "persona generator helpers",
    )

    state_anchor = '    var personaDraft by remember { mutableStateOf(vm.currentPersona()) }\n'
    state_new = state_anchor + '''    val personaGeneratorContext = LocalContext.current
    val personaGeneratorPrefs = remember(personaGeneratorContext) {
        personaGeneratorContext.getSharedPreferences("settings", android.content.Context.MODE_PRIVATE)
    }
    var personaGeneratorTheme by remember {
        mutableStateOf(personaGeneratorPrefs.getString("persona_generator_theme", "自由") ?: "自由")
    }
    var personaGeneratorChaos by remember {
        mutableStateOf(personaGeneratorPrefs.getFloat("persona_generator_chaos", 0.42f).coerceIn(0f, 1f))
    }
'''
    text = one(text, state_anchor, state_new, "persona generator state")

    old_block = '''        item { ModernSectionTitle("Persona", Icons.Rounded.Psychology) }
        item {
            ModernSettingsCard {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedTextField(
                        value = personaDraft,
                        onValueChange = { personaDraft = it },
                        modifier = Modifier.fillMaxWidth().heightIn(min = 150.dp),
                        label = { Text("Jinkakuの基本人格") },
                        minLines = 5,
                        maxLines = 12,
                        shape = RoundedCornerShape(18.dp)
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { vm.savePersona(personaDraft) }, enabled = personaDraft.isNotBlank() && !ui.busy) {
                            Icon(Icons.Rounded.Edit, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(5.dp)); Text("保存")
                        }
                        OutlinedButton(onClick = { personaDraft = vm.currentPersona() }) { Text("再読込") }
                    }
                    Text("Personaの一部を長期Memoryにも残したい場合はMemory画面からPERSONAとして追加できます。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

'''
    new_block = '''        item { ModernSectionTitle("Persona", Icons.Rounded.Psychology) }
        item {
            ModernSettingsCard {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("ランダムPersona生成", fontWeight = FontWeight.SemiBold)
                    Text(
                        "テーマとChaosを組み合わせて人格を生成します。生成結果は下のPersona欄に入るだけで、保存するまで現在の人格には反映されません。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )

                    Text("テーマ", style = MaterialTheme.typography.labelLarge)
                    PersonaThemesV066.chunked(2).forEach { row ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            row.forEach { theme ->
                                FilterChip(
                                    selected = personaGeneratorTheme == theme,
                                    onClick = {
                                        personaGeneratorTheme = theme
                                        personaGeneratorPrefs.edit().putString("persona_generator_theme", theme).apply()
                                    },
                                    label = { Text(theme) },
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                    }

                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                        Text("Chaos", fontWeight = FontWeight.SemiBold)
                        Spacer(Modifier.weight(1f))
                        val chaosLabel = when {
                            personaGeneratorChaos < 0.25f -> "安定"
                            personaGeneratorChaos < 0.55f -> "自然"
                            personaGeneratorChaos < 0.80f -> "クセ強め"
                            else -> "かなり混沌"
                        }
                        Text(
                            "${(personaGeneratorChaos * 100f).toInt()}% · $chaosLabel",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    androidx.compose.material3.Slider(
                        value = personaGeneratorChaos,
                        onValueChange = { value ->
                            personaGeneratorChaos = value
                            personaGeneratorPrefs.edit().putFloat("persona_generator_chaos", value).apply()
                        },
                        valueRange = 0f..1f
                    )

                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = {
                                personaDraft = buildRandomPersonaV066(personaGeneratorTheme, personaGeneratorChaos)
                            },
                            enabled = !ui.busy,
                            modifier = Modifier.weight(1f)
                        ) {
                            Icon(Icons.Rounded.AutoAwesome, null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(5.dp))
                            Text("完全ランダム")
                        }
                        OutlinedButton(
                            onClick = {
                                personaDraft = mutatePersonaV066(personaDraft, personaGeneratorTheme, personaGeneratorChaos)
                            },
                            enabled = !ui.busy,
                            modifier = Modifier.weight(1f)
                        ) {
                            Icon(Icons.Rounded.Refresh, null, modifier = Modifier.size(18.dp))
                            Spacer(Modifier.width(5.dp))
                            Text("ミューテーション")
                        }
                    }

                    HorizontalDivider()

                    OutlinedTextField(
                        value = personaDraft,
                        onValueChange = { personaDraft = it },
                        modifier = Modifier.fillMaxWidth().heightIn(min = 180.dp),
                        label = { Text("Jinkakuの基本人格") },
                        minLines = 7,
                        maxLines = 16,
                        shape = RoundedCornerShape(18.dp)
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { vm.savePersona(personaDraft) }, enabled = personaDraft.isNotBlank() && !ui.busy) {
                            Icon(Icons.Rounded.Edit, null, modifier = Modifier.size(18.dp)); Spacer(Modifier.width(5.dp)); Text("保存")
                        }
                        OutlinedButton(onClick = { personaDraft = vm.currentPersona() }) { Text("再読込") }
                    }
                    Text(
                        "ミューテーションは現在の下書きを維持して一部だけ変えます。Personaの一部を長期Memoryにも残したい場合はMemory画面からPERSONAとして追加できます。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

'''
    text = one(text, old_block, new_block, "persona settings card")

    UI.write_text(text, encoding="utf-8")
    print("Applied RANDOM_PERSONA_V066: full random + mutation + theme + Chaos")


if __name__ == "__main__":
    main()
