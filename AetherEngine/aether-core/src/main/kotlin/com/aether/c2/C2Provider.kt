package com.aether.c2

/**
 * Raw transport boundary (LC0). No policy here — policy lives in license/.
 * C1 provides the real transport (mock/replay/live); flags OFF wires NoOp.
 */
interface C2Provider {
    fun isAvailable(): Boolean
    fun request(path: String, body: ByteArray): ByteArray?
}

/** Disabled-module stand-in: no transport, every request returns null. */
object NoOpC2Provider : C2Provider {
    override fun isAvailable(): Boolean = false
    override fun request(path: String, body: ByteArray): ByteArray? = null
}
