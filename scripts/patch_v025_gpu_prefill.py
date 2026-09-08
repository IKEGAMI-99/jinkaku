from pathlib import Path
import re


PATH = Path("app/src/main/cpp/upstream_llama_jni.cpp")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"anchor not found: {label}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if "GPU_PREFILL_V025" in text:
        print("GPU prefill v0.1.25 patch already applied")
        return

    text = replace_once(
        text,
        """std::vector<llama_token> g_cached_tokens;\nint32_t g_decode_threads = 6;\nint32_t g_batch_threads = 6;\n""",
        """std::vector<llama_token> g_cached_tokens;\nint32_t g_decode_threads = 6;\nint32_t g_batch_threads = 6;\n\n// GPU_PREFILL_V025: use OpenCL only for cold, long prompt evaluation.\n// Token-by-token generation remains on the standard ARM CPU kernels. A full\n// backend swap is intentionally avoided for short prompts because model reload\n// and KV-state transfer would cost more than the saved prefill time.\nstd::string g_model_path;\nconstexpr int32_t GPU_PREFILL_MIN_TOKENS = 768;\n""",
        "GPU prefill globals",
    )

    text = replace_once(
        text,
        "void free_model_locked() {\n",
        "void free_model_locked(bool clear_cache = true) {\n",
        "free model signature",
    )
    text = replace_once(
        text,
        "    g_cached_tokens.clear();\n}\n",
        "    if (clear_cache) g_cached_tokens.clear();\n}\n",
        "conditional cache clear",
    )

    text = replace_once(
        text,
        """        const std::string path = from_jstring(env, modelPath);\n        if (path.empty()) return error_string(env, \"empty model path\");\n""",
        """        const std::string path = from_jstring(env, modelPath);\n        if (path.empty()) return error_string(env, \"empty model path\");\n        g_model_path = path;\n""",
        "remember model path",
    )

    helper_anchor = "std::string token_piece(llama_token token) {\n"
    helper_code = r'''std::string load_phase_runtime_locked(
        const std::string & path,
        int32_t ctx,
        int32_t gpu_layers,
        bool generation_tools) {
    free_model_locked(false);

    llama_model_params mparams = llama_model_default_params();
    mparams.n_gpu_layers = gpu_layers;
    g_model = llama_model_load_from_file(path.c_str(), mparams);
    if (!g_model) return "phase llama_model_load_from_file returned null";

    g_vocab = llama_model_get_vocab(g_model);
    if (!g_vocab) {
        free_model_locked(false);
        return "phase llama_model_get_vocab returned null";
    }

    llama_context_params cparams = llama_context_default_params();
    cparams.n_ctx = static_cast<uint32_t>(ctx);
    cparams.n_batch = 512;
    cparams.n_ubatch = gpu_layers > 0 ? 128 : 256;
    cparams.n_threads = g_decode_threads;
    cparams.n_threads_batch = g_batch_threads;

    g_ctx = llama_init_from_model(g_model, cparams);
    if (!g_ctx) {
        free_model_locked(false);
        return "phase llama_init_from_model returned null";
    }
    g_context_size = ctx;
    llama_set_n_threads(g_ctx, g_decode_threads, g_batch_threads);
    g_gpu_layers = gpu_layers;
    g_backend_label = gpu_layers > 0 ? "GPU PREFILL · OpenCL" : "CPU";

    if (generation_tools) {
        g_chat_templates = common_chat_templates_init(g_model, "");
        if (!g_chat_templates) {
            free_model_locked(false);
            return "phase common_chat_templates_init returned null";
        }

        llama_sampler_chain_params chainParams = llama_sampler_chain_default_params();
        g_sampler = llama_sampler_chain_init(chainParams);
        if (!g_sampler) {
            free_model_locked(false);
            return "phase llama_sampler_chain_init returned null";
        }
        llama_sampler_chain_add(g_sampler, llama_sampler_init_top_k(64));
        llama_sampler_chain_add(g_sampler, llama_sampler_init_top_p(0.95f, 1));
        llama_sampler_chain_add(g_sampler, llama_sampler_init_temp(1.0f));
        llama_sampler_chain_add(g_sampler, llama_sampler_init_dist(LLAMA_DEFAULT_SEED));
    }

    g_stop.store(false, std::memory_order_relaxed);
    return {};
}

std::string export_seq_state_locked(std::vector<uint8_t> & state) {
    if (!g_ctx) return "cannot export state without context";
    const size_t size = llama_state_seq_get_size_ext(g_ctx, 0, LLAMA_STATE_SEQ_FLAGS_NONE);
    if (size == 0) return "llama_state_seq_get_size_ext returned 0";
    state.resize(size);
    const size_t written = llama_state_seq_get_data_ext(
        g_ctx,
        state.data(),
        state.size(),
        0,
        LLAMA_STATE_SEQ_FLAGS_NONE
    );
    if (written != state.size()) {
        state.clear();
        return "llama_state_seq_get_data_ext size mismatch";
    }
    return {};
}

std::string import_seq_state_locked(const std::vector<uint8_t> & state) {
    if (!g_ctx || state.empty()) return "cannot import empty state";
    const size_t consumed = llama_state_seq_set_data_ext(
        g_ctx,
        state.data(),
        state.size(),
        0,
        LLAMA_STATE_SEQ_FLAGS_NONE
    );
    return consumed == state.size() ? std::string() : "llama_state_seq_set_data_ext size mismatch";
}

std::string gpu_prefill_then_cpu_locked(
        const std::vector<llama_token> & tokens,
        int64_t & gpu_compute_us,
        int64_t & handoff_us,
        size_t & state_bytes) {
    if (g_model_path.empty()) return "model path is unavailable";
    const std::string opencl = find_opencl_device();
    if (opencl.empty()) return "OpenCL/Adreno device not available";

    const int32_t ctx = g_context_size;
    LOGI("GPU prefill phase start tokens=%zu device=%s", tokens.size(), opencl.c_str());

    std::string error = load_phase_runtime_locked(g_model_path, ctx, 999, false);
    if (!error.empty()) return "GPU phase load failed: " + error;

    llama_memory_clear(llama_get_memory(g_ctx), false);
    const int64_t compute_started = now_us();
    error = decode_prompt(tokens, 0);
    gpu_compute_us = std::max<int64_t>(1, now_us() - compute_started);
    if (!error.empty()) return "GPU prompt decode failed: " + error;

    std::vector<uint8_t> state;
    error = export_seq_state_locked(state);
    if (!error.empty()) return "GPU state export failed: " + error;
    state_bytes = state.size();

    const int64_t handoff_started = now_us();
    error = load_phase_runtime_locked(g_model_path, ctx, 0, true);
    if (!error.empty()) return "CPU phase reload failed: " + error;

    error = import_seq_state_locked(state);
    if (!error.empty()) return "CPU state import failed: " + error;

    // A restored KV state does not guarantee fresh logits on the new backend.
    // Drop and re-evaluate only the final prompt token on CPU. This is tiny
    // compared with re-prefilling the whole prompt and leaves decode fully CPU.
    if (!tokens.empty()) {
        llama_memory_t mem = llama_get_memory(g_ctx);
        const llama_pos last = static_cast<llama_pos>(tokens.size() - 1);
        if (!llama_memory_seq_rm(mem, 0, last, -1)) {
            return "CPU handoff could not remove final prompt token";
        }
        error = decode_prompt(tokens, tokens.size() - 1);
        if (!error.empty()) return "CPU final-token refresh failed: " + error;
    }

    handoff_us = std::max<int64_t>(1, now_us() - handoff_started);
    g_backend_label = "CPU";
    g_gpu_layers = 0;
    LOGI(
        "GPU prefill handoff complete gpuComputeMs=%.1f handoffMs=%.1f stateMiB=%.1f",
        gpu_compute_us / 1000.0,
        handoff_us / 1000.0,
        state_bytes / (1024.0 * 1024.0)
    );
    return {};
}

'''
    text = replace_once(text, helper_anchor, helper_code + helper_anchor, "GPU prefill helpers")

    prefill_pattern = re.compile(
        r'''        const int64_t prefill_started = now_us\(\);\n'''
        r'''        const std::string decodeError = decode_prompt\(tokens, reuse\);\n'''
        r'''        g_prefill_us = std::max<int64_t>\(1, now_us\(\) - prefill_started\);\n'''
        r'''        if \(!decodeError\.empty\(\)\) \{\n'''
        r'''            g_cached_tokens\.clear\(\);\n'''
        r'''            return error_string\(env, decodeError\);\n'''
        r'''        \}\n'''
        r'''        g_cached_tokens = tokens;\n'''
        r'''        g_decode_started_us = now_us\(\);\n''',
        re.S,
    )
    prefill_replacement = r'''        const int64_t prefill_started = now_us();
        bool used_gpu_prefill = false;
        int64_t gpu_compute_us = 0;
        int64_t handoff_us = 0;
        size_t state_bytes = 0;
        std::string decodeError;

        // Only cold / non-reusable long prefixes use the GPU path. Once the CPU
        // KV prefix cache is warm, the suffix is normally small and staying on
        // CPU is faster than swapping the model across backends.
        if (reuse == 0 && prefill_tokens >= GPU_PREFILL_MIN_TOKENS) {
            decodeError = gpu_prefill_then_cpu_locked(tokens, gpu_compute_us, handoff_us, state_bytes);
            if (decodeError.empty()) {
                used_gpu_prefill = true;
            } else {
                LOGW("GPU prefill unavailable; falling back to CPU: %s", decodeError.c_str());
                const std::string recover = load_phase_runtime_locked(g_model_path, g_context_size, 0, true);
                if (!recover.empty()) {
                    g_cached_tokens.clear();
                    return error_string(env, "GPU prefill failed and CPU recovery failed: " + recover);
                }
                llama_memory_clear(llama_get_memory(g_ctx), false);
                decodeError = decode_prompt(tokens, 0);
            }
        } else {
            decodeError = decode_prompt(tokens, reuse);
        }

        g_prefill_us = std::max<int64_t>(1, now_us() - prefill_started);
        if (!decodeError.empty()) {
            g_cached_tokens.clear();
            return error_string(env, decodeError);
        }
        g_cached_tokens = tokens;
        g_decode_started_us = now_us();
'''
    text, count = prefill_pattern.subn(lambda _: prefill_replacement, text, count=1)
    if count != 1:
        raise RuntimeError("anchor not found: nativeBegin prefill block")

    old_log = '''        const double prefill_tps = prefill_tokens * 1000000.0 / static_cast<double>(g_prefill_us);\n        const double cache_pct = tokenized > 0 ? (100.0 * reuse / static_cast<double>(tokenized)) : 0.0;\n        LOGI(\n            "generation begun totalPrompt=%d prefillTokens=%d cachedPrefix=%zu cacheHit=%.1f%% maxTokens=%d thinking=%s prefill=%.2f tok/s backend=%s",\n            tokenized,\n            prefill_tokens,\n            reuse,\n            cache_pct,\n            g_max_tokens,\n            enableThinking == JNI_TRUE ? "true" : "false",\n            prefill_tps,\n            g_backend_label.c_str()\n        );\n'''
    new_log = '''        const double prefill_tps = prefill_tokens * 1000000.0 / static_cast<double>(g_prefill_us);\n        const double cache_pct = tokenized > 0 ? (100.0 * reuse / static_cast<double>(tokenized)) : 0.0;\n        const double gpu_compute_tps = used_gpu_prefill && gpu_compute_us > 0\n            ? prefill_tokens * 1000000.0 / static_cast<double>(gpu_compute_us)\n            : 0.0;\n        LOGI(\n            "generation begun totalPrompt=%d prefillTokens=%d cachedPrefix=%zu cacheHit=%.1f%% maxTokens=%d thinking=%s prefillMode=%s effectivePrefill=%.2f tok/s gpuCompute=%.2f tok/s handoffMs=%.1f stateMiB=%.1f decodeBackend=%s",\n            tokenized,\n            prefill_tokens,\n            reuse,\n            cache_pct,\n            g_max_tokens,\n            enableThinking == JNI_TRUE ? "true" : "false",\n            used_gpu_prefill ? "GPU->CPU" : "CPU",\n            prefill_tps,\n            gpu_compute_tps,\n            handoff_us / 1000.0,\n            state_bytes / (1024.0 * 1024.0),\n            g_backend_label.c_str()\n        );\n'''
    text = replace_once(text, old_log, new_log, "GPU prefill telemetry log")

    PATH.write_text(text, encoding="utf-8")
    print("Applied GPU_PREFILL_V025: OpenCL cold long-prefill -> portable KV state -> CPU decode")


if __name__ == "__main__":
    main()
