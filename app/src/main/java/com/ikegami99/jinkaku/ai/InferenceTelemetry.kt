package com.ikegami99.jinkaku.ai

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class InferenceTelemetryState(
    val phase: String = "IDLE",
    val prefillTokPerSec: Double = 0.0,
    val decodeTokPerSec: Double = 0.0,
    val ttftSeconds: Double = 0.0,
    val promptTokens: Int = 0,
    val generatedTokens: Int = 0,
    val contextUsed: Int = 0,
    val contextMax: Int = 0,
    val backend: String = "CPU",
    val finalTextHash: Int? = null
) {
    val contextRemaining: Int get() = (contextMax - contextUsed).coerceAtLeast(0)
    val contextFraction: Float
        get() = if (contextMax <= 0) 0f else (contextUsed.toFloat() / contextMax.toFloat()).coerceIn(0f, 1f)

    fun ttftLabel(): String = if (ttftSeconds > 0.0) "%.2f".format(ttftSeconds) else "--"
    fun prefillLabel(): String = if (prefillTokPerSec > 0.0) "%.1f".format(prefillTokPerSec) else "--"
    fun decodeLabel(): String = if (decodeTokPerSec > 0.0) "%.1f".format(decodeTokPerSec) else "--"
}

object InferenceTelemetry {
    private val _state = MutableStateFlow(InferenceTelemetryState())
    val state: StateFlow<InferenceTelemetryState> = _state.asStateFlow()

    fun reset(contextMax: Int, phase: String = "LOADING", backend: String = "CPU") {
        _state.value = InferenceTelemetryState(
            phase = phase,
            contextMax = contextMax,
            backend = backend
        )
    }

    fun phase(value: String) {
        _state.value = _state.value.copy(phase = value)
    }

    fun update(native: NativeInferenceStats, phase: String? = null) {
        val prefill = if (native.prefillMicros > 0L) {
            native.promptTokens * 1_000_000.0 / native.prefillMicros.toDouble()
        } else 0.0
        val decode = if (native.decodeMicros > 0L && native.generatedTokens > 0) {
            native.generatedTokens * 1_000_000.0 / native.decodeMicros.toDouble()
        } else 0.0
        _state.value = _state.value.copy(
            phase = phase ?: _state.value.phase,
            prefillTokPerSec = prefill,
            decodeTokPerSec = decode,
            promptTokens = native.promptTokens,
            generatedTokens = native.generatedTokens,
            contextUsed = native.contextUsed,
            contextMax = native.contextSize,
            backend = native.backend
        )
    }

    /** LiteRT-LM path. getTokenCount() gives the real KV occupancy, while benchmark
     * values are filled in when LiteRT exposes them at the end of the turn. */
    fun updateLiteRt(
        contextUsed: Int,
        contextMax: Int,
        phase: String? = null,
        prefillTokPerSec: Double? = null,
        decodeTokPerSec: Double? = null,
        ttftSeconds: Double? = null,
        promptTokens: Int? = null,
        generatedTokens: Int? = null,
        backend: String = "GPU+MTP"
    ) {
        val old = _state.value
        _state.value = old.copy(
            phase = phase ?: old.phase,
            prefillTokPerSec = prefillTokPerSec ?: old.prefillTokPerSec,
            decodeTokPerSec = decodeTokPerSec ?: old.decodeTokPerSec,
            ttftSeconds = ttftSeconds ?: old.ttftSeconds,
            promptTokens = promptTokens ?: old.promptTokens,
            generatedTokens = generatedTokens ?: old.generatedTokens,
            contextUsed = contextUsed.coerceIn(0, contextMax.coerceAtLeast(0)),
            contextMax = contextMax,
            backend = backend
        )
    }

    fun completeLiteRt(
        finalText: String,
        contextUsed: Int,
        contextMax: Int,
        prefillTokPerSec: Double,
        decodeTokPerSec: Double,
        ttftSeconds: Double,
        generatedTokens: Int,
        backend: String = "GPU+MTP"
    ) {
        val safeGenerated = generatedTokens.coerceAtLeast(0)
        updateLiteRt(
            contextUsed = contextUsed,
            contextMax = contextMax,
            phase = "DONE",
            prefillTokPerSec = prefillTokPerSec,
            decodeTokPerSec = decodeTokPerSec,
            ttftSeconds = ttftSeconds,
            promptTokens = (contextUsed - safeGenerated).coerceAtLeast(0),
            generatedTokens = safeGenerated,
            backend = backend
        )
        _state.value = _state.value.copy(finalTextHash = finalText.hashCode())
    }

    fun complete(native: NativeInferenceStats, finalText: String) {
        update(native, "DONE")
        _state.value = _state.value.copy(finalTextHash = finalText.hashCode())
    }

    fun stopped() {
        _state.value = _state.value.copy(phase = "STOPPED")
    }
}
