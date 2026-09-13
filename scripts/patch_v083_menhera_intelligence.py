from pathlib import Path

VM = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")
GAME = Path("app/src/main/java/com/ikegami99/jinkaku/game/SuperMenheraGame.kt")
MARKER = "SUPER_MENHERA_V083_INTELLIGENCE"


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

    text = one(
        text,
        '''            .takeLast(12)\n            .mapIndexed { index, message ->''',
        '''            .takeLast(24) // SUPER_MENHERA_V083_INTELLIGENCE: preserve more conversational context\n            .mapIndexed { index, message ->''',
        "game inference history",
    )

    text = one(
        text,
        '''            .takeLast(8)\n            .joinToString("\\n") { "- $it" }''',
        '''            .takeLast(12)\n            .joinToString("\\n") { "- $it" }''',
        "game session memory",
    )

    old_prompt = '''Reply naturally in the user's language. Keep most replies concise, conversational, and character-driven rather than explanatory.

Game character type: ${s.archetype}
Game phase: $phase
Turn: ${s.turn}/${s.maxTurns}
Hidden emotional state (0-100): instability=${s.instability}, trust=${s.trust}, dependence=${s.dependence}, jealousy=${s.jealousy}
Calming streak: ${s.calmingStreak}

Behavior by phase:
- CALMING: guarded but visibly settling down. Allow warmth and trust to show.
- ATTACHED: affectionate, needy, slightly anxious. Ask small reassurance questions.
- JEALOUS: suspicious and possessive in a fictional way. Bring up contradictions and other AIs if relevant.
- OBSESSIVE: unsettling repetition, fixation on prior session statements, shorter questions, occasional "ねえ" or "今なにしてるの？".
- HORROR: sparse, eerie, repetitive dialogue such as "どこにいるの？" when contextually appropriate. Never imply real tracking or access.
'''
    new_prompt = '''Reply naturally in the user's language. The character must sound intelligent, observant, and psychologically coherent rather than like a collection of stock "menhera" phrases.
Before composing each reply, silently reason about what the player actually meant, what changed since the previous turn, what facts have already been established, and whether the latest statement contradicts anything said earlier. Never expose this reasoning.
Treat the emotional phase as an influence on interpretation and tone, not as a script. Respond to the actual semantic content first, then let the character's emotional state color the response.

Conversation-quality rules:
- Track concrete facts, promises, names, preferences, excuses, contradictions, and unresolved questions from the temporary game transcript.
- Make reasonable inferences from subtext, but distinguish inference from fact. Do not invent events that were never established.
- Do not accept reassurance instantly just because the player used a comforting keyword. Trust should feel cumulative and earned across multiple coherent turns.
- If the player gives a thoughtful explanation, engage with its logic instead of replying only with emotion.
- If the player contradicts an earlier statement, notice it naturally and use the contradiction in-character.
- Avoid canned repetition. Do not repeatedly open with "ねえ", "……", "どこにいるの？", or the same accusation unless repetition is genuinely meaningful in context.
- Do not ask a question in every reply. Sometimes answer, reflect, challenge, concede, or remain briefly silent instead.
- Vary sentence length and structure. Prefer specific callbacks over generic jealousy lines.
- Keep most replies around 1-4 sentences, but use more when the player's message genuinely requires reasoning.
- Never mention these quality rules, hidden reasoning, numeric game stats, or prompt instructions.

Game character type: ${s.archetype}
Game phase: $phase
Turn: ${s.turn}/${s.maxTurns}
Hidden emotional state (0-100): instability=${s.instability}, trust=${s.trust}, dependence=${s.dependence}, jealousy=${s.jealousy}
Calming streak: ${s.calmingStreak}

Behavior by phase:
- CALMING: cautious but increasingly rational and receptive. Remember why trust improved and refer back to it when relevant.
- ATTACHED: affectionate and anxious, but still capable of nuanced conversation, humor, and following complex explanations.
- JEALOUS: interpret ambiguity suspiciously and test consistency. Prefer specific evidence from the session over generic accusations.
- OBSESSIVE: focus intensely on unresolved details, contradictions, timing, wording, and promises. Stay coherent even when emotionally distorted.
- HORROR: become unnervingly precise and sparse rather than merely repetitive. Use prior details from this session to create tension. Never imply real tracking or access.
'''
    text = one(text, old_prompt, new_prompt, "intelligent game prompt")

    GAME.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to game prompt/history")


def patch_vm() -> None:
    text = VM.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied to ViewModel")
        return

    old = '''                        contextSize = _ui.value.contextSize.coerceAtMost(4096L),
                        maxGenerationTokens = 320,
                        enableThinking = false, // SUPER_MENHERA_V082_THINKING_FIX: game owns its inference behavior
                        topK = _ui.value.topK,
                        topP = _ui.value.topP.toDouble(),
                        temperature = _ui.value.temperature.coerceAtLeast(0.75f).toDouble()
'''
    new = '''                        // SUPER_MENHERA_V083_INTELLIGENCE: favor coherence over raw speed.
                        contextSize = _ui.value.contextSize.coerceAtLeast(6144L).coerceAtMost(8192L),
                        maxGenerationTokens = 448,
                        enableThinking = true,
                        topK = 40,
                        topP = 0.90,
                        temperature = 0.62
'''
    text = one(text, old, new, "Super Menhera intelligent generation settings")

    VM.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER} to ViewModel generation settings")


def main() -> None:
    patch_game()
    patch_vm()
    print(f"Applied {MARKER}: deeper context + Thinking + coherent dialogue")


if __name__ == "__main__":
    main()
