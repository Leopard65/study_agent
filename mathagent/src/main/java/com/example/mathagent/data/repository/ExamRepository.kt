package com.example.mathagent.data.repository

import com.example.mathagent.data.local.dao.ExamAttemptDao
import com.example.mathagent.data.local.dao.ExamQuestionDao
import com.example.mathagent.data.local.entity.ExamAttempt
import com.example.mathagent.data.local.entity.ExamQuestion
import kotlinx.coroutines.flow.Flow

class ExamRepository(
    private val questionDao: ExamQuestionDao,
    private val attemptDao: ExamAttemptDao
) {
    // Questions
    fun getAllQuestions(): Flow<List<ExamQuestion>> = questionDao.getAll()

    fun getQuestionsBySubject(subject: String): Flow<List<ExamQuestion>> =
        questionDao.getBySubject(subject)

    suspend fun getRandomQuestions(subject: String, count: Int): List<ExamQuestion> =
        questionDao.getRandomBySubject(subject, count)

    suspend fun insertQuestion(question: ExamQuestion): Long = questionDao.insert(question)

    suspend fun deleteQuestion(question: ExamQuestion) = questionDao.delete(question)

    fun questionCount(): Flow<Int> = questionDao.count()

    // Attempts
    fun getAllAttempts(): Flow<List<ExamAttempt>> = attemptDao.getAll()

    fun getAttemptsBySubject(subject: String): Flow<List<ExamAttempt>> =
        attemptDao.getBySubject(subject)

    suspend fun insertAttempt(attempt: ExamAttempt): Long = attemptDao.insert(attempt)

    fun attemptCount(): Flow<Int> = attemptDao.count()

    fun bestScore(subject: String): Flow<Int?> = attemptDao.bestScoreBySubject(subject)
}
