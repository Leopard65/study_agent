package com.example.mathagent.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.example.mathagent.data.local.entity.BackupLog
import kotlinx.coroutines.flow.Flow

@Dao
interface BackupLogDao {

    @Query("SELECT * FROM backup_logs ORDER BY createdAt DESC")
    fun getAll(): Flow<List<BackupLog>>

    @Query("SELECT * FROM backup_logs ORDER BY createdAt DESC LIMIT 1")
    suspend fun getLatest(): BackupLog?

    @Query("SELECT * FROM backup_logs ORDER BY createdAt DESC LIMIT 1")
    fun getLatestFlow(): Flow<BackupLog?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(log: BackupLog): Long

    @Delete
    suspend fun delete(log: BackupLog)

    @Query("DELETE FROM backup_logs WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("SELECT COUNT(*) FROM backup_logs")
    fun count(): Flow<Int>
}
