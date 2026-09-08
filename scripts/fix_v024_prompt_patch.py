from pathlib import Path
import re

PATH = Path("app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt")

text = PATH.read_text(encoding="utf-8")
pattern = re.compile(
    r'''    private fun buildSystemPrompt\(memories: List<String>, enableThinking: Boolean\): String \{.*?\n    \}\n\n    fun downloadE4B\(\) \{''',
    re.S,
)
replacement = '''    private fun buildSystemPrompt(memories: List<String>, enableThinking: Boolean): String {
        val persona = db.currentPersona()
        val memoryBlock = if (memories.isEmpty()) "(none)" else memories.joinToString("\\n") { "- $it" }
        val reasoning = if (enableThinking) {
            "<|think|>\\nThink carefully before answering, but keep internal reasoning private. Output only the final answer after thinking."
        } else {
            "Answer directly without a hidden thinking/reasoning phase. Do not emit thought or analysis markers."
        }
        return """$reasoning
You are Jinkaku, a persistent local AI with an evolving but coherent personality. Do not blindly agree. Be consistent with durable memories while treating them as fallible context. Reply naturally in the user's language.
Persona state: $persona
Relevant long-term memories:
$memoryBlock""".trimIndent()
    }

    fun downloadE4B() {'''
text, count = pattern.subn(lambda _: replacement, text, count=1)
if count != 1:
    raise RuntimeError("generated buildSystemPrompt not found")
PATH.write_text(text, encoding="utf-8")
print("Fixed v0.1.24 Kotlin prompt string literals")
