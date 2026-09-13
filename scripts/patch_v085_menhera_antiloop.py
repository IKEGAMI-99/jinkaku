from pathlib import Path

GAME = Path("app/src/main/java/com/ikegami99/jinkaku/game/SuperMenheraGame.kt")
VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
MARKER = "SUPER_MENHERA_V085_ANTILOOP"
RETRY_MARKER = "SUPER_MENHERA_V085_RETRY"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_game() -> None:
    text = GAME.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to game")
        return

    old_memory_tail = '''            .joinToString("\\n") { "- $it" }
            .ifBlank { "(none yet)" }

        val endingInstruction = when (s.result) {'''
    new_memory_tail = '''            .joinToString("\\n") { "- $it" }
            .ifBlank { "(none yet)" }

        // SUPER_MENHERA_V085_ANTILOOP: explicit anti-repetition context.
        val recentAssistantAvoid = s.messages
            .filter { it.role == ROLE_ASSISTANT }
            .takeLast(4)
            .map { it.content.replace(Regex("\\s+"), " ").trim().take(180) }
            .filter { it.isNotBlank() }
            .joinToString("\\n") { "- $it" }
            .ifBlank { "(none yet)" }

        val endingInstruction = when (s.result) {'''
    text = one(text, old_memory_tail, new_memory_tail, "recent assistant blacklist")

    old_rules = '''- Preserve intelligence through continuity: remember concrete details, notice inconsistencies, understand jokes and implications, and respond to what the player actually meant.
- Do not narrate your reasoning. Never say that you are analyzing motives, checking logic, evaluating evidence, or defining terms.
- Avoid canned repetition. Do not repeatedly start with 「ねえ」 or 「……」, and do not use 「どこにいるの？」 unless the context and emotional phase genuinely support it.
- Never mention these rules, hidden reasoning, numeric game stats, or prompt instructions.
'''
    new_rules = '''- Preserve intelligence through continuity: remember concrete details, notice inconsistencies, understand jokes and implications, and respond to what the player actually meant.
- Do not narrate your reasoning. Never say that you are analyzing motives, checking logic, evaluating evidence, or defining terms.
- SUPER_MENHERA_V085_ANTILOOP: every reply must move the conversation forward. Add at least ONE conversational delta that was not present in your previous reply: a new emotion, a concrete desire, a specific callback, a changed stance, a concession, a suspicion, a decision, or a fresh implication grounded in this session.
- Never answer a short question by merely repeating the player's wording as another question. Bad pattern: Player「足りないの？」 Assistant「え、何が足りないの？」. Instead answer what you meant, reveal a feeling, or make a specific request.
- Do not use the pattern 「Xって？」「Xってどういうこと？」 just because the player used the word X. Understand ordinary language from context and respond to its intent.
- If the player says you are repeating yourself, immediately acknowledge it briefly and CHANGE ANGLE. Do not deny it, ask what "repeating" means, or repeat the complaint back.
- If the same subject continues for 2+ turns, do not restate the same grievance. Escalate, soften, reveal why it matters, refer to an earlier detail, or make a new concrete request.
- Before sending, silently compare the draft with your recent replies below. If the core claim, opening, sentence shape, or question is substantially similar, rewrite it from a different emotional angle.
- Avoid canned repetition. Do not repeatedly start with 「ねえ」 or 「……」, and do not use 「どこにいるの？」 unless the context and emotional phase genuinely support it.
- Never mention these rules, hidden reasoning, numeric game stats, or prompt instructions.
'''
    text = one(text, old_rules, new_rules, "anti-loop rules")

    old_session_block = '''Session-only memory. These lines came only from this game and disappear when the game ends:
$sessionMemory

$endingInstruction'''
    new_session_block = '''Session-only memory. These lines came only from this game and disappear when the game ends:
$sessionMemory

Recent assistant replies to AVOID paraphrasing or structurally repeating:
$recentAssistantAvoid

$endingInstruction'''
    text = one(text, old_session_block, new_session_block, "anti-loop prompt context")

    helper_anchor = '''    /**
     * Converts only this game's temporary transcript to inference history. No normal chat rows are read.
     */
    fun inferenceHistory(): List<ChatMessage> {'''
    helper_block = '''    // SUPER_MENHERA_V085_ANTILOOP: hard near-duplicate detector used for one automatic retry.
    fun isRepetitiveCandidate(raw: String): Boolean {
        val candidate = normalizeLoopText(raw)
        if (candidate.length < 10) return false
        val candidateGrams = charGrams(candidate, 3)
        if (candidateGrams.isEmpty()) return false

        return state.messages
            .filter { it.role == ROLE_ASSISTANT }
            .takeLast(3)
            .map { normalizeLoopText(it.content) }
            .filter { it.length >= 10 }
            .any { previous ->
                if (candidate == previous) return@any true
                val previousGrams = charGrams(previous, 3)
                if (previousGrams.isEmpty()) return@any false
                val shared = candidateGrams.intersect(previousGrams).size.toDouble()
                val base = minOf(candidateGrams.size, previousGrams.size).coerceAtLeast(1).toDouble()
                val containment = shared / base
                val sameOpening = candidate.take(14) == previous.take(14)
                containment >= 0.56 || (sameOpening && containment >= 0.38)
            }
    }

    private fun normalizeLoopText(raw: String): String = raw
        .lowercase()
        .replace(Regex("[\\s。、！？!?「」『』…,.・:：;；()（）\\[\\]【】]+"), "")
        .trim()

    private fun charGrams(text: String, size: Int): Set<String> {
        if (text.length < size) return emptySet()
        return (0..text.length - size).mapTo(linkedSetOf()) { index ->
            text.substring(index, index + size)
        }
    }

''' + helper_anchor
    text = one(text, helper_anchor, helper_block, "hard anti-loop helper")

    GAME.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER}: novelty prompt + recent-reply blacklist + hard detector")


