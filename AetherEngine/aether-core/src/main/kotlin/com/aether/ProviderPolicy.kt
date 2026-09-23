package com.aether

/**
 * G2 (P1 batch 3): per-provider install policy — allow-list with experiment flags.
 *
 * Evidence: guest manifest provider inventory (package.conf, eightballpool
 * 56.23.2 → 13 providers) + device proof (apk 0955c54 round P4:
 * FirebaseInitProvider → m7.* dynamite SE on main-looper → silent exit(0)).
 *
 * Default = today's behavior EXACTLY (safe: game reaches onResume). Every SKIP
 * names the flag that re-opens it — device P4 flips ONE flag per run and
 * logcat shows GATED-TRY / GATED-OK / FAIL per provider.
 * Experiment order: PlayGames → Firebase-retest → gms.ads → ads.
 */
enum class ProviderDisposition {
    /** install, normal logging */
    ALLOW,
    /** install + experiment telemetry (future: worker-thread install hook) */
    GATED,
    /** do not install; reason recorded in skippedProviders */
    SKIP,
}

/** Kill-switches + per-class overrides (default OFF = today's behavior). */
object ProviderFlags {
    @Volatile var retestFirebaseProvider: Boolean = false
    @Volatile var allowPlayGamesProvider: Boolean = false
    @Volatile var allowGmsAdsProvider: Boolean = false
    @Volatile var allowAdsProviders: Boolean = false
    private val overrides = java.util.concurrent.ConcurrentHashMap<String, ProviderDisposition>()
    fun overrideFor(providerClass: String): ProviderDisposition? = overrides[providerClass]
    fun setOverride(providerClass: String, d: ProviderDisposition?) {
        if (d == null) overrides.remove(providerClass) else overrides[providerClass] = d
    }
}

object ProviderPolicy {
    const val FIREBASE_INIT = "com.google.firebase.provider.FirebaseInitProvider"
    const val PLAYGAMES_INIT = "com.google.android.gms.games.provider.PlayGamesInitProvider"

    private val adsPrefixes = listOf(
        "io.bidmachine.",
        "com.vungle.",
        "com.ironsource.",
        "com.applovin.",
        "com.facebook.ads.",
    )

    fun policyFor(providerClass: String): Pair<ProviderDisposition, String> {
        ProviderFlags.overrideFor(providerClass)?.let { return it to "manual override" }
        if (providerClass == FIREBASE_INIT) {
            return if (ProviderFlags.retestFirebaseProvider)
                ProviderDisposition.GATED to "flag retestFirebaseProvider=on (P4 experiment)"
            else ProviderDisposition.SKIP to
                "device proof 0955c54/P4: m7.* dynamite SE on main-looper (set retestFirebaseProvider to retry)"
        }
        if (providerClass == PLAYGAMES_INIT) {
            return if (ProviderFlags.allowPlayGamesProvider)
                ProviderDisposition.GATED to "flag allowPlayGamesProvider=on (login-grade experiment #1)"
            else ProviderDisposition.SKIP to
                "login-grade, never attempted (set allowPlayGamesProvider to try)"
        }
        if (providerClass.startsWith("com.google.android.gms.ads")) {
            return if (ProviderFlags.allowGmsAdsProvider)
                ProviderDisposition.GATED to "flag allowGmsAdsProvider=on"
            else ProviderDisposition.SKIP to
                "gms.ads external binder (set allowGmsAdsProvider to try)"
        }
        // NOTE: old "com.google.android.gms.measurement" prefix dropped — guest
        // manifest (package.conf 56.23.2) has NO such provider (AppMeasurement
        // is a service/receiver, not a ContentProvider).
        if (adsPrefixes.any { providerClass.startsWith(it) }) {
            return if (ProviderFlags.allowAdsProviders)
                ProviderDisposition.GATED to "flag allowAdsProviders=on"
            else ProviderDisposition.SKIP to
                "ads provider, not login-grade (set allowAdsProviders to try)"
        }
        return ProviderDisposition.ALLOW to "default allow"
    }
}
