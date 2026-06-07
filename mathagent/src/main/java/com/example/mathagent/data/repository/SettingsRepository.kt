package com.example.mathagent.data.repository

import com.example.mathagent.data.local.dao.AppSettingDao
import com.example.mathagent.data.local.entity.AppSetting
import kotlinx.coroutines.flow.Flow

/**
 * Settings repository for non-sensitive settings stored in Room.
 * API Key is handled separately by SecureSettingsStore (encrypted).
 */
class SettingsRepository(
    private val appSettingDao: AppSettingDao
) {
    suspend fun get(key: String): AppSetting? = appSettingDao.get(key)

    suspend fun getValue(key: String): String? = appSettingDao.getValue(key)

    fun getAll(): Flow<List<AppSetting>> = appSettingDao.getAll()

    suspend fun set(key: String, value: String) {
        appSettingDao.upsert(AppSetting(key = key, value = value, updatedAt = System.currentTimeMillis()))
    }

    suspend fun delete(key: String) = appSettingDao.delete(key)

    // AI config helpers (non-sensitive only)
    suspend fun getBaseUrl(): String? = getValue(KEY_AI_BASE_URL)
    suspend fun setBaseUrl(url: String) = set(KEY_AI_BASE_URL, url)

    suspend fun getModel(): String? = getValue(KEY_AI_MODEL)
    suspend fun setModel(model: String) = set(KEY_AI_MODEL, model)

    companion object {
        const val KEY_AI_BASE_URL = "ai_base_url"
        const val KEY_AI_MODEL = "ai_model"
        // API Key removed — stored in SecureSettingsStore instead
    }
}
