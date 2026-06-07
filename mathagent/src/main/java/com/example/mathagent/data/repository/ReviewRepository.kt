package com.example.mathagent.data.repository

import com.example.mathagent.data.local.dao.ReviewRecordDao
import com.example.mathagent.data.local.entity.ReviewRecord
import com.example.mathagent.domain.model.ReviewQuality
import com.example.mathagent.domain.model.Sm2Scheduler
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.update

@OptIn(kotlinx.coroutines.ExperimentalCoroutinesApi::class)
class ReviewRepository(
    private val reviewRecordDao: ReviewRecordDao
) {
    /**
     * Monotonic counter to guarantee every refresh() emits a new value,
     * even when called multiple times within the same millisecond.
     * The actual timestamp is read inside flatMapLatest.
     */
    private val refreshCounter = MutableStateFlow(0L)

    /** Due reviews using a freshly-read current time on each trigger. */
    val dueForReview: Flow<List<ReviewRecord>> = refreshCounter.flatMapLatest {
        reviewRecordDao.getDueForReview(System.currentTimeMillis())
    }

    /** Count of due reviews using a freshly-read current time on each trigger. */
    val dueCount: Flow<Int> = refreshCounter.flatMapLatest {
        reviewRecordDao.countDueForReview(System.currentTimeMillis())
    }

    /**
     * Force time-sensitive queries to re-evaluate with the current time.
     * Safe to call multiple times in the same millisecond — each call emits.
     */
    fun refreshTime() {
        refreshCounter.update { it + 1 }
    }

    fun getAll(): Flow<List<ReviewRecord>> = reviewRecordDao.getAll()

    suspend fun getByErrorEntryId(errorEntryId: Long): ReviewRecord? =
        reviewRecordDao.getByErrorEntryId(errorEntryId)

    suspend fun insert(record: ReviewRecord): Long = reviewRecordDao.insert(record)

    suspend fun update(record: ReviewRecord) = reviewRecordDao.update(record)

    suspend fun delete(record: ReviewRecord) = reviewRecordDao.delete(record)

    /**
     * Mark a review record as reviewed using the SM-2 algorithm.
     *
     * Delegates all scheduling logic to [Sm2Scheduler] — the repository
     * only reads the result and writes it back to the DAO.
     *
     * @param record    The current review record.
     * @param quality   How well the student recalled the material.
     * @param nowMillis Current timestamp (caller-provided for testability).
     */
    suspend fun markReviewed(
        record: ReviewRecord,
        quality: ReviewQuality,
        nowMillis: Long = System.currentTimeMillis()
    ) {
        val result = Sm2Scheduler.schedule(record, quality, nowMillis)

        val updated = record.copy(
            lastReviewedAt = result.lastReviewedAt,
            nextReviewAt = result.nextReviewAt,
            intervalDays = result.intervalDays,
            easeFactor = result.easeFactor,
            repetitionCount = result.repetitionCount
        )
        reviewRecordDao.update(updated)
    }
}
