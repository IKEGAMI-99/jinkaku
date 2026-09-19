# AGENTS.md — JINKAKU guide for AI coding agents

This file is the primary entry point for AI agents that need to **analyze, summarize, reproduce, modify, debug, or extend JINKAKU**.

JINKAKU is an Android local-personality AI application. The current normal chat path uses **Gemma 4 E2B LiteRT-LM with GPU + MTP**, with local Persona, long-term Memory, inference telemetry, optional Tavily web search, idle monologue, UI customization, and a separate Super Menhera conversation-game mode.

Before changing anything, read:

1. `README.md` — current product-level overview.
2. `.github/workflows/android.yml` — **authoritative build pipeline and patch order**.
3. This file — architecture and modification rules.
4. `docs/CHAT_HANDOFF.md` — historical implementation notes. Useful, but some sections describe older versions and must not override the current workflow/source.

---

## 1. The most important fact about this repository

**The checked-in Kotlin/C++ files are not always the final release sources.**

JINKAKU currently uses a patch-based build architecture:

```
checked-in base source
        ↓
Python patches in scripts/
        ↓
generated / transformed final source
        ↓
Gradle Android release build
        ↓
APK
```

The exact sequence is defined in:

```
.github/workflows/android.yml
```

Do not infer current release behavior from one stored source file alone.

Many Python scripts replace exact source strings and depend on output from earlier scripts. Editing an old anchor can break a later patch with errors such as:

```
anchor not found
expected exactly one anchor
```

When determining what the released app actually does, prefer this order of evidence:

1. latest `.github/workflows/android.yml`
2. the last patches applied by that workflow
3. source generated after applying all workflow patches
4. latest GitHub Release
5. checked-in base source

---

## 2. Current architecture

High-level data flow:

```
Android UI
   ↓
JinkakuViewModel
   ├── Persona
   ├── Chat history
   ├── Memory retrieval
   ├── optional Tavily web search
   ├── generation settings
   ↓
E2BChatEngine
   ↓
Gemma 4 E2B LiteRT-LM
GPU + MTP
   ↓
response + inference telemetry
   ↓
SQLite chat / Memory persistence
```

The major components are:

| Area | Main files / source of truth |
| --- | --- |
| App entry | `MainActivity.kt`, `JinkakuApplication.kt` |
| State / orchestration | `JinkakuViewModel.kt` |
| Current main inference | `ai/E2BChatEngine.kt` plus later workflow patches |
| Memory extraction | `ai/E2BMemoryEngine.kt`, `ai/MemoryEngine.kt` |
| Embeddings | `ai/EmbeddingGemmaBridge.kt`, native bridge |
| Inference telemetry | `ai/InferenceTelemetry.kt` |
| Database | `data/JinkakuDatabase.kt` |
| Model management | `model/ModelManager.kt` |
| Main modern UI | `ui/ModernJinkakuApp.kt` plus UI patches |
| Legacy / alternate UI | `ui/JinkakuApp.kt`, `ui/BrandedJinkakuApp.kt` |
| App updater | `update/AppUpdater.kt` |
| Backup | `backup/BackupManager.kt` |
| Super Menhera | `game/SuperMenheraGame.kt` plus v082-v085 patches |
| Native / legacy llama bridge | `app/src/main/cpp/`, `ai/E4BEngine.kt`, `ai/UpstreamLlamaBridge.kt` |
| Web search | introduced by `scripts/patch_v062_tavily_web_search.py` |
| Idle monologue | introduced by `scripts/patch_v064_monologue.py` |
| Persona generator | introduced by `scripts/patch_v066_random_persona.py` |
| Settings structure | `scripts/patch_v068_settings_categories.py` and later patches |
| Current E2B-only path | `scripts/patch_v077_e2b_only.py` and later |
| 8K / telemetry | `scripts/patch_v079_telemetry_context8k.py` |
| Settings help / updater | `scripts/patch_v081_settings_help_updater.py` |
| Super Menhera | `scripts/patch_v082_super_menhera.py` through `patch_v085_menhera_antiloop.py` |

