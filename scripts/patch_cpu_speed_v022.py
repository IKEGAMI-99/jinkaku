from pathlib import Path
import re


PATH = Path("app/src/main/cpp/upstream_llama_jni.cpp")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if "CPU_SPEED_V022" in text:
        print("CPU speed patch already applied")
        return

    text = replace_once(
        text,
        '#include <string>\n#include <vector>\n',
        '#include <string>\n#include <thread>\n#include <vector>\n',
        "thread include",
    )

    text = replace_once(
        text,
        'int32_t g_gpu_layers = 0;\n',
        '''int32_t g_gpu_layers = 0;\n\n// CPU_SPEED_V022: preserve the already-evaluated prompt prefix between turns.\n// Generated tokens are appended too, so the next request can find the longest\n// exact prefix that still exists in the KV cache and discard only the tail.\nstd::vector<llama_token> g_cached_tokens;\nint32_t g_decode_threads = 6;\nint32_t g_batch_threads = 6;\n''',
        "cache globals",
    )

    text = replace_once(
        text,
        '    g_backend_label = "CPU";\n    g_gpu_layers = 0;\n}\n',
        '    g_backend_label = "CPU";\n    g_gpu_layers = 0;\n    g_cached_tokens.clear();\n}\n',
        "cache clear",
    )

    old_decode = '''std::string decode_prompt(const std::vector<llama_token> & tokens) {\n    constexpr int BATCH = 256;\n    llama_batch batch = llama_batch_init(BATCH, 0, 1);\n    if (!batch.token || !batch.pos || !batch.n_seq_id || !batch.seq_id || !batch.logits) {\n        llama_batch_free(batch);\n        return "llama_batch_init failed";\n    }\n\n    g_position = 0;\n    for (size_t offset = 0; offset < tokens.size(); offset += BATCH) {\n        batch.n_tokens = 0;\n        const size_t end = std::min(tokens.size(), offset + BATCH);\n        for (size_t i = offset; i < end; ++i) {\n            const bool want_logits = (i + 1 == tokens.size());\n            add_batch_token(batch, tokens[i], static_cast<llama_pos>(i), want_logits);\n        }\n        const int rc = llama_decode(g_ctx, batch);\n        if (rc != 0) {\n            llama_batch_free(batch);\n            return "llama_decode(prompt) failed rc=" + std::to_string(rc);\n        }\n        g_position = static_cast<int32_t>(end);\n    }\n    llama_batch_free(batch);\n    return {};\n}\n'''
    new_decode = '''std::string decode_prompt(const std::vector<llama_token> & tokens, size_t start) {\n    constexpr int BATCH = 512;\n    llama_batch batch = llama_batch_init(BATCH, 0, 1);\n    if (!batch.token || !batch.pos || !batch.n_seq_id || !batch.seq_id || !batch.logits) {\n        llama_batch_free(batch);\n        return "llama_batch_init failed";\n    }\n\n    g_position = static_cast<int32_t>(start);\n    for (size_t offset = start; offset < tokens.size(); offset += BATCH) {\n        batch.n_tokens = 0;\n        const size_t end = std::min(tokens.size(), offset + BATCH);\n        for (size_t i = offset; i < end; ++i) {\n            const bool want_logits = (i + 1 == tokens.size());\n            add_batch_token(batch, tokens[i], static_cast<llama_pos>(i), want_logits);\n        }\n        const int rc = llama_decode(g_ctx, batch);\n        if (rc != 0) {\n            llama_batch_free(batch);\n            return "llama_decode(prompt) failed rc=" + std::to_string(rc);\n        }\n        g_position = static_cast<int32_t>(end);\n    }\n    llama_batch_free(batch);\n    return {};\n}\n'''
    text = replace_once(text, old_decode, new_decode, "prompt decoder")

    # The UI/API is already CPU-only. Avoid even probing for a dead OpenCL path.
    pattern = re.compile(
        r'''        const std::string openclDevice = find_opencl_device\(\);\n'''
        r'''        const bool hasOpenCl = !openclDevice\.empty\(\);\n'''
        r'''        int32_t requestedGpuLayers = 0;\n'''
        r'''        switch \(backendMode\) \{.*?'''
        r'''        \}\n\n'''
        r'''        llama_model_params mparams = llama_model_default_params\(\);\n'''
        r'''        mparams\.n_gpu_layers = requestedGpuLayers;\n\n'''
        r'''        LOGI\(\n'''
        r'''            "loading model backendMode=%d opencl=%s gpuLayers=%d",\n'''
        r'''            static_cast<int>\(backendMode\),\n'''
        r'''            hasOpenCl \? openclDevice\.c_str\(\) : "none",\n'''
        r'''            requestedGpuLayers\n'''
        r'''        \);\n''',
        re.S,
    )
    replacement = '''        (void) backendMode;\n        (void) gpuLayers;\n        const int32_t requestedGpuLayers = 0;\n\n        llama_model_params mparams = llama_model_default_params();\n        mparams.n_gpu_layers = 0;\n\n        LOGI("loading model CPU-only");\n'''
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError("anchor not found: CPU-only native load block")

    old_ctx = '''        const int32_t ctx = std::clamp(static_cast<int32_t>(contextSize), 1024, 8192);\n        llama_context_params cparams = llama_context_default_params();\n        cparams.n_ctx = static_cast<uint32_t>(ctx);\n        cparams.n_batch = 256;\n        cparams.n_ubatch = 128;\n        cparams.n_threads = 6;\n        cparams.n_threads_batch = 6;\n\n        g_ctx = llama_init_from_model(g_model, cparams);\n'''
    new_ctx = '''        const int32_t ctx = std::clamp(static_cast<int32_t>(contextSize), 1024, 8192);\n        const unsigned hw = std::max(1u, std::thread::hardware_concurrency());\n        // Single-token decode is memory-bandwidth bound, so using every core can\n        // be slower. Cap decode at 6 while allowing prompt prefill to use up to 8.\n        g_decode_threads = static_cast<int32_t>(std::max(1u, std::min(6u, hw)));\n        g_batch_threads = static_cast<int32_t>(std::max(1u, std::min(8u, hw)));\n\n        llama_context_params cparams = llama_context_default_params();\n        cparams.n_ctx = static_cast<uint32_t>(ctx);\n        cparams.n_batch = 512;\n        cparams.n_ubatch = 256;\n        cparams.n_threads = g_decode_threads;\n        cparams.n_threads_batch = g_batch_threads;\n\n        g_ctx = llama_init_from_model(g_model, cparams);\n'''
    text = replace_once(text, old_ctx, new_ctx, "context tuning")

    text = replace_once(
        text,
        '''        g_context_size = ctx;\n\n        g_chat_templates = common_chat_templates_init(g_model, "");\n''',
        '''        g_context_size = ctx;\n        llama_set_n_threads(g_ctx, g_decode_threads, g_batch_threads);\n\n        g_chat_templates = common_chat_templates_init(g_model, "");\n''',
        "set thread counts",
    )

    old_log = '''        LOGI(\n            "model loaded with upstream llama.cpp ctx=%d threads=6 ubatch=128 backend=%s gpuLayers=%d",\n            ctx,\n            g_backend_label.c_str(),\n            g_gpu_layers\n        );\n'''
    new_log = '''        LOGI(\n            "model loaded CPU-only ctx=%d decodeThreads=%d batchThreads=%d batch=512 ubatch=256 backend=%s",\n            ctx,\n            g_decode_threads,\n            g_batch_threads,\n            g_backend_label.c_str()\n        );\n'''
    text = replace_once(text, old_log, new_log, "load log")

    old_begin = '''        llama_memory_clear(llama_get_memory(g_ctx), false);\n        llama_sampler_reset(g_sampler);\n        g_stop.store(false, std::memory_order_relaxed);\n        g_generated = 0;\n        g_prompt_tokens = tokenized;\n        g_prefill_us = 0;\n        g_decode_started_us = 0;\n        const int32_t available = std::max(16, g_context_size - tokenized - 4);\n        g_max_tokens = std::min(std::clamp(static_cast<int32_t>(maxTokens), 16, 1536), available);\n\n        const int64_t prefill_started = now_us();\n        const std::string decodeError = decode_prompt(tokens);\n        g_prefill_us = std::max<int64_t>(1, now_us() - prefill_started);\n        if (!decodeError.empty()) return error_string(env, decodeError);\n        g_decode_started_us = now_us();\n\n        const double prefill_tps = tokenized * 1000000.0 / static_cast<double>(g_prefill_us);\n        LOGI(\n            "generation begun promptTokens=%d maxTokens=%d thinking=true prefill=%.2f tok/s backend=%s",\n            tokenized,\n            g_max_tokens,\n            prefill_tps,\n            g_backend_label.c_str()\n        );\n'''
    new_begin = '''        // Reuse the longest exact prompt prefix that is already in the KV cache.\n        size_t reuse = 0;\n        const size_t max_common = std::min(tokens.size(), g_cached_tokens.size());\n        while (reuse < max_common && tokens[reuse] == g_cached_tokens[reuse]) ++reuse;\n        // Re-evaluate at least the final prompt token so fresh logits are available.\n        if (reuse >= tokens.size() && reuse > 0) reuse = tokens.size() - 1;\n\n        llama_memory_t mem = llama_get_memory(g_ctx);\n        if (reuse > 0) {\n            if (!llama_memory_seq_rm(mem, 0, static_cast<llama_pos>(reuse), -1)) {\n                LOGW("KV prefix removal failed at %zu; clearing cache", reuse);\n                llama_memory_clear(mem, false);\n                reuse = 0;\n            }\n        } else {\n            llama_memory_clear(mem, false);\n        }\n\n        llama_sampler_reset(g_sampler);\n        g_stop.store(false, std::memory_order_relaxed);\n        g_generated = 0;\n        const int32_t prefill_tokens = tokenized - static_cast<int32_t>(reuse);\n        // NativeInferenceStats.promptTokens is intentionally the number of tokens\n        // actually evaluated this turn so its prefill tok/s remains meaningful.\n        g_prompt_tokens = prefill_tokens;\n        g_prefill_us = 0;\n        g_decode_started_us = 0;\n        const int32_t available = std::max(16, g_context_size - tokenized - 4);\n        g_max_tokens = std::min(std::clamp(static_cast<int32_t>(maxTokens), 16, 1536), available);\n\n        const int64_t prefill_started = now_us();\n        const std::string decodeError = decode_prompt(tokens, reuse);\n        g_prefill_us = std::max<int64_t>(1, now_us() - prefill_started);\n        if (!decodeError.empty()) {\n            g_cached_tokens.clear();\n            return error_string(env, decodeError);\n        }\n        g_cached_tokens = tokens;\n        g_decode_started_us = now_us();\n\n        const double prefill_tps = prefill_tokens * 1000000.0 / static_cast<double>(g_prefill_us);\n        const double cache_pct = tokenized > 0 ? (100.0 * reuse / static_cast<double>(tokenized)) : 0.0;\n        LOGI(\n            "generation begun totalPrompt=%d prefillTokens=%d cachedPrefix=%zu cacheHit=%.1f%% maxTokens=%d thinking=true prefill=%.2f tok/s backend=%s",\n            tokenized,\n            prefill_tokens,\n            reuse,\n            cache_pct,\n            g_max_tokens,\n            prefill_tps,\n            g_backend_label.c_str()\n        );\n'''
    text = replace_once(text, old_begin, new_begin, "KV prefix cache")

    text = replace_once(
        text,
        '''        ++g_position;\n        ++g_generated;\n        return to_byte_array(env, piece);\n''',
        '''        ++g_position;\n        ++g_generated;\n        g_cached_tokens.push_back(token);\n        return to_byte_array(env, piece);\n''',
        "append generated token to cache",
    )

    PATH.write_text(text, encoding="utf-8")
    print("Applied CPU_SPEED_V022: KleidiAI build + 512/256 prefill + 6/8 thread tuning + KV prefix reuse")


if __name__ == "__main__":
    main()
