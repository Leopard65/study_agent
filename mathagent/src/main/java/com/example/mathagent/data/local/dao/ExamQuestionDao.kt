package com.example.mathagent.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.example.mathagent.data.local.entity.ExamQuestion
import kotlinx.coroutines.flow.Flow

@Dao
interface ExamQuestionDao {

    @Query("SELECT * FROM exam_questions ORDER BY createdAt DESC")
    fun getAll(): Flow<List<ExamQuestion>>

    @Query("SELECT * FROM exam_questions WHERE id = :id")
    suspend fun getById(id: Long): ExamQuestion?

    @Query("SELECT * FROM exam_questions WHERE subject = :subject ORDER BY createdAt DESC")
    fun getBySubject(subject: String): Flow<List<ExamQuestion>>

    @Query("SELECT * FROM exam_questions WHERE subject = :subject ORDER BY RANDOM() LIMIT :count")
    suspend fun getRandomBySubject(subject: String, count: Int): List<ExamQuestion>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(question: ExamQuestion): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(questions: List<ExamQuestion>)

    @Delete
    suspend fun delete(question: ExamQuestion)

    @Query("DELETE FROM exam_questions WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("SELECT COUNT(*) FROM exam_questions")
    fun count(): Flow<Int>

    @Query("SELECT * FROM exam_questions")
    suspend fun getAllSync(): List<ExamQuestion>

    @Query("DELETE FROM exam_questions")
    suspend fun deleteAllSync()
}
