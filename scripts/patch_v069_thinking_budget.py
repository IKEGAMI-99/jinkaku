from pathlib import Path

ROOT = Path('app/src/main')
NATIVE = ROOT / 'cpp/upstream_llama_jni.cpp'
ENGINE = ROOT / 'java/com/ikegami99/jinkaku/ai/E4BEngine.kt'
BRIDGE = ROOT / 'java/com/ikegami99/jinkaku/ai/UpstreamLlamaBridge.kt'
UI = ROOT / 'java/com/ikegami99/jinkaku/ui/ModernJinkakuApp.kt'


def one(text, old, new):
    if text.count(old) != 1:
        raise RuntimeError(f'v069 expected exactly one anchor: {old[:100]!r}')
    return text.replace(old, new, 1)


def patch_native():
    text = NATIVE.read_text()
    if 'SEPARATE_BUDGET_V069' in text:
        return
    text = one(text, '#include "llama.h"', '#include "generation_budget.h"\n#include "llama.h"')
    text = one(text, 'int32_t g_max_tokens = 0;', '''int32_t g_max_tokens = 0;
// SEPARATE_BUDGET_V069
GenerationBudget g_budget;
std::string g_initial_thought;
std::string g_finish_reason;
int32_t g_cached_prompt_count = 0;''')
    text = one(text,
        '        g_max_tokens = std::min(std::clamp(static_cast<int32_t>(maxTokens), 16, 1536), available);',
        '''        const int answer_budget = std::clamp(static_cast<int>(maxTokens), 32, 1024);
        // Reserve the full answer plus space for a forced channel delimiter.
        if (available < answer_budget + 16) {
            g_cached_tokens.clear();
            return error_string(env, "Context has insufficient room for the answer budget; start a new chat or increase Context");
        }
        const int thought_budget = enableThinking == JNI_TRUE
            ? std::min(512, available - answer_budget - 16) : 0;
        g_budget.reset(enableThinking == JNI_TRUE, answer_budget, thought_budget);
        g_budget.seed_prompt(prompt);
        g_initial_thought = g_budget.in_thought() ? g_budget.opener : "";
        g_finish_reason = "running";
        g_cached_prompt_count = static_cast<int32_t>(reuse);
        g_max_tokens = answer_budget + thought_budget;
        LOGI("budgets thought=%d answer=%d cachedPrompt=%d", thought_budget, answer_budget, g_cached_prompt_count);''')
    start = text.index('extern "C" JNIEXPORT jbyteArray JNICALL\nJava_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeNext')
    end = text.index('extern "C" JNIEXPORT jlongArray JNICALL', start)
    text = text[:start] + r'''
// Decode a forced channel delimiter in the existing KV context. Never restart
// the prompt or discard the thoughts that the model has already computed.
static jbyteArray force_final_v069(JNIEnv * env) {
    if (g_budget.opener.empty()) {
        throw std::runtime_error("Thinking ended without a recognized channel marker");
    }
    const std::string marker = g_budget.closer();
    const int raw = llama_tokenize(g_vocab, marker.data(), marker.size(), nullptr, 0, false, true);
    const int count = raw < 0 ? -raw : raw;
    if (count <= 0 || count > 16 || g_position + count + g_budget.answer_limit >= g_context_size) {
        throw std::runtime_error("Insufficient context for Thinking-to-answer transition");
    }
    std::vector<llama_token> tokens(count);
    const int n = llama_tokenize(g_vocab, marker.data(), marker.size(), tokens.data(), count, false, true);
    if (n <= 0) throw std::runtime_error("Thinking delimiter tokenization failed");
    llama_batch batch = llama_batch_init(n, 0, 1);
    if (!batch.token || !batch.pos || !batch.n_seq_id || !batch.seq_id || !batch.logits) {
        llama_batch_free(batch);
        throw std::runtime_error("Thinking delimiter batch allocation failed");
    }
    batch.n_tokens = 0;
    for (int i = 0; i < n; ++i) add_batch_token(batch, tokens[i], g_position + i, i == n - 1);
    const int rc = llama_decode(g_ctx, batch);
    llama_batch_free(batch);
    if (rc != 0) throw std::runtime_error("Thinking delimiter decode failed rc=" + std::to_string(rc));
    for (int i = 0; i < n; ++i) llama_sampler_accept(g_sampler, tokens[i]);
    g_position += n;
    g_budget.force_final();
    LOGI("Thinking budget reached; continued in same KV context, answerBudget=%d", g_budget.answer_limit);
    // Let the Kotlin filter consume the same boundary, without displaying it.
    return to_byte_array(env, marker);
}

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeNext(JNIEnv * env, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_model || !g_ctx || !g_vocab || !g_sampler) return nullptr;
    if (g_stop.load(std::memory_order_relaxed)) { g_finish_reason = "cancelled"; return nullptr; }
    if (g_budget.done()) { g_finish_reason = "answer_limit"; return nullptr; }
    if (g_position >= g_context_size - 1) { g_finish_reason = "context_limit"; return nullptr; }
    try {
        if (g_budget.needs_final()) return force_final_v069(env);
        const llama_token token = llama_sampler_sample(g_sampler, g_ctx, -1);
        if (llama_vocab_is_eog(g_vocab, token)) {
            if (g_budget.in_thought()) return force_final_v069(env);
            g_finish_reason = "eos";
            return nullptr;
        }
        llama_sampler_accept(g_sampler, token);
        const std::string piece = token_piece(token);
        llama_batch batch = llama_batch_init(1, 0, 1);
        if (!batch.token || !batch.pos || !batch.n_seq_id || !batch.seq_id || !batch.logits) {
            llama_batch_free(batch);
            throw std::runtime_error("Token batch allocation failed");
        }
        batch.n_tokens = 0;
        add_batch_token(batch, token, g_position, true);
        const int rc = llama_decode(g_ctx, batch);
        llama_batch_free(batch);
        if (rc != 0) throw std::runtime_error("Token decode failed rc=" + std::to_string(rc));
        ++g_position;
        ++g_generated;
        g_budget.observe(piece);
        return to_byte_array(env, piece);
    } catch (const std::exception & e) {
        g_stop.store(true, std::memory_order_relaxed);
        g_finish_reason = "native_error";
        LOGE("nativeNext: %s", e.what());
        env->ThrowNew(env->FindClass("java/lang/IllegalStateException"), e.what());
        return nullptr;
    } catch (...) {
        g_stop.store(true, std::memory_order_relaxed);
        g_finish_reason = "native_error";
        env->ThrowNew(env->FindClass("java/lang/IllegalStateException"), "Unknown native generation failure");
        return nullptr;
    }
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeInitialThought(JNIEnv * env, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    return env->NewStringUTF(g_initial_thought.c_str());
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeGenerationDetails(JNIEnv * env, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    const std::string details = "finishReason=" + g_finish_reason +
        " thoughtTokens=" + std::to_string(g_budget.thought) +
        " answerTokens=" + std::to_string(g_budget.answer) +
        " thoughtBudget=" + std::to_string(g_budget.thought_limit) +
        " answerBudget=" + std::to_string(g_budget.answer_limit) +
        " forcedFinal=" + (g_budget.forced ? "true" : "false") +
        " cachedPromptTokens=" + std::to_string(g_cached_prompt_count);
    return env->NewStringUTF(details.c_str());
}

''' + text[end:]
    text = one(text, '#include <mutex>', '#include <mutex>\n#include <stdexcept>')
    NATIVE.write_text(text)


