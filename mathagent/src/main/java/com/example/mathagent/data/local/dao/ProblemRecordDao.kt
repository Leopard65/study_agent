package com.example.mathagent.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.example.mathagent.data.local.entity.ProblemRecord
import kotlinx.coroutines.flow.Flow

@Dao
interface ProblemRecordDao {

    @Query("SELECT * FROM problem_records WHERE id = :id")
    suspend fun getById(id: Long): ProblemRecord?

    @Query("SELECT * FROM problem_records ORDER BY createdAt DESC")
    fun getAll(): Flow<List<ProblemRecord>>

    @Query("SELECT * FROM problem_records WHERE subject = :subject ORDER BY createdAt DESC")
    fun getBySubject(subject: String): Flow<List<ProblemRecord>>

    @Query("SELECT * FROM problem_records WHERE isCorrect = 0 ORDER BY createdAt DESC")
    fun getIncorrect(): Flow<List<ProblemRecord>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(record: ProblemRecord): Long

    @Delete
    suspend fun delete(record: ProblemRecord)

    @Query("DELETE FROM problem_records WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("SELECT COUNT(*) FROM problem_records")
    fun count(): Flow<Int>

    @Query("SELECT COUNT(*) FROM problem_records WHERE isCorrect = 1")
    fun countCorrect(): Flow<Int>

    @Query("SELECT * FROM problem_records")
    suspend fun getAllSync(): List<ProblemRecord>

    @Query("DELETE FROM problem_records")
    suspend fun deleteAllSync()
}