---

## 3. Current normal-chat runtime

The current main model is:

```
litert-community/gemma-4-E2B-it-litert-lm
gemma-4-E2B-it.litertlm
```

Important properties:

- LiteRT-LM
- GPU backend
- MTP enabled
- no automatic CPU fallback in the current normal-chat path
- context can reach 8K after the current patch chain
- optional Thinking
- Top-K / Top-P / Temperature controls
- repetition detection / retry behavior
- live context and performance telemetry

Do not describe E4B as the current main chat model merely because `E4BEngine.kt` still exists.

E4B and llama.cpp/JNI-related code remain partly for legacy, compatibility, experiments, and EmbeddingGemma/native support.

---

## 4. Persistence and Memory model

JINKAKU stores its primary conversational state locally.

Important concepts include:

- chat sessions
- chat messages
- Persona
- long-term Memory
- model settings
- inference settings
- updater state / related preferences

Memory categories include concepts such as:

- USER
- SELF
- RELATIONSHIP
- EPISODIC
- PREFERENCE
- PROJECT
- PERSONA

A critical rule added in later versions is **memory ownership attribution**.

A USER memory describes the human user.
A SELF / JINKAKU memory describes the assistant.
A RELATIONSHIP memory describes the relationship.
A PROJECT memory describes project state.

Do not collapse these roles when rewriting the memory pipeline. First-person wording inside a stored memory is not enough to determine ownership.

See:

```
scripts/patch_v061_memory_role_attribution.py
```

---

## 5. Features that are intentionally isolated

### Super Menhera

Super Menhera is a separate conversation game.

It must not silently contaminate normal:

- chat history
- Persona
- Memory
- Web context
- long-term user state

Its temporary game state is intended to be discarded when the game ends.

The relevant implementation evolved through:

```
patch_v082_super_menhera.py
patch_v083_menhera_intelligence.py
patch_v084_menhera_emotion.py
patch_v085_menhera_antiloop.py
fix_v085_compile.py
```

When modifying it, read these in workflow order.

### Idle monologue

Idle monologue is generated from Persona + recent conversation context.

It is intentionally not treated as a new user message and should not enter normal Memory extraction as if the user said it.

See:

```
scripts/patch_v064_monologue.py
```

---

## 6. Optional web search

JINKAKU can use Tavily for current/external information.

Web search is optional. Normal local conversation does not require Tavily.

The implementation supports modes such as:

- OFF
- MANUAL
- AUTO

Web results are treated as external untrusted context and appended to the model prompt.

Do not hard-code an API key into source code.

Primary implementation history:

```
scripts/patch_v062_tavily_web_search.py
scripts/patch_v063_web_prefill_budget.py
```

---

## 7. UI architecture

The current release UI is generated from `ModernJinkakuApp.kt` plus many sequential UI patches.

Important features introduced by patches include:

- dark/light themes
- two-color accents
- automatic readable foreground colors
- AI avatar/icon customization
- font scaling
- glass-style UI refinements
- categorized Settings
- live Thinking / context feedback
- Persona generator
- updater UI
- Super Menhera route

Do not select an edit target just because a similarly named UI file exists.

First determine which composable is actually launched and which patches later rewrite it.

---

## 8. Model files

Model files are not bundled into the APK.

Important filenames currently include:

```
gemma-4-E2B-it.litertlm
embeddinggemma-300M-qat-Q4_0.gguf
```

Legacy E4B files may also be supported by model-management code, but that does not make E4B the current normal-chat runtime.

Model download/import behavior lives mainly in:

```
app/src/main/java/com/ikegami99/jinkaku/model/ModelManager.kt
```

Do not casually change model filenames, hashes, storage paths, or validation thresholds without tracing the updater/import/settings dependencies.

---

## 9. Build environment

Current Android configuration is approximately:

