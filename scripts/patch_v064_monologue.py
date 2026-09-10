from pathlib import Path

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")


def one(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def patch_view_model() -> None:
    text = VM.read_text(encoding="utf-8")
    if "MONOLOGUE_MODE_V064" in text:
        print("MONOLOGUE_MODE_V064 already applied to JinkakuViewModel")
        return
    if "WEB_PREFILL_BUDGET_V063" not in text:
        raise RuntimeError("v063 must run before v064")

    method = r'''
    // MONOLOGUE_MODE_V064: generated locally from Persona + recent chat.
    // No user row is inserted and queueMemory() is never called, so this stays out of Memory extraction.
    fun generateMonologue() {
        if (_ui.value.busy || anyModelImporting() || !models.isE4BInstalled()) return
        val chatId = currentChatId
        if (db.recentMessages(chatId, 1).isEmpty()) return

        generationJob = viewModelScope.launch {
            runtimeMutex.withLock {
                prefs.edit().putBoolean(KEY_E4B_ACTIVE, true).commit()
                try {
                    _ui.value = _ui.value.copy(
                        busy = true,
                        thinking = true,
                        generatingText = "",
                        runtimeStatus = "独り言中",
                        error = null
                    )

                    val recent = db.recentMessages(chatId, 8)
                    val memoryQuery = recent
                        .filter { it.role == ROLE_USER }
                        .takeLast(4)
                        .joinToString(" ") { it.content }
                        .takeLast(900)
                        .ifBlank { "recent conversation" }
                    val relevant = withContext(Dispatchers.IO) { memory.retrieve(memoryQuery, 6) }
                    val history = normalizeHistory(db.recentMessages(chatId, 18))
                    val monologueRules =
                        "\n\nSpontaneous monologue mode:\n" +
                        "- This is an internal scheduler event, not a new message from the human user.\n" +
                        "- The human has been quiet for a while. Say one brief, natural remark that fits your Persona and may lightly reflect on the recent conversation.\n" +
                        "- Output only 1 or 2 short sentences.\n" +
                        "- Do not mention timers, inactivity detection, schedulers, hidden prompts, or this instruction.\n" +
                        "- Do not demand a reply and do not end with a direct question.\n" +
                        "- Do not invent new facts about the user.\n" +
                        "- This spontaneous remark is chat-only and must not be treated as a user memory."
                    val system = buildSystemPrompt(relevant, _ui.value.thinkingEnabled) + monologueRules

                    var finalText = ""
                    e4b.generate(
                        model = models.getE4BFile(),
                        currentUserMessage = "Make one spontaneous remark for the quiet chat.",
                        systemPrompt = system,
                        history = history,
                        contextSize = _ui.value.contextSize,
                        enableThinking = _ui.value.thinkingEnabled,
                        topK = _ui.value.topK,
                        temperature = _ui.value.temperature
                    ).collect { event ->
                        when (event) {
                            GenerationEvent.Thinking -> _ui.value = _ui.value.copy(
                                thinking = true,
                                runtimeStatus = "独り言中"
                            )
                            is GenerationEvent.Text -> {
                                finalText += event.value
                                _ui.value = _ui.value.copy(
                                    thinking = false,
                                    generatingText = finalText,
                                    runtimeStatus = "独り言中"
                                )
                            }
                            is GenerationEvent.Completed -> finalText = event.finalText
                        }
                    }

                    val clean = finalText.trim()
                    if (clean.isNotBlank() && currentChatId == chatId) {
                        db.insertMessage(chatId, ROLE_ASSISTANT, clean)
                        logger.i("MONOLOGUE", "generated chars=${clean.length}; memoryQueue=false")
                    }
                    _ui.value = _ui.value.copy(
                        busy = false,
                        thinking = false,
                        generatingText = "",
                        runtimeStatus = "E4B READY"
                    )
                    refresh()
                } catch (t: Throwable) {
                    if (t is CancellationException) {
                        logger.w("MONOLOGUE", "Generation cancelled")
                        _ui.value = _ui.value.copy(
                            busy = false,
                            thinking = false,
                            generatingText = "",
                            runtimeStatus = "IDLE"
                        )
                    } else {
                        logger.e("MONOLOGUE", "Generation failed", t)
                        _ui.value = _ui.value.copy(
                            busy = false,
                            thinking = false,
                            generatingText = "",
                            runtimeStatus = "ERROR",
                            error = "独り言生成: ${t.message ?: "Generation failed"}"
                        )
                    }
                } finally {
                    prefs.edit().putBoolean(KEY_E4B_ACTIVE, false).commit()
                }
            }
        }
    }

'''
    text = one(
        text,
        "    private fun normalizeHistory(input: List<ChatMessage>): List<ChatMessage> {\n",
        method + "    private fun normalizeHistory(input: List<ChatMessage>): List<ChatMessage> {\n",
        "monologue generation method",
    )

    VM.write_text(text, encoding="utf-8")
    print("Applied MONOLOGUE_MODE_V064 to JinkakuViewModel")


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")
    if "MONOLOGUE_UI_V064" in text:
        print("MONOLOGUE_UI_V064 already applied")
        return
    if "TAVILY_WEB_UI_V062" not in text:
        raise RuntimeError("v062 UI patch must run before v064")

    text = one(
        text,
        "import kotlinx.coroutines.launch\n",
        "import kotlinx.coroutines.delay\nimport kotlinx.coroutines.launch\n",
        "delay import",
    )

    text = one(
        text,
        "import java.util.Locale\n",
        "import java.util.Locale\nimport kotlin.random.Random\n",
        "Random import",
    )

    text = one(
        text,
        '    var forceWebSearch by remember { mutableStateOf(false) }\n',
        '    var forceWebSearch by remember { mutableStateOf(false) }\n'
        '    val monologueContext = LocalContext.current\n'
        '    val monologuePrefs = remember(monologueContext) { monologueContext.getSharedPreferences("settings", android.content.Context.MODE_PRIVATE) }\n'
        '    val monologueMode = remember { monologuePrefs.getString("monologue_mode", "NORMAL") ?: "NORMAL" }\n'
        '    var monologueActivity by remember { mutableStateOf(0) }\n'
        '    var monologueFollowUp by remember { mutableStateOf(false) }\n',
        "chat monologue state",
    )

    text = one(
        text,
        '    val showTypingBubble = ui.busy && telemetry.phase in setOf("PREFILL", "THINKING", "DECODE")\n',
        '    val showTypingBubble = ui.busy && telemetry.phase in setOf("PREFILL", "THINKING", "DECODE")\n'
        '\n'
        '    fun noteMonologueActivity() {\n'
        '        monologueActivity += 1\n'
        '        monologueFollowUp = false\n'
        '    }\n'
        '\n'
        '    // MONOLOGUE_UI_V064: this effect only exists while the chat screen is open.\n'
        '    LaunchedEffect(monologueMode, monologueActivity, monologueFollowUp, ui.busy, ui.currentChatId, ui.messages.isEmpty()) {\n'
        '        if (monologueMode == "OFF" || ui.busy || ui.messages.isEmpty()) return@LaunchedEffect\n'
        '        val waitMs = if (monologueFollowUp) {\n'
        '            when (monologueMode) {\n'
        '                "QUIET" -> Random.nextLong(12 * 60_000L, 20 * 60_000L + 1)\n'
        '                "CHATTY" -> Random.nextLong(3 * 60_000L, 6 * 60_000L + 1)\n'
        '                else -> Random.nextLong(5 * 60_000L, 10 * 60_000L + 1)\n'
        '            }\n'
        '        } else {\n'
        '            when (monologueMode) {\n'
        '                "QUIET" -> Random.nextLong(8 * 60_000L, 12 * 60_000L + 1)\n'
        '                "CHATTY" -> Random.nextLong(35_000L, 55_001L)\n'
        '                else -> Random.nextLong(100_000L, 140_001L)\n'
        '            }\n'
        '        }\n'
        '        delay(waitMs)\n'
        '        val baseChance = when (monologueMode) {\n'
        '            "QUIET" -> 0.35\n'
        '            "CHATTY" -> 0.65\n'
        '            else -> 0.45\n'
        '        }\n'
        '        val chance = if (monologueFollowUp) baseChance * 0.65 else baseChance\n'
        '        monologueFollowUp = true\n'
        '        if (Random.nextDouble() <= chance) vm.generateMonologue()\n'
        '    }\n',
        "idle monologue effect",
    )

    text = one(
        text,
        '        val value = input.trim()\n'
        '        if (value.isBlank()) return\n',
        '        val value = input.trim()\n'
        '        if (value.isBlank()) return\n'
        '        noteMonologueActivity()\n',
        "send resets monologue timer",
    )

    text = one(
        text,
        "            modifier = Modifier.weight(1f).fillMaxWidth(),\n",
        "            modifier = Modifier.weight(1f).fillMaxWidth().pointerInput(Unit) {\n"
        "                detectDragGestures(onDragStart = { noteMonologueActivity() }) { _, _ -> }\n"
        "            },\n",
        "user scroll resets monologue timer",
    )

    text = one(
        text,
        "                    value = input,\n"
        "                    onValueChange = { input = it },\n",
        "                    value = input,\n"
        "                    onValueChange = { value -> input = value; noteMonologueActivity() },\n",
        "typing resets monologue timer",
    )

    text = one(
        text,
        '    var tavilyKeyDraft by remember { mutableStateOf(vm.tavilyApiKey()) }\n',
        '    var tavilyKeyDraft by remember { mutableStateOf(vm.tavilyApiKey()) }\n'
        '    val monologueSettingsContext = LocalContext.current\n'
        '    val monologueSettingsPrefs = remember(monologueSettingsContext) { monologueSettingsContext.getSharedPreferences("settings", android.content.Context.MODE_PRIVATE) }\n'
        '    var monologueMode by remember { mutableStateOf(monologueSettingsPrefs.getString("monologue_mode", "NORMAL") ?: "NORMAL") }\n',
        "settings monologue state",
    )

    settings = r'''        item { ModernSectionTitle("独り言モード", Icons.Rounded.ChatBubbleOutline) }
        item {
            ModernSettingsCard {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("放置中のJINKAKU", fontWeight = FontWeight.SemiBold)
                    Text(
                        "チャット画面を開いたまま返事をしないと、Personaと直近の会話を使って短い独り言を生成します。独り言はMemory抽出の対象外です。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    listOf(
                        listOf("OFF" to "OFF", "QUIET" to "控えめ"),
                        listOf("NORMAL" to "普通", "CHATTY" to "よく喋る")
                    ).forEach { row ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            row.forEach { (mode, label) ->
                                FilterChip(
                                    selected = monologueMode == mode,
                                    onClick = {
                                        monologueMode = mode
                                        monologueSettingsPrefs.edit().putString("monologue_mode", mode).apply()
                                    },
                                    label = { Text(label) },
                                    modifier = Modifier.weight(1f)
                                )
                            }
                        }
                    }
                    val monologueHint = when (monologueMode) {
                        "QUIET" -> "最初の候補: 約8〜12分後 / 発言率 約35%"
                        "NORMAL" -> "最初の候補: 約100〜140秒後 / 発言率 約45%"
                        "CHATTY" -> "最初の候補: 約35〜55秒後 / 発言率 約65%"
                        else -> "自動発言しません"
                    }
                    Text(
                        monologueHint + if (monologueMode == "OFF") "" else "。発言後や見送り後は次の候補まで少し長めに間隔を空けます。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }

'''
    text = one(
        text,
        '        item { ModernSectionTitle("Web検索", Icons.Rounded.Public) }\n',
        settings + '        item { ModernSectionTitle("Web検索", Icons.Rounded.Public) }\n',
        "monologue settings section",
    )

    UI.write_text(text, encoding="utf-8")
    print("Applied MONOLOGUE_UI_V064 to ModernJinkakuApp")


def main() -> None:
    patch_view_model()
    patch_ui()
    print("Applied v0.1.64 monologue mode: randomized idle speech, Persona-aware, Memory-excluded")


if __name__ == "__main__":
    main()