def patch_kotlin():
    text = BRIDGE.read_text()
    if 'SEPARATE_BUDGET_V069' not in text:
        text = one(text, '    fun nextTokenBytes(): ByteArray? = nativeNext()', '''    // SEPARATE_BUDGET_V069
    fun initialThought(): String = nativeInitialThought()
    fun generationDetails(): String = nativeGenerationDetails()
    private external fun nativeInitialThought(): String
    private external fun nativeGenerationDetails(): String

    fun nextTokenBytes(): ByteArray? = nativeNext()''')
        BRIDGE.write_text(text)
    text = ENGINE.read_text()
    if 'SEPARATE_BUDGET_V069' not in text:
        text = one(text, '        var nativeStats = bridge.stats()', '''        // SEPARATE_BUDGET_V069: align filtering with Jinja-prefilled thought markers.
        filter.accept(bridge.initialThought())
        var nativeStats = bridge.stats()''')
        text = one(text, '        nativeStats = bridge.stats()\n        InferenceTelemetry.complete(nativeStats, cleaned)', '''        nativeStats = bridge.stats()
        logger.i("E4B", "Generation budgets ${bridge.generationDetails()}")
        check(cleaned.isNotBlank()) {
            "回答本文が空のまま終了しました。ThinkingをOFFにして再試行してください。"
        }
        InferenceTelemetry.complete(nativeStats, cleaned)''')
        ENGINE.write_text(text)
    text = UI.read_text()
    if 'SEPARATE_BUDGET_V069' not in text:
        text = one(text, '                    val replyLengthHint = when (ui.replyLengthMode) {', '''                    // SEPARATE_BUDGET_V069
                    Text("Thinkingは別枠で最大512 token。返信の長さは回答本文だけに適用します。Context残量が少ない場合はThinking枠を縮めます。", style = MaterialTheme.typography.bodySmall)
                    val replyLengthHint = when (ui.replyLengthMode) {''')
        UI.write_text(text)


if __name__ == '__main__':
    patch_native()
    patch_kotlin()
    print('Applied SEPARATE_BUDGET_V069: independent Thinking/answer budgets, same-KV final transition, finish diagnostics')
