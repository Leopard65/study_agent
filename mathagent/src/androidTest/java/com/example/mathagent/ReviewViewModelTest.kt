package com.example.mathagent

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.repository.ErrorEntryRepository
import com.example.mathagent.data.repository.ReviewRepository
import com.example.mathagent.domain.model.ReviewQuality
import com.example.mathagent.ui.viewmodel.ReviewViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented tests for ReviewViewModel using real Room database.
 * Uses polling-based waiting instead of Thread.sleep for deterministic execution.
 * No Thread.sleep required.
 */
@RunWith(AndroidJUnit4::class)
class ReviewViewModelTest {

    private lateinit var db: MathAgentDatabase
    private lateinit var reviewRepo: ReviewRepository
    private lateinit var errorRepo: ErrorEntryRepository

    @Before
    fun setup() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        db = Room.inMemoryDatabaseBuilder(context, MathAgentDatabase::class.java)
            .allowMainThreadQueries().build()
        db.openHelper.writableDatabase.execSQL("PRAGMA foreign_keys = ON")
        reviewRepo = ReviewRepository(db.reviewRecordDao())
        errorRepo = ErrorEntryRepository(db, db.errorEntryDao(), db.reviewRecordDao())
    }

    @After
    fun teardown() {
        db.close()
    }

    /**
     * Polls until the predicate is true or timeout expires.
     * No Thread.sleep — uses coroutine delay for cooperative waiting.
     */
    private suspend fun waitFor(
        timeoutMs: Long = 3000,
        intervalMs: Long = 20,
        predicate: () -> Boolean
    ) {
        val start = System.currentTimeMillis()
        while (!predicate()) {
            if (System.currentTimeMillis() - start > timeoutMs) {
                throw AssertionError("Timed out waiting for condition")
            }
            withContext(Dispatchers.IO) {
                kotlinx.coroutines.delay(intervalMs)
            }
        }
    }

    @Test
    fun initialLoad_showsDueReviews() = runBlocking {
        val errorId = errorRepo.insert(ErrorEntry(id = 0, question = "What is 1+1?"))

        val vm = ReviewViewModel(reviewRepo, errorRepo)
        waitFor { !vm.uiState.value.isLoading }

        val state = vm.uiState.value
        assertTrue(!state.isLoading)
        assertEquals(1, state.dueReviews.size)
        assertEquals(errorId, state.dueReviews[0].errorEntryId)
        assertNotNull(state.errorEntries[errorId])
        assertEquals("What is 1+1?", state.errorEntries[errorId]!!.question)
    }

    @Test
    fun markReviewed_good_removesFromDueList() = runBlocking {
        errorRepo.insert(ErrorEntry(id = 0, question = "Q1"))

        val vm = ReviewViewModel(reviewRepo, errorRepo)
        waitFor { vm.uiState.value.dueReviews.isNotEmpty() }

        assertEquals(1, vm.uiState.value.dueReviews.size)

        vm.markReviewed(vm.uiState.value.dueReviews[0], ReviewQuality.Good)
        waitFor { vm.uiState.value.dueReviews.isEmpty() }

        vm.refresh()
        waitFor { !vm.uiState.value.isLoading }

        assertEquals(0, vm.uiState.value.dueReviews.size)
    }

    @Test
    fun markReviewed_again_resetsAndRemovesFromDueList() = runBlocking {
        errorRepo.insert(ErrorEntry(id = 0, question = "Q2"))

        val vm = ReviewViewModel(reviewRepo, errorRepo)
        waitFor { vm.uiState.value.dueReviews.isNotEmpty() }

        val record = vm.uiState.value.dueReviews[0]
        assertEquals(0, record.repetitionCount)

        vm.markReviewed(record, ReviewQuality.Again)
        waitFor { vm.uiState.value.dueReviews.isEmpty() }

        // After refresh, the record should re-appear (interval=0 means immediately due)
        vm.refresh()
        waitFor { vm.uiState.value.dueReviews.isNotEmpty() }

        val updatedRecord = vm.uiState.value.dueReviews[0]
        assertEquals(0, updatedRecord.repetitionCount)  // Again resets
        assertEquals(0, updatedRecord.intervalDays)      // Again → 0 days
    }

    @Test
    fun markReviewed_easy_incrementsRepetition() = runBlocking {
        errorRepo.insert(ErrorEntry(id = 0, question = "Q3"))

        val vm = ReviewViewModel(reviewRepo, errorRepo)
        waitFor { vm.uiState.value.dueReviews.isNotEmpty() }

        val record = vm.uiState.value.dueReviews[0]
        assertEquals(0, record.repetitionCount)
        assertEquals(1, record.intervalDays)

        vm.markReviewed(record, ReviewQuality.Easy)
        waitFor { vm.uiState.value.dueReviews.isEmpty() }

        // Check the record was updated in the database
        val updatedRecord = db.reviewRecordDao().getById(record.id)!!
        assertEquals(1, updatedRecord.repetitionCount)
        assertEquals(4, updatedRecord.intervalDays)  // Easy rep 0 → 4 days
    }

    @Test
    fun markReviewed_hard_resetsRepetition() = runBlocking {
        errorRepo.insert(ErrorEntry(id = 0, question = "Q4"))

        val vm = ReviewViewModel(reviewRepo, errorRepo)
        waitFor { vm.uiState.value.dueReviews.isNotEmpty() }

        val record = vm.uiState.value.dueReviews[0]

        // First: mark as Good to build up repetition
        vm.markReviewed(record, ReviewQuality.Good)
        waitFor { vm.uiState.value.dueReviews.isEmpty() }
        vm.refresh()
        waitFor { vm.uiState.value.dueReviews.isNotEmpty() }

        val secondRecord = vm.uiState.value.dueReviews[0]
        assertEquals(1, secondRecord.repetitionCount)

        // Now mark as Hard — should reset repetition
        vm.markReviewed(secondRecord, ReviewQuality.Hard)
        waitFor { vm.uiState.value.dueReviews.isEmpty() }

        val finalRecord = db.reviewRecordDao().getById(secondRecord.id)!!
        assertEquals(0, finalRecord.repetitionCount)  // Hard resets
    }

    @Test
    fun skip_removesFromDueList() = runBlocking {
        errorRepo.insert(ErrorEntry(id = 0, question = "Q5"))

        val vm = ReviewViewModel(reviewRepo, errorRepo)
        waitFor { vm.uiState.value.dueReviews.isNotEmpty() }

        assertEquals(1, vm.uiState.value.dueReviews.size)

        vm.skip(vm.uiState.value.dueReviews[0])
        waitFor { vm.uiState.value.dueReviews.isEmpty() }

        vm.refresh()
        waitFor { !vm.uiState.value.isLoading }

        assertEquals(0, vm.uiState.value.dueReviews.size)
    }

    @Test
    fun multipleErrors_allShowUp() = runBlocking {
        errorRepo.insert(ErrorEntry(id = 0, question = "Q1"))
        errorRepo.insert(ErrorEntry(id = 0, question = "Q2"))
        errorRepo.insert(ErrorEntry(id = 0, question = "Q3"))

        val vm = ReviewViewModel(reviewRepo, errorRepo)
        waitFor { vm.uiState.value.dueReviews.size == 3 }

        assertEquals(3, vm.uiState.value.dueReviews.size)
    }
}
