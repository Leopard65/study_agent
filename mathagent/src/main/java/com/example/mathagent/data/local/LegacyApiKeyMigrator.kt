package com.example.mathagent.data.local

import android.util.Log
import com.example.mathagent.data.repository.SettingsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking

/**
 * One-time migration: moves ai_api_key from Room app_settings to
 * [SecureSettingsStore], then deletes the Room copy.
 *
 * Runs synchronously so the key is available before any UI reads.
 * Safe to call on every start — no-op if key absent from Room.
 *
 * Extracted from AppContainer for testability.
 */
object LegacyApiKeyMigrator {

    private const val TAG = "LegacyApiKeyMigrator"
    private const val KEY_AI_API_KEY = "ai_api_key"

    /**
     * Run the migration. Returns true if a key was migrated, false if no-op.
     *
     * All IO operations are batched in a single [runBlocking] to minimise
     * main-thread blocking switches during app startup.
     *
     * @param verifyWrite  read-back check after writing to SecureSettingsStore.
     *                     Default reads from the real store; tests can override
     *                     to simulate write failures.
     */
    fun migrate(
        settingsRepository: SettingsRepository,
        secureSettingsStore: SecureSettingsStore,
        verifyWrite: (suspend () -> String?)? = null
    ): Boolean {
        return try {
            runBlocking(Dispatchers.IO) {
                val oldKey = settingsRepository.getValue(KEY_AI_API_KEY)
                if (oldKey.isNullOrBlank()) return@runBlocking false

                secureSettingsStore.setApiKey(oldKey)

                // Verify write succeeded before deleting source
                val readBack = verifyWrite ?: { secureSettingsStore.getApiKey() }
                val verifyKey = readBack()

                if (verifyKey == oldKey) {
                    settingsRepository.delete(KEY_AI_API_KEY)
                    Log.i(TAG, "Migrated ai_api_key from Room to SecureSettingsStore")
                    true
                } else {
                    Log.w(TAG, "API key migration verify failed, keeping Room copy")
                    false
                }
            }
        } catch (e: Exception) {
            Log.w(TAG, "API key migration skipped", e)
            false
        }
    }
}
