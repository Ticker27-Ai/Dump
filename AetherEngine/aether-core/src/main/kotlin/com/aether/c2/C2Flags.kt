package com.aether.c2

/** Transport mode. Default MOCK = no network traffic at all. */
enum class C2Mode { MOCK, REPLAY, LIVE }

/**
 * C2 kill-switches (LC0). Default OFF+MOCK = today's offline behavior.
 * LIVE additionally requires owner sign-off (plan G-LC3) — never default.
 */
object C2Flags {
    @Volatile var enabled: Boolean = false
    @Volatile var mode: C2Mode = C2Mode.MOCK
    @Volatile var provider: C2Provider = NoOpC2Provider
}
