from pathlib import Path

PATH = Path("app/src/main/cpp/upstream_llama_jni.cpp")
text = PATH.read_text(encoding="utf-8")

old = """        const int64_t prefill_started = now_us();\n        bool used_gpu_prefill = false;\n"""
new = """        const int32_t generation_max_tokens = g_max_tokens;\n        const int64_t prefill_started = now_us();\n        bool used_gpu_prefill = false;\n"""
if old not in text:
    raise RuntimeError("v0.1.25 prefill start anchor not found")
text = text.replace(old, new, 1)

old = """        g_prefill_us = std::max<int64_t>(1, now_us() - prefill_started);\n        if (!decodeError.empty()) {\n"""
new = """        // Phase reloads deliberately tear down the temporary model/context,\n        // which resets generation counters. Restore the values for this request\n        // before entering token-by-token CPU decode.\n        g_generated = 0;\n        g_prompt_tokens = prefill_tokens;\n        g_max_tokens = generation_max_tokens;\n        g_stop.store(false, std::memory_order_relaxed);\n        g_prefill_us = std::max<int64_t>(1, now_us() - prefill_started);\n        if (!decodeError.empty()) {\n"""
if old not in text:
    raise RuntimeError("v0.1.25 counter restore anchor not found")
text = text.replace(old, new, 1)

PATH.write_text(text, encoding="utf-8")
print("Fixed v0.1.25 GPU/CPU phase generation counters")
