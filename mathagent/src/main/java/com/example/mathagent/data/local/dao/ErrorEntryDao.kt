package com.example.mathagent.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.example.mathagent.data.local.entity.ErrorEntry
import kotlinx.coroutines.flow.Flow

@Dao
interface ErrorEntryDao {

    @Query("SELECT * FROM error_entries ORDER BY createdAt DESC")
    fun getAll(): Flow<List<ErrorEntry>>

    @Query("SELECT * FROM error_entries WHERE id = :id")
    suspend fun getById(id: Long): ErrorEntry?

    @Query("SELECT * FROM error_entries WHERE mastered = 0 ORDER BY createdAt DESC")
    fun getUnmastered(): Flow<List<ErrorEntry>>

    @Query("SELECT * FROM error_entries WHERE mastered = 1 ORDER BY updatedAt DESC")
    fun getMastered(): Flow<List<ErrorEntry>>

    @Query("SELECT * FROM error_entries WHERE subject = :subject ORDER BY createdAt DESC")
    fun getBySubject(subject: String): Flow<List<ErrorEntry>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(errorEntry: ErrorEntry): Long

    @Update
    suspend fun update(errorEntry: ErrorEntry)

    @Delete
    suspend fun delete(errorEntry: ErrorEntry)

    @Query("DELETE FROM error_entries WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("UPDATE error_entries SET mastered = :mastered, updatedAt = :updatedAt WHERE id = :id")
    suspend fun updateMastered(id: Long, mastered: Boolean, updatedAt: Long = System.currentTimeMillis())

    @Query("UPDATE error_entries SET analysis = :analysis, updatedAt = :updatedAt WHERE id = :id")
    suspend fun updateAnalysis(id: Long, analysis: String, updatedAt: Long = System.currentTimeMillis())

    @Query("SELECT COUNT(*) FROM error_entries")
    fun count(): Flow<Int>

    @Query("SELECT COUNT(*) FROM error_entries WHERE mastered = 0")
    fun countUnmastered(): Flow<Int>

    @Query("SELECT * FROM error_entries WHERE question LIKE '%' || :query || '%' OR subject LIKE '%' || :query || '%' OR analysis LIKE '%' || :query || '%' ORDER BY createdAt DESC")
    suspend fun search(query: String): List<ErrorEntry>

    @Query("SELECT * FROM error_entries")
    suspend fun getAllSync(): List<ErrorEntry>

    @Query("DELETE FROM error_entries")
    suspend fun deleteAllSync()
}
