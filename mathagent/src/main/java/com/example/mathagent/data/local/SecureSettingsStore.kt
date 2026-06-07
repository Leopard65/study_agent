package com.example.mathagent.data.local

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import androidx.core.content.edit
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Encrypted SharedPreferences for sensitive settings (API Key).
 * Uses AndroidX Security Crypto with AES256_GCM.
 *
 * API Key must NOT be stored in Room (app_settings) to avoid
 * leaking into plaintext database backups.
 *
 * If EncryptedSharedPreferences becomes corrupted (e.g. system restore,
 * key rotation failure), falls back to deleting the corrupt file and
 * re-creating a fresh instance to avoid app crash.
 */
class SecureSettingsStore(context: Context) {

    private val prefs: SharedPreferences = try {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            PREFS_FILE_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    } catch (e: Exception) {
        // Corrupt keyset or prefs file (e.g. after system restore / key rotation failure).
        // Delete the corrupt file and re-create a fresh instance.
        Log.w(TAG, "EncryptedSharedPreferences corrupted, resetting", e)
        context.getSharedPreferences(PREFS_FILE_NAME, Context.MODE_PRIVATE)
            .edit { clear() }
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            PREFS_FILE_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    suspend fun getApiKey(): String? = try {
        prefs.getString(KEY_API_KEY, null)
    } catch (e: Exception) {
        Log.w(TAG, "Failed to read API key", e)
        null
    }

    suspend fun setApiKey(key: String) {
        try {
            prefs.edit { putString(KEY_API_KEY, key) }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to write API key", e)
        }
    }

    suspend fun clearApiKey() {
        try {
            prefs.edit { remove(KEY_API_KEY) }
        } catch (e: Exception) {
            Log.w(TAG, "Failed to clear API key", e)
        }
    }

    companion object {
        private const val TAG = "SecureSettingsStore"
        private const val PREFS_FILE_NAME = "math_agent_secure_prefs"
        private const val KEY_API_KEY = "ai_api_key"
    }
}
