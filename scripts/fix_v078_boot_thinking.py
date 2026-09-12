from pathlib import Path

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
UI = Path("app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt")
ENGINE = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E2BChatEngine.kt")
MARKER = "E2B_THINKING_V078"


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

    # Never let the optional EmbeddingGemma JNI path make the whole app fail at startup.
    # The native library is restored in the APK, but Hashing-256 remains a last-resort fallback.
    text = one(
        text,
        "    private var memory = MemoryEngine(db, logger)\n",
        "    private var memory = MemoryEngine(db, logger)\n"
        "    private var embeddingNativeFailed = false // E2B_THINKING_V078\n",
        "embedding native failure guard",
    )

    old_sync = '''    private fun syncEmbeddingEngine() {
        if (models.isEmbeddingInstalled()) {
            if (memory.embeddingName != EMBEDDING_ENGINE_NAME) {
                memory.useEmbedding(EmbeddingGemmaEngine(models.embeddingFile, logger))
            }
        } else if (memory.embeddingName != "Hashing-256") {
            memory.useHashingEmbedding()
        }
    }
'''
    new_sync = '''    private fun syncEmbeddingEngine() {
        if (!models.isEmbeddingInstalled()) {
            if (memory.embeddingName != "Hashing-256") memory.useHashingEmbedding()
            return
        }
        if (memory.embeddingName == EMBEDDING_ENGINE_NAME || embeddingNativeFailed) return

        runCatching { EmbeddingGemmaEngine(models.embeddingFile, logger) }
            .onSuccess { memory.useEmbedding(it) }
            .onFailure { error ->
                embeddingNativeFailed = true
                memory.useHashingEmbedding()
                logger.e("MEMORY", "EmbeddingGemma JNI unavailable; continuing with Hashing-256", error)
            }
    }
'''
    text = one(text, old_sync, new_sync, "startup-safe embedding engine")

    # v077 forced the system prompt to non-thinking mode. Restore the user's toggle.
    text = one(
        text,
        "buildSystemPrompt(relevant, false)",
        "buildSystemPrompt(relevant, _ui.value.thinkingEnabled)",
        "system prompt thinking toggle",
    )

    text = one(
        text,
        '''                        maxGenerationTokens = replyProfile.maxTokens,
                        topK = _ui.value.topK,
''',
        '''                        maxGenerationTokens = replyProfile.maxTokens,
                        enableThinking = _ui.value.thinkingEnabled,
                        topK = _ui.value.topK,
''',
        "main E2B thinking argument",
    )

    # Keep idle monologue lightweight even when interactive Thinking is enabled.
    text = one(
        text,
        '''                        maxGenerationTokens = 96,
                        topK = _ui.value.topK,
''',
        '''                        maxGenerationTokens = 96,
                        enableThinking = false,
                        topK = _ui.value.topK,
''',
        "monologue E2B thinking argument",
    )

    VM.write_text(text, encoding="utf-8")


