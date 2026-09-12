from pathlib import Path

E2B_CHAT = Path("app/src/main/java/com/ikegami99/jinkaku/ai/E2BChatEngine.kt")
MARKER = "E2B_MTP_FALLBACK_V075"


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

    text = one(
        text,
        "    private var loadedContext: Int = 0\n",
        "    private var loadedContext: Int = 0\n"
        f"    // {MARKER}: remember whether the active GPU engine actually has MTP enabled.\n"
        "    private var loadedMtp: Boolean = false\n",
        "loaded MTP state",
    )

    text = one(
        text,
        '            "Generation start runtime=LiteRT-LM backend=GPU mtp=ON channels=metadata thinking=OFF async=true ctx=$maxContext " +\n',
        '            "Generation start runtime=LiteRT-LM backend=GPU mtp=${if (loadedMtp) \"ON\" else \"OFF\"} channels=metadata thinking=OFF async=true ctx=$maxContext " +\n',
        "dynamic MTP generation-start log",
    )

    text = one(
        text,
        '                        "Generation complete backend=GPU mtp=ON prefillTokS=${"%.1f".format(info.lastPrefillTokensPerSecond)} " +\n',
        '                        "Generation complete backend=GPU mtp=${if (loadedMtp) \"ON\" else \"OFF\"} prefillTokS=${"%.1f".format(info.lastPrefillTokensPerSecond)} " +\n',
        "dynamic MTP benchmark log",
    )

    text = one(
        text,
        '                    logger.i("E2B_CHAT", "Generation complete backend=GPU mtp=ON chars=${finalText.length}")\n',
        '                    logger.i("E2B_CHAT", "Generation complete backend=GPU mtp=${if (loadedMtp) \"ON\" else \"OFF\"} chars=${finalText.length}")\n',
        "dynamic MTP fallback completion log",
    )

    old_init = '''        unload()
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

        engine = created
        loadedPath = path
        loadedContext = maxContext
        logger.i("E2B_CHAT", "Engine loaded backend=GPU mtp=ON ctx=$maxContext file=${model.name}")
        return created
'''

    new_init = f'''        unload()
        ExperimentalFlags.enableBenchmark = true
        Engine.setNativeMinLogSeverity(LogSeverity.ERROR)
        context.cacheDir.mkdirs()

        // {MARKER}: third-party .litertlm bundles do not necessarily contain a compatible
        // speculative-decoding/MTP graph. The official Google bundle does, but forcing MTP on
        // every model can make Engine.initialize() fail before generation starts. Keep the fast
        // path first, then retry the same GPU backend with MTP disabled before declaring the
        // model GPU-incompatible. This never silently falls back to CPU.
        fun createGpuEngine(mtp: Boolean): Engine {{
            ExperimentalFlags.enableSpeculativeDecoding = mtp
            val candidate = Engine(
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
                candidate.initialize()
                return candidate
            }} catch (t: Throwable) {{
                runCatching {{ candidate.close() }}
                throw t
            }}
        }}

        val created = try {{
            val candidate = createGpuEngine(mtp = true)
            loadedMtp = true
            candidate
        }} catch (mtpError: Throwable) {{
            logger.w(
                "E2B_CHAT",
                "GPU+MTP init failed; retrying GPU with MTP=OFF error=${{mtpError.javaClass.simpleName}}: ${{mtpError.message}}"
            )
            try {{
                val candidate = createGpuEngine(mtp = false)
                loadedMtp = false
                logger.i("E2B_CHAT", "GPU fallback succeeded mtp=OFF ctx=$maxContext file=${{model.name}}")
                candidate
            }} catch (gpuError: Throwable) {{
                loadedMtp = false
                throw IllegalStateException(
                    "E2B LiteRT-LMをGPUで読み込めません。MTP ON/OFFの両方で失敗しました。" +
                        "このモデルは端末のLiteRT GPU delegateと互換性がない可能性があります。",
                    gpuError
                )
            }}
        }}

        engine = created
        loadedPath = path
        loadedContext = maxContext
        logger.i(
            "E2B_CHAT",
            "Engine loaded backend=GPU mtp=${{if (loadedMtp) \"ON\" else \"OFF\"}} ctx=$maxContext file=${{model.name}}"
        )
        return created
'''

    text = one(text, old_init, new_init, "GPU MTP initialization block")

    text = one(
        text,
        "        loadedContext = 0\n",
        "        loadedContext = 0\n        loadedMtp = false\n",
        "reset loaded MTP state",
    )

    E2B_CHAT.write_text(text, encoding="utf-8")
    print(f"Applied {MARKER}: GPU+MTP first, GPU MTP-off retry, no silent CPU fallback")


if __name__ == "__main__":
    main()
