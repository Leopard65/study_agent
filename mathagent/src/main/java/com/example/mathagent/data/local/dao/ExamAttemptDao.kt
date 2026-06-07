package com.example.mathagent.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.example.mathagent.data.local.entity.ExamAttempt
import kotlinx.coroutines.flow.Flow

@Dao
interface ExamAttemptDao {

    @Query("SELECT * FROM exam_attempts ORDER BY createdAt DESC")
    fun getAll(): Flow<List<ExamAttempt>>

    @Query("SELECT * FROM exam_attempts WHERE id = :id")
    suspend fun getById(id: Long): ExamAttempt?

    @Query("SELECT * FROM exam_attempts WHERE subject = :subject ORDER BY createdAt DESC")
    fun getBySubject(subject: String): Flow<List<ExamAttempt>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(attempt: ExamAttempt): Long

    @Delete
    suspend fun delete(attempt: ExamAttempt)

    @Query("DELETE FROM exam_attempts WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("SELECT COUNT(*) FROM exam_attempts")
    fun count(): Flow<Int>

    @Query("SELECT MAX(totalScore) FROM exam_attempts WHERE subject = :subject")
    fun bestScoreBySubject(subject: String): Flow<Int?>

    @Query("SELECT * FROM exam_attempts")
    suspend fun getAllSync(): List<ExamAttempt>

    @Query("DELETE FROM exam_attempts")
    suspend fun deleteAllSync()
}