- JDK 17
- Gradle 8.13
- compileSdk 36
- targetSdk 36
- minSdk 33
- arm64-v8a
- NDK 29.0.13113456
- CMake 3.31.6

The canonical versions are the values in the current source and workflow, not this prose.

Basic Gradle command:

```bash
gradle --no-daemon :app:assembleRelease
```

However, a release-equivalent build requires the workflow patch sequence first.

---

## 10. How an AI agent should analyze JINKAKU

For a trustworthy analysis:

### Step A — identify the current build graph

Read:

```
.github/workflows/android.yml
```

Extract the patch scripts in exact order.

### Step B — distinguish base source from generated source

Inspect the relevant stored Kotlin/C++ file and all patches that modify it.

Do not summarize only the base file if a later patch replaces that logic.

### Step C — identify active vs legacy paths

Search callers and launch paths.

Especially distinguish:

- E2B current main chat
- E4B legacy/native code
- Modern UI vs older UI files
- normal chat vs Super Menhera

### Step D — reconstruct final behavior

When possible, apply the workflow patches in a disposable checkout and inspect the resulting source.

### Step E — state uncertainty explicitly

If you have not run the patch chain, build, CI, or app on a device, say so.

Never report:

- “build succeeded”
- “feature works”
- “APK was released”
- “device verified”

unless you actually verified that state.

---

## 11. How to reproduce or fork JINKAKU

A clean reimplementation should preserve these conceptual layers rather than copying accidental patch history:

```
UI
↓
application state / orchestration
↓
Persona + Memory + recent history + optional Web context
↓
local inference runtime
↓
response / telemetry
↓
local persistence
```

Recommended modules for a clean fork:

```
app/
ui/
chat/
persona/
memory/
inference/
models/
web/
storage/
update/
telemetry/
game/
```

The current patch-heavy architecture is useful for preserving development history, but it is not the ideal architecture for a ground-up clone.

If rebuilding from scratch, prefer normal source modules over replaying dozens of textual Python patches.

---

## 12. How to modify JINKAKU safely

Before editing:

1. inspect latest `main`
2. inspect current workflow
3. inspect recent release/version
4. search all references to the target symbol/file
5. identify which later patches depend on the code you want to change

Prefer small changes.

Do not combine unrelated UI, database, model, updater, and build-system changes into one giant edit unless necessary.

For patch-based code:

- preserve exact anchors unless intentionally migrating them
- preserve marker/idempotency logic
- keep patch order valid
- ensure a patch can be reapplied safely when designed to be idempotent
- validate downstream patches after changing earlier output

---

## 13. Where to make common changes

### Change chat behavior

Start with:

```
JinkakuViewModel.kt
ai/E2BChatEngine.kt
scripts/patch_v077_e2b_only.py
scripts/patch_v079_telemetry_context8k.py
later chat-related patches
```

### Change Memory behavior

Start with:

```
ai/MemoryEngine.kt
ai/E2BMemoryEngine.kt
data/JinkakuDatabase.kt
scripts/patch_v061_memory_role_attribution.py
```

### Change Persona

Start with:

```
JinkakuViewModel.kt
ui/ModernJinkakuApp.kt
scripts/patch_v066_random_persona.py
```

### Change UI

Start with:

```
ui/ModernJinkakuApp.kt
scripts/patch_v031_*.py onward
```

Then inspect every later UI patch in workflow order.

### Change web search

Start with:

```
scripts/patch_v062_tavily_web_search.py
scripts/patch_v063_web_prefill_budget.py
```

### Change updater

Start with:

```
update/AppUpdater.kt
scripts/patch_v081_settings_help_updater.py
.github/workflows/android.yml
```

### Change Super Menhera

Start with:

```
game/SuperMenheraGame.kt
scripts/patch_v082_super_menhera.py
scripts/patch_v083_menhera_intelligence.py
scripts/patch_v084_menhera_emotion.py
scripts/patch_v085_menhera_antiloop.py
```

### Change model/runtime

