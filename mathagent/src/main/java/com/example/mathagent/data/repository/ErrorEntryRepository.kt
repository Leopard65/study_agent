package com.example.mathagent.data.repository

import androidx.room.withTransaction
import com.example.mathagent.data.local.dao.ErrorEntryDao
import com.example.mathagent.data.local.dao.ReviewRecordDao
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.local.entity.ReviewRecord
import kotlinx.coroutines.flow.Flow

class ErrorEntryRepository(
    private val database: androidx.room.RoomDatabase,
    private val errorEntryDao: ErrorEntryDao,
    private val reviewRecordDao: ReviewRecordDao
) {
    fun getAll(): Flow<List<ErrorEntry>> = errorEntryDao.getAll()

    fun getUnmastered(): Flow<List<ErrorEntry>> = errorEntryDao.getUnmastered()

    fun getMastered(): Flow<List<ErrorEntry>> = errorEntryDao.getMastered()

    suspend fun getById(id: Long): ErrorEntry? = errorEntryDao.getById(id)

    /**
     * Insert an error entry AND its initial review record atomically.
     * Both succeed or both are rolled back.
     * This is the single entry point for adding errors — never call DAO directly.
     */
    suspend fun insert(errorEntry: ErrorEntry): Long = database.withTransaction {
        val id = errorEntryDao.insert(errorEntry)
        reviewRecordDao.insert(
            ReviewRecord(
                errorEntryId = id,
                nextReviewAt = System.currentTimeMillis(),
                intervalDays = 1,
                easeFactor = 2.5f,
                repetitionCount = 0
            )
        )
        id
    }

    suspend fun update(errorEntry: ErrorEntry) = errorEntryDao.update(errorEntry)

    /**
     * Delete error entry. Review records are cascade-deleted by Room FK constraint.
     */
    suspend fun delete(errorEntry: ErrorEntry) {
        errorEntryDao.delete(errorEntry)
    }

    /**
     * Delete error entry by id. Review records are cascade-deleted by Room FK constraint.
     */
    suspend fun deleteById(id: Long) {
        errorEntryDao.deleteById(id)
    }

    suspend fun toggleMastered(id: Long) {
        val current = errorEntryDao.getById(id) ?: return
        errorEntryDao.updateMastered(id, !current.mastered)
    }

    fun count(): Flow<Int> = errorEntryDao.count()

    fun countUnmastered(): Flow<Int> = errorEntryDao.countUnmastered()
}
