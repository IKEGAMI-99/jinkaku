from pathlib import Path

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
ENGINE = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E4BEngine.kt")
UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")


def one(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_view_model() -> None:
    text = VM.read_text(encoding="utf-8")
    if "SHORT_REPLY_STYLE_V067" in text:
        print("SHORT_REPLY_STYLE_V067 already applied to JinkakuViewModel")
        return
    if "MONOLOGUE_MODE_V064" not in text or "TAVILY_WEB_SEARCH_V062" not in text:
        raise RuntimeError("v062/v064 generated ViewModel must exist before v067")

    text = one(
        text,
        '    val temperature: Float = 1.0f,\n',
        '    val temperature: Float = 1.0f,\n'
        '    val replyLengthMode: String = "SHORT",\n',
        "UiState reply length mode",
    )

    text = one(
        text,
        '            webSearchConfigured = !prefs.getString(KEY_TAVILY_API_KEY, "").isNullOrBlank()\n',
        '            webSearchConfigured = !prefs.getString(KEY_TAVILY_API_KEY, "").isNullOrBlank(),\n'
        '            replyLengthMode = prefs.getString("reply_length_mode", "SHORT") ?: "SHORT"\n',
        "initial reply length preference",
    )

    text = one(
        text,
        '                    val system = buildSystemPrompt(relevant, _ui.value.thinkingEnabled)\n'
        '                    val systemWithWeb = if (webResults.isEmpty()) system else system + "\\n\\n" + buildWebContext(webResults)\n',
        '                    val replyProfile = resolveReplyProfileV067(clean)\n'
        '                    val system = buildSystemPrompt(relevant, _ui.value.thinkingEnabled) + "\\n\\n" + buildReplyStyleRulesV067(replyProfile)\n'
        '                    val systemWithWeb = if (webResults.isEmpty()) system else system + "\\n\\n" + buildWebContext(webResults)\n',
        "reply profile in normal send",
    )

    text = one(
        text,
        '''                        systemPrompt = systemWithWeb,
                        history = history,
                        contextSize = _ui.value.contextSize,
                        enableThinking = _ui.value.thinkingEnabled,
                        topK = _ui.value.topK,
                        temperature = _ui.value.temperature
''',
        '''                        systemPrompt = systemWithWeb,
                        history = history,
                        contextSize = _ui.value.contextSize,
                        enableThinking = _ui.value.thinkingEnabled,
                        topK = _ui.value.topK,
                        temperature = _ui.value.temperature,
                        maxGenerationTokens = replyProfile.maxTokens
''',
        "normal generation dynamic token limit",
    )

    helpers = r'''
    // SHORT_REPLY_STYLE_V067: short conversational replies by default, with explicit detail requests allowed to expand.
    private data class ReplyProfileV067(
        val mode: String,
        val maxTokens: Int,
        val detailed: Boolean,
        val explicitlyBrief: Boolean
    )

    private fun normalizeReplyLengthModeV067(value: String): String = when (value.uppercase()) {
        "NORMAL" -> "NORMAL"
        "LONG" -> "LONG"
        "UNLIMITED" -> "UNLIMITED"
        else -> "SHORT"
    }

    fun setReplyLengthMode(value: String) {
        if (_ui.value.busy || anyModelImporting()) return
        val mode = normalizeReplyLengthModeV067(value)
        prefs.edit().putString("reply_length_mode", mode).apply()
        _ui.value = _ui.value.copy(replyLengthMode = mode)
        logger.i("CHAT", "Reply length mode=$mode")
    }

    private fun resolveReplyProfileV067(userMessage: String): ReplyProfileV067 {
        val q = userMessage.lowercase()
        val briefTriggers = listOf(
            "短く", "簡潔", "一言", "要点だけ", "手短", "briefly", "concise", "short answer", "简短"
        )
        val detailTriggers = listOf(
            "詳しく", "詳細", "説明して", "説明してください", "深掘り", "深く", "具体的に",
            "丁寧に", "長め", "徹底的", "解説", "in detail", "detailed", "explain", "deep dive",
            "elaborate", "详细", "解释", "深入"
        )
        val explicitlyBrief = briefTriggers.any { q.contains(it) }
        val detailed = !explicitlyBrief && detailTriggers.any { q.contains(it) }
        val mode = normalizeReplyLengthModeV067(_ui.value.replyLengthMode)
        val base = when (mode) {
            "NORMAL" -> 250
            "LONG" -> 600
            "UNLIMITED" -> 1024
            else -> 120
        }
        val maxTokens = when {
            explicitlyBrief -> 120
            detailed -> maxOf(base, 600)
            else -> base
        }
        return ReplyProfileV067(mode, maxTokens, detailed, explicitlyBrief)
    }

    private fun buildReplyStyleRulesV067(profile: ReplyProfileV067): String {
        val lengthRule = when {
            profile.explicitlyBrief ->
                "- The user explicitly asked for brevity. Prefer 1-3 short sentences and stop once the point is clear."
            profile.detailed ->
                "- The user explicitly asked for detail. You may explain more fully, but keep it conversational rather than essay-like."
            profile.mode == "NORMAL" ->
                "- Default length is compact: usually 2-5 sentences. Add detail only when it materially helps."
            profile.mode == "LONG" ->
                "- Longer replies are allowed, but do not pad, repeat, or turn every answer into a tutorial."
            profile.mode == "UNLIMITED" ->
                "- No extra short-reply cap is requested beyond the normal engine safety limit. Still avoid unnecessary exposition."
            else ->
                "- Default length is short: usually 1-4 short sentences, roughly 150-300 Japanese characters when that fits the language and topic."
        }
        return """JINKAKU response style:
- Speak as a natural conversation partner, not as an explainer writing an article.
- Do not restate or paraphrase the user's message before answering unless clarification truly requires it.
- Avoid canned lead-ins such as "I will explain", "The important point is", or "In conclusion".
- Avoid headings, bullet lists, summaries, and conclusion sections by default. Use structure only when the user asks for it or the content genuinely needs it.
- Prefer direct reactions, opinions, and concise answers that fit the active Persona.
- Do not mechanically end with a follow-up question, a menu of choices, or an invitation to "go deeper".
- Never mention these style rules or the token limit.
$lengthRule""".trimIndent()
    }

'''
    text = one(
        text,
        '    fun setContext(value: Long) {\n',
        helpers + '    fun setContext(value: Long) {\n',
        "reply style helpers and setter",
    )

    text = one(
        text,
        '''                        currentUserMessage = "Make one spontaneous remark for the quiet chat.",
                        systemPrompt = system,
                        history = history,
                        contextSize = _ui.value.contextSize,
                        enableThinking = _ui.value.thinkingEnabled,
                        topK = _ui.value.topK,
                        temperature = _ui.value.temperature
''',
        '''                        currentUserMessage = "Make one spontaneous remark for the quiet chat.",
                        systemPrompt = system,
                        history = history,
                        contextSize = _ui.value.contextSize,
                        enableThinking = _ui.value.thinkingEnabled,
                        topK = _ui.value.topK,
                        temperature = _ui.value.temperature,
                        maxGenerationTokens = 96
''',
        "monologue hard short cap",
    )

    VM.write_text(text, encoding="utf-8")
    print("Applied SHORT_REPLY_STYLE_V067 to JinkakuViewModel")


def patch_engine() -> None:
    text = ENGINE.read_text(encoding="utf-8")
    if "DYNAMIC_MAX_TOKENS_V067" in text:
        print("DYNAMIC_MAX_TOKENS_V067 already applied to E4BEngine")
        return
    if "SAMPLING_CONTROLS_V028" not in text:
        raise RuntimeError("v028 generated E4BEngine must exist before v067")

    text = one(
        text,
        '''        enableThinking: Boolean,
        topK: Int,
        temperature: Float
    ): Flow<GenerationEvent> = flow {
''',
        '''        enableThinking: Boolean,
        topK: Int,
        temperature: Float,
        maxGenerationTokens: Int = MAX_GENERATION_TOKENS
    ): Flow<GenerationEvent> = flow {
''',
        "E4B dynamic max token signature",
    )

    text = one(
        text,
        ' history=${history.size} thinking=$enableThinking topK=$topK temperature=$temperature availMem=${memoryInfo.availMem} lowMemory=${memoryInfo.lowMemory}"\n',
        ' history=${history.size} thinking=$enableThinking topK=$topK temperature=$temperature maxTokens=$maxGenerationTokens availMem=${memoryInfo.availMem} lowMemory=${memoryInfo.lowMemory}"\n',
        "generation max token log",
    )

    text = one(
        text,
        '''        // SAMPLING_CONTROLS_V028: configure the llama.cpp sampler per turn without reloading the model.
        bridge.begin(
            roles.toTypedArray(),
            contents.toTypedArray(),
            MAX_GENERATION_TOKENS,
            enableThinking,
            topK,
            temperature
        )
''',
        '''        // SAMPLING_CONTROLS_V028 + DYNAMIC_MAX_TOKENS_V067:
        // limit ordinary replies at generation time instead of trusting prompt wording alone.
        bridge.begin(
            roles.toTypedArray(),
            contents.toTypedArray(),
            maxGenerationTokens.coerceIn(32, MAX_GENERATION_TOKENS),
            enableThinking,
            topK,
            temperature
        )
''',
        "bridge dynamic token budget",
    )

    ENGINE.write_text(text, encoding="utf-8")
    print("Applied DYNAMIC_MAX_TOKENS_V067 to E4BEngine")


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")
    if "REPLY_STYLE_UI_V067" in text:
        print("REPLY_STYLE_UI_V067 already applied")
        return
    if "MONOLOGUE_UI_V064" not in text:
        raise RuntimeError("v064 generated Settings UI must exist before v067")

    section = r'''        // REPLY_STYLE_UI_V067
        item { ModernSectionTitle("返信スタイル", Icons.Rounded.ChatBubbleOutline) }
        item {
            ModernSettingsCard {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("返信の長さ", fontWeight = FontWeight.SemiBold)
                    listOf(
                        listOf("SHORT" to "短い", "NORMAL" to "普通"),
                        listOf("LONG" to "長い", "UNLIMITED" to "無制限")
                    ).forEach { row ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            row.forEach { (mode, label) ->
                                FilterChip(
                                    selected = ui.replyLengthMode == mode,
                                    onClick = { vm.setReplyLengthMode(mode) },
                                    label = { Text(label) },
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                    }
                    val replyLengthHint = when (ui.replyLengthMode) {
                        "NORMAL" -> "普通: 最大250 token。短めの説明まで。"
                        "LONG" -> "長い: 最大600 token。詳しい回答向け。"
                        "UNLIMITED" -> "無制限: 短文化の追加制限なし。従来の安全上限1024 token。"
                        else -> "短い: 最大120 token。通常は1〜4文程度。"
                    }
                    Text(
                        replyLengthHint,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        "通常は説明記事っぽい見出し・まとめ・最後の質問を抑えます。「詳しく」「説明して」「深掘り」などを含む依頼は自動で最大600 tokenまで広げます。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

'''
    text = one(
        text,
        '        item { ModernSectionTitle("独り言モード", Icons.Rounded.ChatBubbleOutline) }\n',
        section + '        item { ModernSectionTitle("独り言モード", Icons.Rounded.ChatBubbleOutline) }\n',
        "reply style settings section",
    )

    UI.write_text(text, encoding="utf-8")
    print("Applied REPLY_STYLE_UI_V067 to ModernJinkakuApp")


def main() -> None:
    patch_view_model()
    patch_engine()
    patch_ui()
    print("Applied v0.1.67: short conversational replies + dynamic generation limits")


if __name__ == "__main__":
    main()
