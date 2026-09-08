package com.ikegami99.jinkaku.ai

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlin.math.roundToInt

data class InferenceTelemetryState(
    val phase: String = "IDLE",
    val prefillTokPerSec: Double = 0.0,
    val decodeTokPerSec: Double = 0.0,
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

    fun prefillLabel(): String = if (prefillTokPerSec > 0.0) "%.1f".format(prefillTokPerSec) else "--"
    fun decodeLabel(): String = if (decodeTokPerSec > 0.0) "%.1f".format(decodeTokPerSec) else "--"
}

object InferenceTelemetry {
    private val _state = MutableStateFlow(InferenceTelemetryState())
    val state: StateFlow<InferenceTelemetryState> = _state.asStateFlow()

    fun reset(contextMax: Int, phase: String = "LOADING") {
        _state.value = InferenceTelemetryState(
            phase = phase,
            contextMax = contextMax,
            backend = "CPU"
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

    fun complete(native: NativeInferenceStats, finalText: String) {
        update(native, "DONE")
        _state.value = _state.value.copy(finalTextHash = finalText.hashCode())
    }

    fun stopped() {
        _state.value = _state.value.copy(phase = "STOPPED")
    }
}
