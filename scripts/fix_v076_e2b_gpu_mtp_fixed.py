from pathlib import Path

E2B_CHAT = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E2BChatEngine.kt")
MARKER = "E2B_GPU_MTP_FIXED_V076"


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = E2B_CHAT.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"{MARKER} already applied")
        return

    old = '''        unload()
        ExperimentalFlags.enableBenchmark = true
        ExperimentalFlags.enableSpeculativeDecoding = true
        Engine.setNativeMinLogSeverity(LogSeverity.ERROR)
        context.cacheDir.mkdirs()

        val created = Engine(
            EngineConfig(
                modelPath = path,
                backend = Backend.GPU(),
                visionBackend = null,
                audioBackend = null,
                maxNumTokens = maxContext,
                cacheDir = context.cacheDir.absolutePath
            )
        )
        try {
            created.initialize()
        } catch (t: Throwable) {
            runCatching { created.close() }
            throw t
        }
'''

    new = f'''        unload()
        ExperimentalFlags.enableBenchmark = true
        ExperimentalFlags.enableSpeculativeDecoding = true
        Engine.setNativeMinLogSeverity(LogSeverity.ERROR)
        context.cacheDir.mkdirs()

        // {MARKER}: E2B main chat has one runtime policy only.
        // GPU and MTP/speculative decoding are mandatory. Never retry with MTP off and never
        // fall back to CPU, because a silent fallback makes performance/compatibility impossible
        // to verify from the UI.
        logger.i(
            "E2B_CHAT",
            "Engine init policy backend=GPU mtp=ON fallback=NONE ctx=$maxContext file=${{model.name}}"
        )
        val created = Engine(
            EngineConfig(
                modelPath = path,
                backend = Backend.GPU(),
                visionBackend = null,
                audioBackend = null,
                maxNumTokens = maxContext,
                cacheDir = context.cacheDir.absolutePath
            )
        )
        try {{
            created.initialize()
        }} catch (t: Throwable) {{
            runCatching {{ created.close() }}
            logger.e("E2B_CHAT", "GPU+MTP initialization failed; fallback=NONE", t)
            throw IllegalStateException(
                "E2B LiteRT-LMはGPU + MTP固定です。GPU+MTP初期化に失敗しました。" +
                    "MTP OFFやCPUへのフォールバックは行いません。",
                t
            )
        }}
'''

    text = one(text, old, new, "fixed GPU+MTP initialization policy")
    E2B_CHAT.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER}: GPU+MTP mandatory, fallback disabled")


if __name__ == "__main__":
    main()
