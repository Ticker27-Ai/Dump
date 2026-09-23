package com.aether.license

/**
 * License policy boundary (LC0). L1 provides the real LicenseManager;
 * flags OFF wires [NoOpLicenseProvider] (offline parity = today's behavior).
 */
interface LicenseProvider {
    fun state(): LicenseState
    fun isEntitled(): Boolean
    fun sellerId(): String?
    fun accessToken(): String?
}

/** Disabled-module stand-in: core behaves exactly as before LC0. */
object NoOpLicenseProvider : LicenseProvider {
    override fun state(): LicenseState = LicenseState.DISABLED
    override fun isEntitled(): Boolean = true
    override fun sellerId(): String? = null
    override fun accessToken(): String? = null
}
