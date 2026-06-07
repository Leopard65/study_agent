package com.example.mathagent.data.repository

import com.example.mathagent.data.local.dao.ProblemRecordDao
import com.example.mathagent.data.local.entity.ProblemRecord
import kotlinx.coroutines.flow.Flow

class ProblemRepository(
    private val problemRecordDao: ProblemRecordDao
) {
    fun getAll(): Flow<List<ProblemRecord>> = problemRecordDao.getAll()

    fun getIncorrect(): Flow<List<ProblemRecord>> = problemRecordDao.getIncorrect()

    fun getBySubject(subject: String): Flow<List<ProblemRecord>> =
        problemRecordDao.getBySubject(subject)

    suspend fun getById(id: Long): ProblemRecord? = problemRecordDao.getById(id)

    suspend fun insert(record: ProblemRecord): Long = problemRecordDao.insert(record)

    suspend fun delete(record: ProblemRecord) = problemRecordDao.delete(record)

    suspend fun deleteById(id: Long) = problemRecordDao.deleteById(id)

    fun count(): Flow<Int> = problemRecordDao.count()

    fun countCorrect(): Flow<Int> = problemRecordDao.countCorrect()
}