Start with:

```
model/ModelManager.kt
ai/E2BChatEngine.kt
app/build.gradle.kts
.github/workflows/android.yml
```

Be especially careful with LiteRT-LM API versions, GPU support, MTP behavior, context limits, and model-file compatibility.

---

## 14. Validation checklist for AI agents

After a code change, verify as many of these as the environment allows:

- patch chain completes
- no downstream `anchor not found`
- Kotlin compiles
- C++/JNI compiles if touched
- release APK builds
- app version behavior is intentional
- existing app ID is preserved unless explicitly changing package identity
- signing compatibility is preserved when update compatibility matters
- database schema/state is not accidentally destroyed
- Persona still loads
- Memory retrieval still preserves ownership
- E2B model loading still works
- Context / Thinking settings still reach inference
- telemetry still updates
- optional Web search still remains optional
- Super Menhera remains isolated
- app updater still detects a newer `versionCode`

If device testing is unavailable, report it as unverified instead of guessing.

---

## 15. Release and versioning

Version values are stored in:

```
gradle.properties
```

The GitHub Actions workflow creates the release APK and `version.json`.

For an app release, verify the latest existing version before incrementing.

Do not reuse an old version number for a materially different APK.

For documentation-only commits, the repository has historically used `[skip ci]` to avoid unnecessary release builds. Confirm current branch-protection/CI expectations before relying on it.

---

## 16. Signing warning

The v0.x release signing configuration currently prioritizes personal use and update continuity.

The repository contains a fixed release keystore/configuration.

Treat this as **not suitable for high-security public distribution**.

Do not rotate the signing identity casually: doing so can break in-place updates for already installed builds.

---

## 17. Image / branding changes

Do not regenerate a user-provided logo or wordmark unless explicitly requested.

Inspect the actual file format, resolution, alpha channel, and resource references.

The header-specific wordmark is:

```
app/src/main/res/drawable-nodpi/jinkaku_header_wordmark.png
```

Older/shared assets may also be referenced by launcher resources. Do not overwrite them merely because the names look similar.

For historical branding details see:

```
docs/CHAT_HANDOFF.md
```

---

## 18. Codebase size and shape

The checked-in application source is roughly a few thousand lines of Kotlin plus native C/C++.

The repository is larger than that because it also contains many Python migration/patch scripts.

When reporting “lines of code”, distinguish:

- current checked-in app source
- Python patch/migration source
- generated post-patch source
- tests
- documentation/resources

Otherwise the number is misleading.

---

## 19. Preferred agent behavior

When working on this repository:

- inspect before editing
- use current source, not assumptions from old docs
- make small, reviewable changes
- preserve existing user data unless explicitly migrating it
- do not silently remove features
- do not replace the chosen model without an explicit request
- do not weaken local/privacy behavior merely for implementation convenience
- do not claim validation you did not perform
- keep the repository buildable at each meaningful step
- explain which source is authoritative when conflicting legacy code exists

A good JINKAKU change should be understandable by the next agent without reconstructing the entire archaeological site from commit sediment.

---

## 20. Fast orientation checklist

If you only have a few minutes:

```
README.md
AGENTS.md
.github/workflows/android.yml
gradle.properties
app/src/main/java/com/ikegami99/jinkaku/JinkakuViewModel.kt
app/src/main/java/com/ikegami99/jinkaku/ai/E2BChatEngine.kt
app/src/main/java/com/ikegami99/jinkaku/data/JinkakuDatabase.kt
app/src/main/java/com/ikegami99/jinkaku/model/ModelManager.kt
app/src/main/java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt
scripts/patch_v077_e2b_only.py
scripts/patch_v079_telemetry_context8k.py
scripts/patch_v081_settings_help_updater.py
scripts/patch_v082_super_menhera.py
scripts/patch_v085_menhera_antiloop.py
```

Then inspect any earlier patch specifically related to the feature you are changing.

That is the shortest reliable route to understanding the current app.