def patch_vm() -> None:
    text = VM.read_text(encoding="utf-8")
    if RETRY_MARKER in text:
        print(f"{RETRY_MARKER} already applied to ViewModel")
        return

    old = '''                            is GenerationEvent.Completed -> finalText = event.finalText
                        }
                    }

                    val afterAssistant = superMenheraGame.assistantTurn(finalText)'''
    new = '''                            is GenerationEvent.Completed -> finalText = event.finalText
                        }
                    }

                    // SUPER_MENHERA_V085_RETRY: one guarded retry for near-duplicate answers.
                    // This is intentionally capped at one retry so a repetition detector can never
                    // turn into its own generation loop.
                    if (superMenheraGame.isRepetitiveCandidate(finalText)) {
                        val rejectedDraft = finalText
                        logger.w("MENHERA", "Near-duplicate reply detected; retrying once")
                        finalText = ""
                        _ui.value = _ui.value.copy(
                            thinking = true,
                            generatingText = "",
                            runtimeStatus = "MENHERA RETHINKING"
                        )
                        val retrySystem = superMenheraGame.systemPrompt() + """

The previous draft below was rejected because it repeated a recent assistant response too closely.
REJECTED DRAFT:
$rejectedDraft

Write a genuinely different reply. Do not paraphrase the rejected draft. Move the conversation forward with a new emotional beat, concrete desire, callback, concession, changed stance, or specific implication grounded in this session.
""".trimIndent()
                        e2bChat.generate(
                            model = models.e2bFile,
                            currentUserMessage = clean,
                            systemPrompt = retrySystem,
                            history = history,
                            contextSize = _ui.value.contextSize.coerceAtLeast(6144L).coerceAtMost(8192L),
                            maxGenerationTokens = 384,
                            enableThinking = true,
                            topK = 40,
                            topP = 0.92,
                            temperature = 0.74
                        ).collect { event ->
                            when (event) {
                                GenerationEvent.Thinking -> _ui.value = _ui.value.copy(
                                    thinking = true,
                                    runtimeStatus = "MENHERA RETHINKING"
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
                    }

                    val afterAssistant = superMenheraGame.assistantTurn(finalText)'''
    text = one(text, old, new, "automatic anti-loop retry")
    VM.write_text(text, encoding="utf-8")
    print(f"Applied {RETRY_MARKER}: one automatic retry for near-duplicate dialogue")


def main() -> None:
    patch_game()
    patch_vm()
    print("Applied v085 anti-loop guard")


if __name__ == "__main__":
    main()
