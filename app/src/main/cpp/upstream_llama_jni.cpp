#include <jni.h>
#include <android/log.h>
#include <atomic>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <mutex>
#include <string>
#include <vector>

#include "llama.h"
#include "chat.h"

#define TAG "JinkakuLlama"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)
#define LOGW(...) __android_log_print(ANDROID_LOG_WARN, TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, TAG, __VA_ARGS__)

namespace {
std::mutex g_mutex;
std::atomic_bool g_stop{false};
bool g_backend_initialized = false;

// Main E4B chat runtime.
llama_model * g_model = nullptr;
llama_context * g_ctx = nullptr;
const llama_vocab * g_vocab = nullptr;
llama_sampler * g_sampler = nullptr;
common_chat_templates_ptr g_chat_templates;
int32_t g_position = 0;
int32_t g_generated = 0;
int32_t g_prompt_tokens = 0;
int32_t g_max_tokens = 0;
int32_t g_context_size = 0;
int64_t g_prefill_us = 0;
int64_t g_decode_started_us = 0;

// Separate EmbeddingGemma runtime. Keeping it separate prevents memory lookup
// from clearing or otherwise mutating the E4B chat context.
llama_model * g_emb_model = nullptr;
llama_context * g_emb_ctx = nullptr;
const llama_vocab * g_emb_vocab = nullptr;
int32_t g_emb_context_size = 0;

int64_t now_us() {
    return std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

void ensure_backend_initialized() {
    if (g_backend_initialized) return;
    llama_log_set([](enum ggml_log_level level, const char * text, void *) {
        if (level >= GGML_LOG_LEVEL_ERROR) LOGE("%s", text);
        else if (level == GGML_LOG_LEVEL_WARN) LOGW("%s", text);
    }, nullptr);
    llama_backend_init();
    g_backend_initialized = true;
    LOGI("upstream llama.cpp backend initialized");
}

void append_utf8(std::string & out, uint32_t cp) {
    if (cp <= 0x7F) {
        out.push_back(static_cast<char>(cp));
    } else if (cp <= 0x7FF) {
        out.push_back(static_cast<char>(0xC0 | (cp >> 6)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else if (cp <= 0xFFFF) {
        out.push_back(static_cast<char>(0xE0 | (cp >> 12)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    } else {
        out.push_back(static_cast<char>(0xF0 | (cp >> 18)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 12) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | ((cp >> 6) & 0x3F)));
        out.push_back(static_cast<char>(0x80 | (cp & 0x3F)));
    }
}

std::string from_jstring(JNIEnv * env, jstring value) {
    if (value == nullptr) return {};
    const jsize len = env->GetStringLength(value);
    const jchar * chars = env->GetStringChars(value, nullptr);
    if (!chars) return {};
    std::string out;
    out.reserve(static_cast<size_t>(len) * 3);
    for (jsize i = 0; i < len; ++i) {
        uint32_t cp = chars[i];
        if (cp >= 0xD800 && cp <= 0xDBFF && i + 1 < len) {
            const uint32_t low = chars[i + 1];
            if (low >= 0xDC00 && low <= 0xDFFF) {
                cp = 0x10000 + ((cp - 0xD800) << 10) + (low - 0xDC00);
                ++i;
            }
        }
        append_utf8(out, cp);
    }
    env->ReleaseStringChars(value, chars);
    return out;
}

jstring error_string(JNIEnv * env, const std::string & message) {
    return env->NewStringUTF(message.c_str());
}

void free_model_locked() {
    g_stop.store(true, std::memory_order_relaxed);
    if (g_sampler) {
        llama_sampler_free(g_sampler);
        g_sampler = nullptr;
    }
    g_chat_templates.reset();
    if (g_ctx) {
        llama_free(g_ctx);
        g_ctx = nullptr;
    }
    if (g_model) {
        llama_model_free(g_model);
        g_model = nullptr;
    }
    g_vocab = nullptr;
    g_position = 0;
    g_generated = 0;
    g_prompt_tokens = 0;
    g_max_tokens = 0;
    g_context_size = 0;
    g_prefill_us = 0;
    g_decode_started_us = 0;
}

void free_embedding_locked() {
    if (g_emb_ctx) {
        llama_free(g_emb_ctx);
        g_emb_ctx = nullptr;
    }
    if (g_emb_model) {
        llama_model_free(g_emb_model);
        g_emb_model = nullptr;
    }
    g_emb_vocab = nullptr;
    g_emb_context_size = 0;
}

bool add_batch_token(llama_batch & batch, llama_token token, llama_pos pos, bool logits) {
    const int i = batch.n_tokens;
    batch.token[i] = token;
    batch.pos[i] = pos;
    batch.n_seq_id[i] = 1;
    batch.seq_id[i][0] = 0;
    batch.logits[i] = logits ? 1 : 0;
    batch.n_tokens++;
    return true;
}

std::string decode_prompt(const std::vector<llama_token> & tokens) {
    constexpr int BATCH = 256;
    llama_batch batch = llama_batch_init(BATCH, 0, 1);
    if (!batch.token || !batch.pos || !batch.n_seq_id || !batch.seq_id || !batch.logits) {
        llama_batch_free(batch);
        return "llama_batch_init failed";
    }

    g_position = 0;
    for (size_t offset = 0; offset < tokens.size(); offset += BATCH) {
        batch.n_tokens = 0;
        const size_t end = std::min(tokens.size(), offset + BATCH);
        for (size_t i = offset; i < end; ++i) {
            const bool want_logits = (i + 1 == tokens.size());
            add_batch_token(batch, tokens[i], static_cast<llama_pos>(i), want_logits);
        }
        const int rc = llama_decode(g_ctx, batch);
        if (rc != 0) {
            llama_batch_free(batch);
            return "llama_decode(prompt) failed rc=" + std::to_string(rc);
        }
        g_position = static_cast<int32_t>(end);
    }
    llama_batch_free(batch);
    return {};
}

std::string token_piece(llama_token token) {
    int needed = llama_token_to_piece(g_vocab, token, nullptr, 0, 0, true);
    if (needed == 0) return {};
    if (needed > 0) {
        std::vector<char> buf(static_cast<size_t>(needed));
        const int written = llama_token_to_piece(g_vocab, token, buf.data(), static_cast<int32_t>(buf.size()), 0, true);
        return written > 0 ? std::string(buf.data(), static_cast<size_t>(written)) : std::string();
    }
    needed = -needed;
    std::vector<char> buf(static_cast<size_t>(needed));
    const int written = llama_token_to_piece(g_vocab, token, buf.data(), static_cast<int32_t>(buf.size()), 0, true);
    return written > 0 ? std::string(buf.data(), static_cast<size_t>(written)) : std::string();
}

jbyteArray to_byte_array(JNIEnv * env, const std::string & value) {
    auto arr = env->NewByteArray(static_cast<jsize>(value.size()));
    if (!arr) return nullptr;
    if (!value.empty()) {
        env->SetByteArrayRegion(arr, 0, static_cast<jsize>(value.size()), reinterpret_cast<const jbyte *>(value.data()));
    }
    return arr;
}

jfloatArray to_float_array(JNIEnv * env, const float * values, int32_t size) {
    if (!values || size <= 0) return nullptr;
    std::vector<float> normalized(static_cast<size_t>(size));
    double norm2 = 0.0;
    for (int32_t i = 0; i < size; ++i) norm2 += static_cast<double>(values[i]) * values[i];
    const double norm = std::sqrt(norm2);
    const float scale = norm > 0.0 ? static_cast<float>(1.0 / norm) : 1.0f;
    for (int32_t i = 0; i < size; ++i) normalized[static_cast<size_t>(i)] = values[i] * scale;
    jfloatArray result = env->NewFloatArray(size);
    if (!result) return nullptr;
    env->SetFloatArrayRegion(result, 0, size, normalized.data());
    return result;
}
} // namespace

extern "C" JNIEXPORT jstring JNICALL
Java_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeInit(JNIEnv * env, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    try {
        ensure_backend_initialized();
        return nullptr;
    } catch (const std::exception & e) {
        return error_string(env, e.what());
    }
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeLoad(JNIEnv * env, jobject, jstring modelPath, jint contextSize) {
    std::lock_guard<std::mutex> lock(g_mutex);
    try {
        ensure_backend_initialized();
        free_model_locked();
        const std::string path = from_jstring(env, modelPath);
        if (path.empty()) return error_string(env, "empty model path");

        llama_model_params mparams = llama_model_default_params();
        mparams.n_gpu_layers = 0;

        g_model = llama_model_load_from_file(path.c_str(), mparams);
        if (!g_model) return error_string(env, "llama_model_load_from_file returned null");
        g_vocab = llama_model_get_vocab(g_model);
        if (!g_vocab) {
            free_model_locked();
            return error_string(env, "llama_model_get_vocab returned null");
        }

        const int32_t ctx = std::clamp(static_cast<int32_t>(contextSize), 1024, 8192);
        llama_context_params cparams = llama_context_default_params();
        cparams.n_ctx = static_cast<uint32_t>(ctx);
        cparams.n_batch = 256;
        cparams.n_ubatch = 128;
        cparams.n_threads = 6;
        cparams.n_threads_batch = 6;

        g_ctx = llama_init_from_model(g_model, cparams);
        if (!g_ctx) {
            free_model_locked();
            return error_string(env, "llama_init_from_model returned null");
        }
        g_context_size = ctx;

        g_chat_templates = common_chat_templates_init(g_model, "");
        if (!g_chat_templates) {
            free_model_locked();
            return error_string(env, "common_chat_templates_init returned null");
        }

        llama_sampler_chain_params chainParams = llama_sampler_chain_default_params();
        g_sampler = llama_sampler_chain_init(chainParams);
        if (!g_sampler) {
            free_model_locked();
            return error_string(env, "llama_sampler_chain_init returned null");
        }
        llama_sampler_chain_add(g_sampler, llama_sampler_init_top_k(64));
        llama_sampler_chain_add(g_sampler, llama_sampler_init_top_p(0.95f, 1));
        llama_sampler_chain_add(g_sampler, llama_sampler_init_temp(1.0f));
        llama_sampler_chain_add(g_sampler, llama_sampler_init_dist(LLAMA_DEFAULT_SEED));

        g_stop.store(false, std::memory_order_relaxed);
        LOGI("model loaded with upstream llama.cpp ctx=%d threads=6 ubatch=128 backend=CPU", ctx);
        return nullptr;
    } catch (const std::exception & e) {
        free_model_locked();
        return error_string(env, std::string("native load exception: ") + e.what());
    } catch (...) {
        free_model_locked();
        return error_string(env, "native load unknown exception");
    }
}

extern "C" JNIEXPORT jstring JNICALL
Java_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeBegin(
        JNIEnv * env,
        jobject,
        jobjectArray roles,
        jobjectArray contents,
        jint maxTokens) {
    std::lock_guard<std::mutex> lock(g_mutex);
    try {
        if (!g_model || !g_ctx || !g_vocab || !g_sampler || !g_chat_templates) {
            return error_string(env, "model is not loaded");
        }
        const jsize roleCount = env->GetArrayLength(roles);
        const jsize contentCount = env->GetArrayLength(contents);
        if (roleCount != contentCount || roleCount <= 0) {
            return error_string(env, "invalid chat arrays");
        }

        common_chat_templates_inputs inputs;
        inputs.use_jinja = true;
        inputs.add_generation_prompt = true;
        inputs.enable_thinking = true;
        inputs.messages.reserve(static_cast<size_t>(roleCount));

        for (jsize i = 0; i < roleCount; ++i) {
            auto jrole = static_cast<jstring>(env->GetObjectArrayElement(roles, i));
            auto jcontent = static_cast<jstring>(env->GetObjectArrayElement(contents, i));
            common_chat_msg msg;
            msg.role = from_jstring(env, jrole);
            msg.content = from_jstring(env, jcontent);
            inputs.messages.push_back(std::move(msg));
            env->DeleteLocalRef(jrole);
            env->DeleteLocalRef(jcontent);
        }

        const auto rendered = common_chat_templates_apply(g_chat_templates.get(), inputs);
        const std::string & prompt = rendered.prompt;
        if (prompt.empty()) return error_string(env, "Jinja rendered an empty prompt");

        const int neededRaw = llama_tokenize(g_vocab, prompt.data(), static_cast<int32_t>(prompt.size()), nullptr, 0, true, true);
        const int needed = neededRaw < 0 ? -neededRaw : neededRaw;
        if (needed <= 0) return error_string(env, "prompt tokenization returned no tokens");
        if (needed >= g_context_size - 8) {
            return error_string(env, "prompt is too large for the active context: " + std::to_string(needed) + "/" + std::to_string(g_context_size));
        }

        std::vector<llama_token> tokens(static_cast<size_t>(needed));
        const int tokenized = llama_tokenize(g_vocab, prompt.data(), static_cast<int32_t>(prompt.size()), tokens.data(), static_cast<int32_t>(tokens.size()), true, true);
        if (tokenized < 0) return error_string(env, "prompt tokenization failed");
        tokens.resize(static_cast<size_t>(tokenized));

        llama_memory_clear(llama_get_memory(g_ctx), false);
        llama_sampler_reset(g_sampler);
        g_stop.store(false, std::memory_order_relaxed);
        g_generated = 0;
        g_prompt_tokens = tokenized;
        g_prefill_us = 0;
        g_decode_started_us = 0;
        const int32_t available = std::max(16, g_context_size - tokenized - 4);
        g_max_tokens = std::min(std::clamp(static_cast<int32_t>(maxTokens), 16, 1536), available);

        const int64_t prefill_started = now_us();
        const std::string decodeError = decode_prompt(tokens);
        g_prefill_us = std::max<int64_t>(1, now_us() - prefill_started);
        if (!decodeError.empty()) return error_string(env, decodeError);
        g_decode_started_us = now_us();

        const double prefill_tps = tokenized * 1000000.0 / static_cast<double>(g_prefill_us);
        LOGI("generation begun promptTokens=%d maxTokens=%d thinking=true prefill=%.2f tok/s", tokenized, g_max_tokens, prefill_tps);
        return nullptr;
    } catch (const std::exception & e) {
        return error_string(env, std::string("native begin exception: ") + e.what());
    } catch (...) {
        return error_string(env, "native begin unknown exception");
    }
}

extern "C" JNIEXPORT jbyteArray JNICALL
Java_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeNext(JNIEnv * env, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_model || !g_ctx || !g_vocab || !g_sampler) return nullptr;
    if (g_stop.load(std::memory_order_relaxed) || g_generated >= g_max_tokens) return nullptr;
    if (g_position >= g_context_size - 1) return nullptr;

    try {
        const llama_token token = llama_sampler_sample(g_sampler, g_ctx, -1);
        llama_sampler_accept(g_sampler, token);
        if (llama_vocab_is_eog(g_vocab, token)) return nullptr;

        const std::string piece = token_piece(token);
        llama_batch batch = llama_batch_init(1, 0, 1);
        if (!batch.token) {
            llama_batch_free(batch);
            g_stop.store(true, std::memory_order_relaxed);
            return nullptr;
        }
        batch.n_tokens = 0;
        add_batch_token(batch, token, g_position, true);
        const int rc = llama_decode(g_ctx, batch);
        llama_batch_free(batch);
        if (rc != 0) {
            LOGE("llama_decode(token) failed rc=%d", rc);
            g_stop.store(true, std::memory_order_relaxed);
            return nullptr;
        }
        ++g_position;
        ++g_generated;
        return to_byte_array(env, piece);
    } catch (const std::exception & e) {
        LOGE("nativeNext exception: %s", e.what());
        g_stop.store(true, std::memory_order_relaxed);
        return nullptr;
    } catch (...) {
        LOGE("nativeNext unknown exception");
        g_stop.store(true, std::memory_order_relaxed);
        return nullptr;
    }
}

extern "C" JNIEXPORT jlongArray JNICALL
Java_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeStats(JNIEnv * env, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    const int64_t decode_us = g_decode_started_us > 0
        ? std::max<int64_t>(0, now_us() - g_decode_started_us)
        : 0;
    const jlong values[7] = {
        static_cast<jlong>(g_prompt_tokens),
        static_cast<jlong>(g_generated),
        static_cast<jlong>(g_context_size),
        static_cast<jlong>(g_position),
        static_cast<jlong>(g_prefill_us),
        static_cast<jlong>(decode_us),
        static_cast<jlong>(g_max_tokens)
    };
    jlongArray result = env->NewLongArray(7);
    if (!result) return nullptr;
    env->SetLongArrayRegion(result, 0, 7, values);
    return result;
}

extern "C" JNIEXPORT void JNICALL
Java_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeStop(JNIEnv *, jobject) {
    g_stop.store(true, std::memory_order_relaxed);
}

extern "C" JNIEXPORT void JNICALL
Java_com_ikegami99_jinkaku_ai_UpstreamLlamaBridge_nativeUnload(JNIEnv *, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    free_model_locked();
    LOGI("model unloaded");
}

// -----------------------------------------------------------------------------
// EmbeddingGemma JNI
// -----------------------------------------------------------------------------
extern "C" JNIEXPORT jstring JNICALL
Java_com_ikegami99_jinkaku_ai_EmbeddingGemmaBridge_nativeEmbeddingLoad(
        JNIEnv * env, jobject, jstring modelPath) {
    std::lock_guard<std::mutex> lock(g_mutex);
    try {
        ensure_backend_initialized();
        free_embedding_locked();
        const std::string path = from_jstring(env, modelPath);
        if (path.empty()) return error_string(env, "empty embedding model path");

        llama_model_params mparams = llama_model_default_params();
        mparams.n_gpu_layers = 0;
        g_emb_model = llama_model_load_from_file(path.c_str(), mparams);
        if (!g_emb_model) return error_string(env, "embedding llama_model_load_from_file returned null");
        g_emb_vocab = llama_model_get_vocab(g_emb_model);
        if (!g_emb_vocab) {
            free_embedding_locked();
            return error_string(env, "embedding llama_model_get_vocab returned null");
        }

        llama_context_params cparams = llama_context_default_params();
        cparams.n_ctx = 1024;
        cparams.n_batch = 1024;
        cparams.n_ubatch = 1024;
        cparams.n_threads = 4;
        cparams.n_threads_batch = 4;
        cparams.embeddings = true;
        cparams.pooling_type = LLAMA_POOLING_TYPE_UNSPECIFIED;
        cparams.attention_type = LLAMA_ATTENTION_TYPE_UNSPECIFIED;

        g_emb_ctx = llama_init_from_model(g_emb_model, cparams);
        if (!g_emb_ctx) {
            free_embedding_locked();
            return error_string(env, "embedding llama_init_from_model returned null");
        }
        g_emb_context_size = 1024;
        LOGI("EmbeddingGemma loaded ctx=1024 backend=CPU dim=%d pooling=%d",
             llama_model_n_embd_out(g_emb_model), static_cast<int>(llama_pooling_type(g_emb_ctx)));
        return nullptr;
    } catch (const std::exception & e) {
        free_embedding_locked();
        return error_string(env, std::string("embedding load exception: ") + e.what());
    } catch (...) {
        free_embedding_locked();
        return error_string(env, "embedding load unknown exception");
    }
}

extern "C" JNIEXPORT jfloatArray JNICALL
Java_com_ikegami99_jinkaku_ai_EmbeddingGemmaBridge_nativeEmbeddingEncode(
        JNIEnv * env, jobject, jstring inputText) {
    std::lock_guard<std::mutex> lock(g_mutex);
    if (!g_emb_model || !g_emb_ctx || !g_emb_vocab) return nullptr;
    try {
        const std::string text = from_jstring(env, inputText);
        if (text.empty()) return nullptr;

        const int neededRaw = llama_tokenize(
            g_emb_vocab, text.data(), static_cast<int32_t>(text.size()), nullptr, 0, true, true);
        const int needed = neededRaw < 0 ? -neededRaw : neededRaw;
        if (needed <= 0 || needed > g_emb_context_size) {
            LOGE("EmbeddingGemma token count invalid: %d/%d", needed, g_emb_context_size);
            return nullptr;
        }

        std::vector<llama_token> tokens(static_cast<size_t>(needed));
        const int tokenized = llama_tokenize(
            g_emb_vocab, text.data(), static_cast<int32_t>(text.size()), tokens.data(),
            static_cast<int32_t>(tokens.size()), true, true);
        if (tokenized <= 0) return nullptr;
        tokens.resize(static_cast<size_t>(tokenized));

        llama_memory_clear(llama_get_memory(g_emb_ctx), true);
        llama_batch batch = llama_batch_init(tokenized, 0, 1);
        if (!batch.token || !batch.pos || !batch.n_seq_id || !batch.seq_id || !batch.logits) {
            llama_batch_free(batch);
            return nullptr;
        }
        batch.n_tokens = 0;
        for (int i = 0; i < tokenized; ++i) {
            add_batch_token(batch, tokens[static_cast<size_t>(i)], static_cast<llama_pos>(i), true);
        }

        const int64_t started = now_us();
        const int rc = llama_decode(g_emb_ctx, batch);
        llama_batch_free(batch);
        if (rc != 0) {
            LOGE("EmbeddingGemma llama_decode failed rc=%d", rc);
            return nullptr;
        }

        const float * emb = llama_get_embeddings_seq(g_emb_ctx, 0);
        if (!emb) emb = llama_get_embeddings_ith(g_emb_ctx, -1);
        const int32_t dim = llama_model_n_embd_out(g_emb_model);
        if (!emb || dim <= 0) {
            LOGE("EmbeddingGemma output missing dim=%d", dim);
            return nullptr;
        }
        const double elapsed_ms = (now_us() - started) / 1000.0;
        LOGI("EmbeddingGemma encoded tokens=%d dim=%d elapsed=%.1fms", tokenized, dim, elapsed_ms);
        return to_float_array(env, emb, dim);
    } catch (const std::exception & e) {
        LOGE("EmbeddingGemma encode exception: %s", e.what());
        return nullptr;
    } catch (...) {
        LOGE("EmbeddingGemma encode unknown exception");
        return nullptr;
    }
}

extern "C" JNIEXPORT void JNICALL
Java_com_ikegami99_jinkaku_ai_EmbeddingGemmaBridge_nativeEmbeddingUnload(JNIEnv *, jobject) {
    std::lock_guard<std::mutex> lock(g_mutex);
    free_embedding_locked();
    LOGI("EmbeddingGemma unloaded");
}