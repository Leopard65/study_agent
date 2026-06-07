package com.example.mathagent

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.SecureSettingsStore
import com.example.mathagent.data.local.dao.ReviewRecordDao
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.local.entity.ReviewRecord
import com.example.mathagent.data.repository.ErrorEntryRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented tests for ErrorEntryRepository:
 * - Inserting an error entry creates a ReviewRecord (transactional)
 * - Deleting an error entry cascade-deletes its ReviewRecord
 * - Transaction rollback on failure
 * - API Key is not stored in app_settings
 */
@RunWith(AndroidJUnit4::class)
class ErrorEntryRepositoryTest {

    private lateinit var db: MathAgentDatabase
    private lateinit var repo: ErrorEntryRepository

    @Before
    fun setup() {
        db = Room.inMemoryDatabaseBuilder(
            ApplicationProvider.getApplicationContext(),
            MathAgentDatabase::class.java
        ).allowMainThreadQueries().build()

        db.openHelper.writableDatabase.execSQL("PRAGMA foreign_keys = ON")

        repo = ErrorEntryRepository(
            database = db,
            errorEntryDao = db.errorEntryDao(),
            reviewRecordDao = db.reviewRecordDao()
        )
    }

    @After
    fun teardown() {
        db.close()
    }

    @Test
    fun insertErrorEntry_createsReviewRecord() = runTest {
        val error = ErrorEntry(question = "What is 2+2?")
        val id = repo.insert(error)

        val saved = repo.getById(id)
        assertNotNull(saved)
        assertEquals("What is 2+2?", saved!!.question)

        val review = db.reviewRecordDao().getByErrorEntryId(id)
        assertNotNull(review)
        assertEquals(id, review!!.errorEntryId)
        assertEquals(1, review.intervalDays)
        assertEquals(2.5f, review.easeFactor)
        assertEquals(0, review.repetitionCount)
    }

    @Test
    fun insert_isTransactional() = runTest {
        val id = repo.insert(ErrorEntry(question = "Transactional test"))

        val errorEntry = repo.getById(id)
        val reviewRecord = db.reviewRecordDao().getByErrorEntryId(id)

        assertNotNull("Error entry must exist", errorEntry)
        assertNotNull("Review record must exist", reviewRecord)
        assertEquals(id, reviewRecord!!.errorEntryId)
    }

    @Test
    fun insert_rollsBackOnReviewInsertFailure() = runTest {
        // Use a fake ReviewRecordDao that always throws to simulate failure
        val failingReviewDao = object : ReviewRecordDao {
            override fun getAll(): Flow<List<ReviewRecord>> = throw NotImplementedError()
            override fun getDueForReview(now: Long): Flow<List<ReviewRecord>> = throw NotImplementedError()
            override suspend fun getById(id: Long): ReviewRecord? = throw NotImplementedError()
            override suspend fun getByErrorEntryId(errorEntryId: Long): ReviewRecord? = throw NotImplementedError()
            override suspend fun insert(record: ReviewRecord): Long = throw RuntimeException("Simulated DB failure")
            override suspend fun update(record: ReviewRecord) = throw NotImplementedError()
            override suspend fun delete(record: ReviewRecord) = throw NotImplementedError()
            override suspend fun deleteByErrorEntryId(errorEntryId: Long) = throw NotImplementedError()
            override fun countDueForReview(now: Long): Flow<Int> = throw NotImplementedError()
            override suspend fun getAllSync(): List<ReviewRecord> = throw NotImplementedError()
            override suspend fun deleteAllSync() = throw NotImplementedError()
        }

        val failingRepo = ErrorEntryRepository(
            database = db,
            errorEntryDao = db.errorEntryDao(),
            reviewRecordDao = failingReviewDao
        )

        try {
            failingRepo.insert(ErrorEntry(question = "Should be rolled back"))
            fail("Expected exception was not thrown")
        } catch (e: RuntimeException) {
            assertEquals("Simulated DB failure", e.message)
        }

        // The error entry should NOT exist (transaction rolled back)
        val all = db.errorEntryDao().getAll().first()
        assertEquals("Error entry should be rolled back", 0, all.size)
    }

    @Test
    fun deleteErrorEntry_cascadeDeletesReviewRecord() = runTest {
        val error = ErrorEntry(question = "What is 3+3?")
        val id = repo.insert(error)

        val reviewBefore = db.reviewRecordDao().getByErrorEntryId(id)
        assertNotNull(reviewBefore)

        val saved = repo.getById(id)!!
        repo.delete(saved)

        assertNull(repo.getById(id))
        assertNull(db.reviewRecordDao().getByErrorEntryId(id))
    }

    @Test
    fun deleteById_cascadeDeletesReviewRecord() = runTest {
        val error = ErrorEntry(question = "What is 5+5?")
        val id = repo.insert(error)

        assertNotNull(db.reviewRecordDao().getByErrorEntryId(id))

        repo.deleteById(id)

        assertNull(repo.getById(id))
        assertNull(db.reviewRecordDao().getByErrorEntryId(id))
    }

    @Test
    fun apiKey_secureStoreDoesNotWriteToRoom() = runTest {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val secureStore = SecureSettingsStore(context)

        secureStore.setApiKey("sk-test-secret-key-12345")

        val apiKeyInRoom = db.appSettingDao().getValue("ai_api_key")
        assertNull(
            "API Key must NOT appear in Room app_settings table after SecureSettingsStore.setApiKey()",
            apiKeyInRoom
        )

        val retrieved = secureStore.getApiKey()
        assertEquals("sk-test-secret-key-12345", retrieved)

        secureStore.clearApiKey()
    }

    @Test
    fun getAll_returnsInsertedErrors() = runTest {
        repo.insert(ErrorEntry(question = "Q1"))
        repo.insert(ErrorEntry(question = "Q2"))
        repo.insert(ErrorEntry(question = "Q3"))

        val all = repo.getAll().first()
        assertEquals(3, all.size)
    }

    @Test
    fun toggleMastered_flipsState() = runTest {
        val id = repo.insert(ErrorEntry(question = "Q1", mastered = false))

        repo.toggleMastered(id)
        val after1 = repo.getById(id)!!
        assertEquals(true, after1.mastered)

        repo.toggleMastered(id)
        val after2 = repo.getById(id)!!
        assertEquals(false, after2.mastered)
    }
}
