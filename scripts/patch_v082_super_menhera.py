from pathlib import Path

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
MARKER = "SUPER_MENHERA_V082"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_view_model() -> None:
    text = VM.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to ViewModel")
        return

    text = one(
        text,
        "import com.ikegami99.jinkaku.model.ModelManager\n",
        "import com.ikegami99.jinkaku.model.ModelManager\n"
        "import com.ikegami99.jinkaku.game.SuperMenheraGameSession\n"
        "import com.ikegami99.jinkaku.game.SuperMenheraState\n",
        "game imports",
    )

    text = one(
        text,
        "    val error: String? = null,\n",
        "    val superMenhera: SuperMenheraState = SuperMenheraState(),\n"
        "    val error: String? = null,\n",
        "UiState game field",
    )

    text = one(
        text,
        "    private val runtimeMutex = Mutex()\n",
        "    private val runtimeMutex = Mutex()\n"
        "    private val superMenheraGame = SuperMenheraGameSession()\n",
        "game session field",
    )

    methods = r'''    // SUPER_MENHERA_V082: fully isolated, in-memory conversation game.
    fun startSuperMenhera() {
        if (_ui.value.busy || anyModelImporting()) {
            setError("処理中はスーパーメンヘラモードを開始できません")
            return
        }
        if (!models.isE2BInstalled()) {
            setError("スーパーメンヘラモードにはE2B LiteRT-LMモデルが必要です")
            return
        }
        memoryIdleJob?.cancel()
        val game = superMenheraGame.start()
        _ui.value = _ui.value.copy(
            superMenhera = game,
            runtimeStatus = "SUPER MENHERA",
            generatingText = "",
            thinking = false,
            error = null,
            notice = null
        )
        logger.i("MENHERA", "Game started type=${game.archetype}; storage=RAM_ONLY maxTurns=${game.maxTurns}")
    }

    fun stopSuperMenhera() {
        if (!_ui.value.superMenhera.active) return
        generationJob?.cancel()
        generationJob = null
        val cleared = superMenheraGame.stop()
        _ui.value = _ui.value.copy(
            superMenhera = cleared,
            busy = false,
            thinking = false,
            generatingText = "",
            runtimeStatus = "IDLE",
            notice = "スーパーメンヘラのセッションMemoryを破棄しました"
        )
        logger.i("MENHERA", "Game stopped; temporary session discarded")
    }

    fun restartSuperMenhera() {
        if (_ui.value.busy || anyModelImporting()) return
        val game = superMenheraGame.start()
        _ui.value = _ui.value.copy(
            superMenhera = game,
            runtimeStatus = "SUPER MENHERA",
            generatingText = "",
            thinking = false,
            error = null,
            notice = null
        )
        logger.i("MENHERA", "Game restarted type=${game.archetype}")
    }

    fun stopSuperMenheraGeneration() {
        if (!_ui.value.superMenhera.active) return
        generationJob?.cancel()
        generationJob = null
        val game = superMenheraGame.setGenerating(false)
        _ui.value = _ui.value.copy(
            superMenhera = game,
            busy = false,
            thinking = false,
            generatingText = "",
            runtimeStatus = "SUPER MENHERA"
        )
        logger.w("MENHERA", "Generation cancelled by player")
    }

    fun sendSuperMenhera(text: String) {
        val clean = text.trim()
        val currentGame = _ui.value.superMenhera
        if (clean.isEmpty() || _ui.value.busy || !currentGame.active || currentGame.finished) return
        if (anyModelImporting()) {
            setError("モデル処理中です。完了後に送信してください")
            return
        }
        if (!models.isE2BInstalled()) {
            setError("E2B LiteRT-LMモデルが必要です")
            return
        }

        memoryIdleJob?.cancel()
        val afterUser = superMenheraGame.userTurn(clean)
        _ui.value = _ui.value.copy(superMenhera = afterUser, error = null, notice = null)

        generationJob = viewModelScope.launch {
            runtimeMutex.withLock {
                try {
                    val generating = superMenheraGame.setGenerating(true)
                    _ui.value = _ui.value.copy(
                        superMenhera = generating,
                        busy = true,
                        thinking = true,
                        generatingText = "",
                        runtimeStatus = "MENHERA THINKING",
                        error = null
                    )

                    // Only the temporary game transcript is supplied. Normal DB messages,
                    // Persona, long-term Memory, pending-memory queue and web search are bypassed.
                    val history = superMenheraGame.inferenceHistory()
                    val system = superMenheraGame.systemPrompt()
                    var finalText = ""
                    e2bChat.generate(
                        model = models.e2bFile,
                        currentUserMessage = clean,
                        systemPrompt = system,
                        history = history,
                        contextSize = _ui.value.contextSize.coerceAtMost(4096L),
                        maxGenerationTokens = 320,
                        topK = _ui.value.topK,
                        topP = _ui.value.topP.toDouble(),
                        temperature = _ui.value.temperature.coerceAtLeast(0.75f).toDouble()
                    ).collect { event ->
                        when (event) {
                            GenerationEvent.Thinking -> _ui.value = _ui.value.copy(
                                thinking = true,
                                runtimeStatus = "MENHERA THINKING"
                            )
                            is GenerationEvent.Text -> {
                                finalText += event.value
                                _ui.value = _ui.value.copy(
                                    thinking = false,
                                    generatingText = finalText,
                                    runtimeStatus = "MENHERA TALKING"
                                )
                            }
                            is GenerationEvent.Completed -> finalText = event.finalText
                        }
                    }

                    val afterAssistant = superMenheraGame.assistantTurn(finalText)
                    _ui.value = _ui.value.copy(
                        superMenhera = afterAssistant,
                        busy = false,
                        thinking = false,
                        generatingText = "",
                        runtimeStatus = if (afterAssistant.finished) "MENHERA RESULT" else "SUPER MENHERA"
                    )
                    logger.i(
                        "MENHERA",
                        "Turn=${afterAssistant.turn}/${afterAssistant.maxTurns} result=${afterAssistant.result} " +
                            "instability=${afterAssistant.instability} trust=${afterAssistant.trust} " +
                            "dependence=${afterAssistant.dependence} jealousy=${afterAssistant.jealousy}"
                    )
                } catch (t: Throwable) {
                    val stopped = superMenheraGame.setGenerating(false)
                    if (t is CancellationException) {
                        _ui.value = _ui.value.copy(
                            superMenhera = stopped,
                            busy = false,
                            thinking = false,
                            generatingText = "",
                            runtimeStatus = "SUPER MENHERA"
                        )
                        logger.w("MENHERA", "Generation cancelled")
                    } else {
                        logger.e("MENHERA", "Generation failed", t)
                        _ui.value = _ui.value.copy(
                            superMenhera = stopped,
                            busy = false,
                            thinking = false,
                            generatingText = "",
                            runtimeStatus = "ERROR",
                            error = t.message ?: "スーパーメンヘラ生成に失敗しました"
                        )
                    }
                }
            }
        }
    }

'''
    text = one(
        text,
        "    fun stopGeneration() {\n",
        methods + "    fun stopGeneration() {\n",
        "game methods insertion",
    )

    text = one(
        text,
        "    override fun onCleared() {\n",
        "    override fun onCleared() {\n        superMenheraGame.stop()\n",
        "discard game on ViewModel clear",
    )

    text = text.replace(
        "class JinkakuViewModel(app: Application) : AndroidViewModel(app) {",
        "class JinkakuViewModel(app: Application) : AndroidViewModel(app) {\n    // SUPER_MENHERA_V082: game state never enters normal storage.",
        1,
    )

    VM.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to ViewModel")


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to UI")
        return

    text = one(
        text,
        "import com.ikegami99.jinkaku.JinkakuViewModel\n",
        "import com.ikegami99.jinkaku.JinkakuViewModel\n"
        "import com.ikegami99.jinkaku.game.SuperMenheraResult\n",
        "game UI import",
    )

    text = one(
        text,
        "private enum class ModernScreen { CHAT, MEMORY, SETTINGS }",
        "private enum class ModernScreen { CHAT, MEMORY, SETTINGS, MENHERA }",
        "ModernScreen game route",
    )

    sync_block = '''
    LaunchedEffect(ui.superMenhera.active) {
        if (ui.superMenhera.active) {
            screen = ModernScreen.MENHERA
        } else if (screen == ModernScreen.MENHERA) {
            screen = ModernScreen.SETTINGS
        }
    }

'''
    text = one(
        text,
        "    MaterialTheme(\n",
        sync_block + "    MaterialTheme(\n",
        "game route sync",
    )

    text = one(
        text,
        "                    ModernScreen.MEMORY -> ModernMemoryScreen(vm, Modifier.padding(padding))\n",
        "                    ModernScreen.MEMORY -> ModernMemoryScreen(vm, Modifier.padding(padding))\n"
        "                    ModernScreen.MENHERA -> SuperMenheraScreen(vm, Modifier.padding(padding))\n",
        "game screen route",
    )

    # Put the game switch immediately below the v081 quick-start guide, above collapsed categories.
    settings_card = r'''
        item {
            ModernSettingsCard {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Surface(
                        shape = RoundedCornerShape(14.dp),
                        color = MaterialTheme.colorScheme.errorContainer,
                        modifier = Modifier.size(42.dp)
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(Icons.Rounded.Psychology, null, tint = MaterialTheme.colorScheme.onErrorContainer)
                        }
                    }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text("スーパーメンヘラモード", fontWeight = FontWeight.Bold)
                        Text(
                            "100チャット以内になだめる独立ゲーム。Persona・Memory・履歴は通常チャットと完全分離し、終了時に破棄します。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Switch(
                        checked = ui.superMenhera.active,
                        onCheckedChange = { enabled ->
                            if (enabled) vm.startSuperMenhera() else vm.stopSuperMenhera()
                        },
                        enabled = !ui.busy
                    )
                }
            }
        }

'''
    text = one(
        text,
        "        item { JinkakuUsageGuide() }\n\n",
        "        item { JinkakuUsageGuide() }\n\n" + settings_card,
        "Settings game switch",
    )

    game_screen = r'''
@Composable
private fun SuperMenheraScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier) {
    val ui by vm.ui.collectAsStateWithLifecycle()
    val game = ui.superMenhera
    var input by remember { mutableStateOf("") }
    val focusManager = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    val listState = rememberLazyListState()

    fun submit() {
        val value = input.trim()
        if (value.isBlank() || game.finished) return
        input = ""
        focusManager.clearFocus(force = true)
        keyboard?.hide()
        vm.sendSuperMenhera(value)
    }

    LaunchedEffect(game.messages.size, game.generating) {
        val total = game.messages.size + if (game.generating) 1 else 0
        if (total > 0) listState.animateScrollToItem(total - 1)
    }

    Column(modifier.fillMaxSize()) {
        Card(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 10.dp),
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.72f),
                contentColor = MaterialTheme.colorScheme.onErrorContainer
            ),
            shape = RoundedCornerShape(24.dp)
        ) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("SUPER MENHERA", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleLarge)
                        Text(
                            "${game.archetype}  ·  ${game.statusLabel}",
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                    AssistChip(onClick = {}, label = { Text("残り ${game.remainingTurns}") })
                }
                LinearProgressIndicator(
                    progress = { (game.turn.toFloat() / game.maxTurns.coerceAtLeast(1)).coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(999.dp))
                )
                Text(
                    "この会話のPersonaとMemoryはゲーム専用・RAM内のみ。通常チャットには一切保存されません。",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onErrorContainer.copy(alpha = 0.78f)
                )
            }
        }

        if (game.result != SuperMenheraResult.PLAYING) {
            Card(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 2.dp),
                colors = CardDefaults.cardColors(
                    containerColor = if (game.result == SuperMenheraResult.CLEARED)
                        MaterialTheme.colorScheme.secondaryContainer
                    else MaterialTheme.colorScheme.errorContainer
                )
            ) {
                Column(
                    Modifier.fillMaxWidth().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        if (game.result == SuperMenheraResult.CLEARED) "CLEAR" else "FAILED",
                        style = MaterialTheme.typography.headlineMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        if (game.result == SuperMenheraResult.CLEARED)
                            "${game.turn} / ${game.maxTurns}チャットでなだめることに成功"
                        else
                            "100チャット到達。今回はなだめきれませんでした。"
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = vm::restartSuperMenhera, enabled = !ui.busy) { Text("もう一度") }
                        OutlinedButton(onClick = vm::stopSuperMenhera, enabled = !ui.busy) { Text("終了") }
                    }
                }
            }
        }

        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 10.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(game.messages, key = { it.id }) { message ->
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = if (message.role == ROLE_USER) Arrangement.End else Arrangement.Start
                ) {
                    Surface(
                        shape = if (message.role == ROLE_USER)
                            RoundedCornerShape(24.dp, 24.dp, 6.dp, 24.dp)
                        else RoundedCornerShape(24.dp, 24.dp, 24.dp, 6.dp),
                        color = if (message.role == ROLE_USER)
                            MaterialTheme.colorScheme.primaryContainer
                        else MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.55f),
                        modifier = Modifier.fillMaxWidth(0.88f)
                    ) {
                        Text(
                            message.content,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 13.dp),
                            style = MaterialTheme.typography.bodyLarge
                        )
                    }
                }
            }

            if (game.generating) {
                item {
                    Surface(
                        shape = RoundedCornerShape(24.dp, 24.dp, 24.dp, 6.dp),
                        color = MaterialTheme.colorScheme.errorContainer.copy(alpha = 0.55f)
                    ) {
                        Row(
                            Modifier.padding(horizontal = 16.dp, vertical = 13.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            StatusDot(true)
                            Text(
                                when {
                                    game.turn >= 90 -> "……入力してる"
                                    game.turn >= 70 -> "ねえ…"
                                    else -> modernTypingLabel(0)
                                },
                                color = MaterialTheme.colorScheme.onErrorContainer
                            )
                        }
                    }
                }
            }
        }

        Surface(color = MaterialTheme.colorScheme.background, tonalElevation = 2.dp) {
            Column(Modifier.fillMaxWidth().navigationBarsPadding()) {
                Row(
                    Modifier.fillMaxWidth().imePadding().padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.Bottom,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    OutlinedTextField(
                        value = input,
                        onValueChange = { input = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text(if (game.finished) "ゲーム終了" else "なだめる…") },
                        shape = RoundedCornerShape(24.dp),
                        enabled = !game.finished && !ui.busy,
                        maxLines = 6
                    )
                    FilledIconButton(
                        onClick = {
                            if (ui.busy) {
                                focusManager.clearFocus(force = true)
                                keyboard?.hide()
                                vm.stopSuperMenheraGeneration()
                            } else submit()
                        },
                        enabled = ui.busy || (!game.finished && input.isNotBlank()),
                        modifier = Modifier.size(54.dp)
                    ) {
                        Icon(if (ui.busy) Icons.Rounded.StopCircle else Icons.Rounded.Send, null)
                    }
                }
                TextButton(
                    onClick = vm::stopSuperMenhera,
                    enabled = !ui.busy,
                    modifier = Modifier.align(Alignment.CenterHorizontally)
                ) {
                    Text("スーパーメンヘラモードを終了")
                }
            }
        }
    }
}

'''
    text = one(
        text,
        "@Composable\nprivate fun ModernMemoryScreen(",
        game_screen + "@Composable\nprivate fun ModernMemoryScreen(",
        "game screen composable",
    )

    # Tag the UI for idempotence without relying on a fragile generated block.
    text = text.replace(
        "private fun SuperMenheraScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier) {",
        "private fun SuperMenheraScreen(vm: JinkakuViewModel, modifier: Modifier = Modifier) { // SUPER_MENHERA_V082",
        1,
    )

    UI.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to UI")


def main() -> None:
    patch_view_model()
    patch_ui()
    print(f"Applied {MARKER}: isolated 100-turn Super Menhera game mode")


if __name__ == "__main__":
    main()