def patch_engine() -> None:
    text = ENGINE.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to E2BChatEngine")
        return

    text = one(
        text,
        '''        maxGenerationTokens: Int,
        topK: Int,
''',
        '''        maxGenerationTokens: Int,
        enableThinking: Boolean,
        topK: Int,
''',
        "E2B generate thinking parameter",
    )

    text = one(
        text,
        '''        val outputLimit = maxGenerationTokens.coerceIn(32, MAX_OUTPUT_TOKENS)
        val activeEngine = ensureEngine(model, maxContext)
''',
        '''        // E2B_THINKING_V078: LiteRT-LM counts reasoning + final answer against
        // maxOutputToken. Reserve a separate 512-token reasoning budget while leaving
        // roughly one quarter of the context for the prompt/history.
        val requestedAnswerLimit = maxGenerationTokens.coerceIn(32, MAX_OUTPUT_TOKENS)
        val generationWindow = (maxContext * 3 / 4).coerceAtLeast(128)
        val thinkingBudget = if (enableThinking) {
            minOf(THINKING_TOKEN_BUDGET, (generationWindow - 32).coerceAtLeast(0))
        } else {
            0
        }
        val answerLimit = minOf(
            requestedAnswerLimit,
            (generationWindow - thinkingBudget).coerceAtLeast(32)
        )
        val totalOutputLimit = (answerLimit + thinkingBudget)
            .coerceIn(32, MAX_TOTAL_OUTPUT_TOKENS)
        val thinkingActive = enableThinking && thinkingBudget > 0
        val activeEngine = ensureEngine(model, maxContext)
''',
        "E2B reasoning budget",
    )

    text = one(
        text,
        '''            "Generation start runtime=LiteRT-LM backend=GPU mtp=ON fallback=NONE thinking=OFF " +
                "ctx=$maxContext history=${recentHistory.size} outputLimit=$outputLimit " +
''',
        '''            "Generation start runtime=LiteRT-LM backend=GPU mtp=ON fallback=NONE " +
                "thinking=$thinkingActive thoughtBudget=$thinkingBudget answerLimit=$answerLimit " +
                "ctx=$maxContext history=${recentHistory.size} totalOutputLimit=$totalOutputLimit " +
''',
        "E2B thinking diagnostics",
    )

    text = one(
        text,
        "        emit(GenerationEvent.Thinking)\n",
        "        if (thinkingActive) emit(GenerationEvent.Thinking)\n",
        "conditional thinking event",
    )

    output_count = text.count("maxOutputToken = outputLimit")
    if output_count != 2:
        raise RuntimeError(f"E2B maxOutputToken: expected 2 anchors, found {output_count}")
    text = text.replace("maxOutputToken = outputLimit", "maxOutputToken = totalOutputLimit")

    thinking_block = '''                    thinkingConfig = ThinkingConfig(
                        enableThinking = false,
                        thinkingTokenBudget = 0
                    )'''
    replacement = '''                    thinkingConfig = ThinkingConfig(
                        enableThinking = thinkingActive,
                        thinkingTokenBudget = thinkingBudget
                    )'''
    thinking_count = text.count(thinking_block)
    if thinking_count != 2:
        raise RuntimeError(f"E2B ThinkingConfig: expected 2 anchors, found {thinking_count}")
    text = text.replace(thinking_block, replacement)

    text = one(
        text,
        '''        private const val MAX_OUTPUT_TOKENS = 1024
        private const val MAX_HISTORY_MESSAGES = 6
''',
        '''        private const val MAX_OUTPUT_TOKENS = 1024
        private const val THINKING_TOKEN_BUDGET = 512
        private const val MAX_TOTAL_OUTPUT_TOKENS = MAX_OUTPUT_TOKENS + THINKING_TOKEN_BUDGET
        private const val MAX_HISTORY_MESSAGES = 6
''',
        "E2B thinking constants",
    )

    ENGINE.write_text(text, encoding="utf-8")


def patch_ui() -> None:
    text = UI.read_text(encoding="utf-8")
    if "Thinking (E2BではOFF固定)" not in text:
        raise RuntimeError("v077 finalized Thinking UI was not found")

    text = one(
        text,
        'Text("Thinking (E2BではOFF固定)", fontWeight = FontWeight.SemiBold)',
        'Text("Thinking", fontWeight = FontWeight.SemiBold)',
        "Thinking title",
    )
    text = one(
        text,
        '"LiteRT-LMはThinkingを使わず直接回答"',
        'if (ui.thinkingEnabled) "LiteRT-LMのThinkingを使ってから回答" else "Thinkingを省略して直接回答"',
        "Thinking description",
    )
    text = one(
        text,
        '''checked = false,
                            onCheckedChange = null,
                            enabled = false''',
        '''checked = ui.thinkingEnabled,
                            onCheckedChange = vm::setThinkingEnabled,
                            enabled = !ui.busy && !ui.e2bImporting''',
        "Thinking switch",
    )
    text = one(
        text,
        '"GPU + MTPの高速経路を優先するためOFF固定です。"',
        'if (ui.thinkingEnabled) "Thinking内容は非表示です。最大512 tokenを推論に使います。" else "OFFでは直接回答します。"',
        "Thinking status hint",
    )
    text = one(
        text,
        'E2BではThinking OFF固定。返信の長さは回答本文の最大token数です。',
        'Thinkingは別枠で最大512 token。返信の長さは回答本文側の目安です。Contextが小さい場合は回答枠を自動調整します。',
        "Thinking budget hint",
    )

    UI.write_text(text, encoding="utf-8")


def main() -> None:
    patch_view_model()
    patch_engine()
    patch_ui()
    print("Applied E2B_THINKING_V078: startup-safe embedding JNI + LiteRT-LM Thinking toggle")


if __name__ == "__main__":
    main()
