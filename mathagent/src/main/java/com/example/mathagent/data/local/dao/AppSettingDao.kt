package com.example.mathagent.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.example.mathagent.data.local.entity.AppSetting
import kotlinx.coroutines.flow.Flow

@Dao
interface AppSettingDao {

    @Query("SELECT * FROM app_settings WHERE `key` = :key")
    suspend fun get(key: String): AppSetting?

    @Query("SELECT value FROM app_settings WHERE `key` = :key")
    suspend fun getValue(key: String): String?

    @Query("SELECT * FROM app_settings ORDER BY `key` ASC")
    fun getAll(): Flow<List<AppSetting>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(setting: AppSetting)

    @Query("DELETE FROM app_settings WHERE `key` = :key")
    suspend fun delete(key: String)

    @Query("DELETE FROM app_settings")
    suspend fun deleteAll()

    @Query("SELECT * FROM app_settings")
    suspend fun getAllSync(): List<AppSetting>
}
