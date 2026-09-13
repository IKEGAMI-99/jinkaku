from pathlib import Path

GAME = Path("app/src/main/java/com/ikegami99/jinkaku/game/SuperMenheraGame.kt")
MARKER = "SUPER_MENHERA_V085_ANTILOOP"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = GAME.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied")
        return

    # Give the model an explicit short blacklist of its own recent answers. The history alone was
    # not enough for E2B to notice that it was paraphrasing itself every turn.
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

    GAME.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER}: explicit novelty + recent-reply blacklist")


if __name__ == "__main__":
    main()
