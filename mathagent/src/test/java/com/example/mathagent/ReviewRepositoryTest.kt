package com.example.mathagent

import com.example.mathagent.data.local.dao.ReviewRecordDao
import com.example.mathagent.data.local.entity.ReviewRecord
import com.example.mathagent.data.repository.ReviewRepository
import com.example.mathagent.domain.model.ReviewQuality
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class ReviewRepositoryTest {

    private val testDispatcher = StandardTestDispatcher()

    @Before
    fun setup() {
        Dispatchers.setMain(testDispatcher)
    }

    @After
    fun teardown() {
        Dispatchers.resetMain()
    }

    private class FakeReviewRecordDao : ReviewRecordDao {
        val inserted = mutableListOf<ReviewRecord>()
        val updated = mutableListOf<ReviewRecord>()
        var getDueForReviewCallCount = 0
        private val dueFlow = MutableStateFlow<List<ReviewRecord>>(emptyList())

        fun setDue(reviews: List<ReviewRecord>) { dueFlow.value = reviews }

        override fun getAll(): Flow<List<ReviewRecord>> = flowOf(emptyList())
        override fun getDueForReview(now: Long): Flow<List<ReviewRecord>> {
            getDueForReviewCallCount++
            return dueFlow
        }
        override suspend fun getById(id: Long): ReviewRecord? = null
        override suspend fun getByErrorEntryId(errorEntryId: Long): ReviewRecord? = null
        override suspend fun insert(record: ReviewRecord): Long {
            inserted.add(record)
            return inserted.size.toLong()
        }
        override suspend fun update(record: ReviewRecord) { updated.add(record) }
        override suspend fun delete(record: ReviewRecord) {}
        override suspend fun deleteByErrorEntryId(errorEntryId: Long) {}
        override fun countDueForReview(now: Long): Flow<Int> = flowOf(dueFlow.value.size)
        override suspend fun getAllSync(): List<ReviewRecord> = emptyList()
        override suspend fun deleteAllSync() {}
    }

    @Test
    fun reviewRepo_initialEmission_noRefreshNeeded() = runTest(testDispatcher) {
        val dao = FakeReviewRecordDao()
        dao.setDue(listOf(ReviewRecord(id = 42, errorEntryId = 99)))

        val repo = ReviewRepository(dao)
        val result = repo.dueForReview.first()

        assertEquals(1, result.size)
        assertEquals(99L, result[0].errorEntryId)
    }

    @Test
    fun reviewRepo_dueCount_initialEmission() = runTest(testDispatcher) {
        val dao = FakeReviewRecordDao()
        dao.setDue(listOf(
            ReviewRecord(id = 1, errorEntryId = 10),
            ReviewRecord(id = 2, errorEntryId = 20),
            ReviewRecord(id = 3, errorEntryId = 30)
        ))

        val repo = ReviewRepository(dao)
        assertEquals(3, repo.dueCount.first())
    }

    @Test
    fun reviewRepo_refreshTime_triggersReQuery_activeCollector() = runTest(testDispatcher) {
        val dao = FakeReviewRecordDao()
        dao.setDue(emptyList())
        val repo = ReviewRepository(dao)

        val emissions = async { repo.dueForReview.take(3).toList() }
        advanceUntilIdle()

        val countAfterInitial = dao.getDueForReviewCallCount

        repo.refreshTime()
        advanceUntilIdle()
        repo.refreshTime()
        advanceUntilIdle()

        val result = emissions.await()
        assertEquals(3, result.size)
        assertTrue("Expected re-queries after refresh", dao.getDueForReviewCallCount > countAfterInitial)
    }

    @Test
    fun reviewRepo_markReviewed_good_updatesDao() = runTest(testDispatcher) {
        val dao = FakeReviewRecordDao()
        val record = ReviewRecord(id = 1, errorEntryId = 10, intervalDays = 1, easeFactor = 2.5f, repetitionCount = 0)
        dao.setDue(listOf(record))
        val repo = ReviewRepository(dao)
        repo.dueForReview.first()

        val now = 1_700_000_000_000L
        repo.markReviewed(record, ReviewQuality.Good, nowMillis = now)

        assertEquals(1, dao.updated.size)
        val updated = dao.updated[0]
        assertEquals(1, updated.repetitionCount)   // Good increments
        assertEquals(1, updated.intervalDays)       // rep 0 → 1 day
        assertEquals(now, updated.lastReviewedAt)
        assertEquals(now + 1 * 24 * 60 * 60 * 1000L, updated.nextReviewAt)
    }

    @Test
    fun reviewRepo_markReviewed_easy_bonusInterval() = runTest(testDispatcher) {
        val dao = FakeReviewRecordDao()
        val record = ReviewRecord(id = 1, errorEntryId = 10, intervalDays = 1, easeFactor = 2.5f, repetitionCount = 0)
        val repo = ReviewRepository(dao)

        repo.markReviewed(record, ReviewQuality.Easy, nowMillis = 1_000_000L)
        val updated = dao.updated.last()

        assertEquals(1, updated.repetitionCount)   // Easy increments
        assertEquals(4, updated.intervalDays)       // rep 0 → 4 days
        assertEquals(2.6f, updated.easeFactor, 0.01f) // Easy: +0.1
    }

    @Test
    fun reviewRepo_markReviewed_again_resetsRepetition() = runTest(testDispatcher) {
        val dao = FakeReviewRecordDao()
        val record = ReviewRecord(id = 1, errorEntryId = 10, intervalDays = 20,
            easeFactor = 2.5f, repetitionCount = 5)
        val repo = ReviewRepository(dao)

        repo.markReviewed(record, ReviewQuality.Again, nowMillis = 1_000_000L)
        val updated = dao.updated.last()

        assertEquals(0, updated.repetitionCount)   // Again resets
        assertEquals(0, updated.intervalDays)       // Again → same day
        assertEquals(1_000_000L, updated.nextReviewAt) // immediately re-due
    }

    @Test
    fun reviewRepo_markReviewed_hard_resetsRepetition() = runTest(testDispatcher) {
        val dao = FakeReviewRecordDao()
        val record = ReviewRecord(id = 1, errorEntryId = 10, intervalDays = 20,
            easeFactor = 2.5f, repetitionCount = 3)
        val repo = ReviewRepository(dao)

        repo.markReviewed(record, ReviewQuality.Hard, nowMillis = 1_000_000L)
        val updated = dao.updated.last()

        assertEquals(0, updated.repetitionCount)   // Hard resets
        assertEquals(24, updated.intervalDays)      // Hard rep 2+ → max(20*1.2, 1) = 24
    }

    @Test
    fun reviewRepo_markReviewed_good_incrementsRepetition() = runTest(testDispatcher) {
        val dao = FakeReviewRecordDao()
        val repo = ReviewRepository(dao)

        // First review
        val record = ReviewRecord(id = 1, errorEntryId = 10, intervalDays = 1,
            easeFactor = 2.5f, repetitionCount = 0)
        repo.markReviewed(record, ReviewQuality.Good, nowMillis = 1_000_000L)
        val first = dao.updated.last()
        assertEquals(1, first.repetitionCount)
        assertEquals(1, first.intervalDays)

        // Second review
        repo.markReviewed(first, ReviewQuality.Good, nowMillis = 2_000_000L)
        val second = dao.updated.last()
        assertEquals(2, second.repetitionCount)
        assertEquals(6, second.intervalDays) // rep 1 → 6 days
    }

    @Test
    fun reviewRepo_markReviewed_easeFactor_clampedAtMinimum() = runTest(testDispatcher) {
        val dao = FakeReviewRecordDao()
        val repo = ReviewRepository(dao)

        val record = ReviewRecord(id = 1, errorEntryId = 10, intervalDays = 1,
            easeFactor = 1.2f, repetitionCount = 0)
        repo.markReviewed(record, ReviewQuality.Again, nowMillis = 1_000_000L)
        val updated = dao.updated.last()

        assertEquals(1.3f, updated.easeFactor, 0.01f)
    }
}
