package com.example.mathagent

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.entity.BackupLog
import com.example.mathagent.data.local.entity.ChatMessage
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.local.entity.ExamAttempt
import com.example.mathagent.data.local.entity.ExamQuestion
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.local.entity.MaterialChunk
import com.example.mathagent.data.local.entity.ProblemRecord
import com.example.mathagent.data.local.entity.ReviewRecord
import com.example.mathagent.data.local.entity.StudyPlan
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class DaoTest {

    private lateinit var db: MathAgentDatabase

    @Before
    fun createDb() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        db = MathAgentDatabase.createInMemory(context)
        // Ensure FK constraints are enforced
        db.openHelper.writableDatabase.execSQL("PRAGMA foreign_keys = ON")
    }

    @After
    fun closeDb() {
        db.close()
    }

    // ---- MaterialDao ----

    @Test
    fun material_insertAndGetAll() = runTest {
        val dao = db.materialDao()
        val id = dao.insert(Material(title = "高等数学", subject = "数学"))
        val all = dao.getAll().first()
        assertEquals(1, all.size)
        assertEquals("高等数学", all[0].title)
        assertEquals(id, all[0].id)
    }

    @Test
    fun material_delete() = runTest {
        val dao = db.materialDao()
        val id = dao.insert(Material(title = "线性代数"))
        dao.deleteById(id)
        val all = dao.getAll().first()
        assertTrue(all.isEmpty())
    }

    @Test
    fun material_count() = runTest {
        val dao = db.materialDao()
        dao.insert(Material(title = "A"))
        dao.insert(Material(title = "B"))
        val count = dao.count().first()
        assertEquals(2, count)
    }

    // ---- MaterialChunkDao ----

    @Test
    fun materialChunk_insertAndQuery() = runTest {
        val materialDao = db.materialDao()
        val chunkDao = db.materialChunkDao()

        val materialId = materialDao.insert(Material(title = "Test"))
        chunkDao.insert(MaterialChunk(materialId = materialId, chunkIndex = 0, content = "Part 1"))
        chunkDao.insert(MaterialChunk(materialId = materialId, chunkIndex = 1, content = "Part 2"))

        val chunks = chunkDao.getByMaterialId(materialId).first()
        assertEquals(2, chunks.size)
        assertEquals("Part 1", chunks[0].content)
        assertEquals("Part 2", chunks[1].content)
    }

    @Test
    fun materialChunk_cascadeDelete() = runTest {
        val materialDao = db.materialDao()
        val chunkDao = db.materialChunkDao()

        val materialId = materialDao.insert(Material(title = "Test"))
        chunkDao.insert(MaterialChunk(materialId = materialId, chunkIndex = 0, content = "Part"))

        materialDao.deleteById(materialId)
        val chunks = chunkDao.getByMaterialId(materialId).first()
        assertTrue(chunks.isEmpty())
    }

    // ---- ErrorEntryDao ----

    @Test
    fun errorEntry_insertAndGet() = runTest {
        val dao = db.errorEntryDao()
        val id = dao.insert(ErrorEntry(question = "1+1=?", subject = "数学"))
        val entry = dao.getById(id)
        assertNotNull(entry)
        assertEquals("1+1=?", entry!!.question)
    }

    @Test
    fun errorEntry_toggleMastered() = runTest {
        val dao = db.errorEntryDao()
        val id = dao.insert(ErrorEntry(question = "Test"))
        dao.updateMastered(id, true)
        val entry = dao.getById(id)
        assertTrue(entry!!.mastered)
    }

    @Test
    fun errorEntry_unmasteredFilter() = runTest {
        val dao = db.errorEntryDao()
        dao.insert(ErrorEntry(question = "A"))
        val id2 = dao.insert(ErrorEntry(question = "B"))
        dao.updateMastered(id2, true)

        val unmastered = dao.getUnmastered().first()
        assertEquals(1, unmastered.size)
        assertEquals("A", unmastered[0].question)
    }

    // ---- StudyPlanDao ----

    @Test
    fun studyPlan_insertAndGet() = runTest {
        val dao = db.studyPlanDao()
        val id = dao.insert(StudyPlan(title = "复习高数"))
        val plan = dao.getById(id)
        assertNotNull(plan)
        assertEquals("复习高数", plan!!.title)
    }

    @Test
    fun studyPlan_toggleCompleted() = runTest {
        val dao = db.studyPlanDao()
        val id = dao.insert(StudyPlan(title = "Test"))
        dao.updateCompleted(id, true)
        val plan = dao.getById(id)
        assertTrue(plan!!.completed)
    }

    @Test
    fun studyPlan_activeFilter() = runTest {
        val dao = db.studyPlanDao()
        dao.insert(StudyPlan(title = "Active"))
        val id2 = dao.insert(StudyPlan(title = "Done"))
        dao.updateCompleted(id2, true)

        val active = dao.getActive().first()
        assertEquals(1, active.size)
        assertEquals("Active", active[0].title)
    }

    @Test
    fun studyPlan_delete() = runTest {
        val dao = db.studyPlanDao()
        val id = dao.insert(StudyPlan(title = "Test"))
        dao.deleteById(id)
        assertNull(dao.getById(id))
    }

    // ---- ReviewRecordDao (FK: requires parent ErrorEntry) ----

    @Test
    fun reviewRecord_insertAndQuery() = runTest {
        val errorDao = db.errorEntryDao()
        val reviewDao = db.reviewRecordDao()

        val errorId = errorDao.insert(ErrorEntry(question = "Parent"))
        val id = reviewDao.insert(ReviewRecord(errorEntryId = errorId))
        val all = reviewDao.getAll().first()
        assertEquals(1, all.size)
        assertEquals(errorId, all[0].errorEntryId)
    }

    @Test
    fun reviewRecord_dueForReview() = runTest {
        val errorDao = db.errorEntryDao()
        val reviewDao = db.reviewRecordDao()

        val errorId1 = errorDao.insert(ErrorEntry(question = "Past due"))
        val errorId2 = errorDao.insert(ErrorEntry(question = "Future"))

        reviewDao.insert(ReviewRecord(errorEntryId = errorId1, nextReviewAt = System.currentTimeMillis() - 1000))
        reviewDao.insert(ReviewRecord(errorEntryId = errorId2, nextReviewAt = System.currentTimeMillis() + 86400000))

        val due = reviewDao.getDueForReview().first()
        assertEquals(1, due.size)
        assertEquals(errorId1, due[0].errorEntryId)
    }

    @Test
    fun reviewRecord_cascadeDeleteOnErrorEntryDelete() = runTest {
        val errorDao = db.errorEntryDao()
        val reviewDao = db.reviewRecordDao()

        val errorId = errorDao.insert(ErrorEntry(question = "To be deleted"))
        reviewDao.insert(ReviewRecord(errorEntryId = errorId))

        // Verify review exists
        assertNotNull(reviewDao.getByErrorEntryId(errorId))

        // Delete error entry -> cascade deletes review
        errorDao.deleteById(errorId)

        assertNull(reviewDao.getByErrorEntryId(errorId))
    }

    // ---- ChatMessageDao ----

    @Test
    fun chatMessage_insertAndGet() = runTest {
        val dao = db.chatMessageDao()
        dao.insert(ChatMessage(role = "user", content = "你好"))
        dao.insert(ChatMessage(role = "assistant", content = "你好！"))

        val all = dao.getAll().first()
        assertEquals(2, all.size)
    }

    @Test
    fun chatMessage_deleteAll() = runTest {
        val dao = db.chatMessageDao()
        dao.insert(ChatMessage(role = "user", content = "A"))
        dao.insert(ChatMessage(role = "assistant", content = "B"))
        dao.deleteAll()
        assertTrue(dao.getAll().first().isEmpty())
    }

    // ---- ProblemRecordDao ----

    @Test
    fun problemRecord_insertAndQuery() = runTest {
        val dao = db.problemRecordDao()
        dao.insert(ProblemRecord(question = "1+1", isCorrect = true, score = 10))
        dao.insert(ProblemRecord(question = "2+2", isCorrect = false, score = 0))

        val incorrect = dao.getIncorrect().first()
        assertEquals(1, incorrect.size)
        assertEquals("2+2", incorrect[0].question)
    }

    // ---- ExamQuestionDao ----

    @Test
    fun examQuestion_insertAndQuery() = runTest {
        val dao = db.examQuestionDao()
        dao.insert(ExamQuestion(question = "选择题A", subject = "数学"))
        dao.insert(ExamQuestion(question = "选择题B", subject = "物理"))

        val math = dao.getBySubject("数学").first()
        assertEquals(1, math.size)
        assertEquals("选择题A", math[0].question)
    }

    // ---- ExamAttemptDao ----

    @Test
    fun examAttempt_insertAndQuery() = runTest {
        val dao = db.examAttemptDao()
        dao.insert(ExamAttempt(subject = "数学", totalScore = 85, maxScore = 100))
        dao.insert(ExamAttempt(subject = "数学", totalScore = 90, maxScore = 100))

        val best = dao.bestScoreBySubject("数学").first()
        assertEquals(90, best)
    }

    // ---- AppSettingDao ----

    @Test
    fun appSetting_upsertAndGet() = runTest {
        val dao = db.appSettingDao()
        dao.upsert(com.example.mathagent.data.local.entity.AppSetting(key = "theme", value = "dark"))
        val value = dao.getValue("theme")
        assertEquals("dark", value)

        dao.upsert(com.example.mathagent.data.local.entity.AppSetting(key = "theme", value = "light"))
        val updated = dao.getValue("theme")
        assertEquals("light", updated)
    }

    // ---- BackupLogDao ----

    @Test
    fun backupLog_insertAndQuery() = runTest {
        val dao = db.backupLogDao()
        dao.insert(BackupLog(fileName = "backup.db"))
        val latest = dao.getLatest()
        assertNotNull(latest)
        assertEquals("backup.db", latest!!.fileName)
    }

    // ---- Search queries ----

    @Test
    fun errorEntry_searchByQuestion() = runTest {
        val dao = db.errorEntryDao()
        dao.insert(ErrorEntry(question = "What is 2+2?", subject = "Math"))
        dao.insert(ErrorEntry(question = "Photosynthesis process", subject = "Biology"))
        dao.insert(ErrorEntry(question = "What is 3+3?", subject = "Math"))

        val results = dao.search("photosynthesis")
        assertEquals(1, results.size)
        assertEquals("Photosynthesis process", results[0].question)
    }

    @Test
    fun errorEntry_searchBySubject() = runTest {
        val dao = db.errorEntryDao()
        dao.insert(ErrorEntry(question = "Q1", subject = "Physics"))
        dao.insert(ErrorEntry(question = "Q2", subject = "Chemistry"))

        val results = dao.search("physics")
        assertEquals(1, results.size)
        assertEquals("Physics", results[0].subject)
    }

    @Test
    fun studyPlan_searchByTitle() = runTest {
        val dao = db.studyPlanDao()
        dao.insert(StudyPlan(title = "复习高数", subject = "数学"))
        dao.insert(StudyPlan(title = "英语阅读", subject = "英语"))

        val results = dao.search("高数")
        assertEquals(1, results.size)
        assertEquals("复习高数", results[0].title)
    }

    @Test
    fun material_searchByTitle() = runTest {
        val dao = db.materialDao()
        dao.insert(Material(title = "高等数学讲义", subject = "数学"))
        dao.insert(Material(title = "英语词汇手册", subject = "英语"))

        val results = dao.search("数学")
        assertEquals(1, results.size)
        assertEquals("高等数学讲义", results[0].title)
    }

    @Test
    fun material_daoSearch_emptyString_sqliteLikeMatchesAll() = runTest {
        // NOTE: This tests SQLite LIKE '%%' behavior, NOT business search logic.
        // Business layer (SearchRepository/SearchViewModel) guards against empty queries.
        val dao = db.materialDao()
        dao.insert(Material(title = "Test1"))
        dao.insert(Material(title = "Test2"))

        val results = dao.search("")
        assertEquals(2, results.size)
    }

    @Test
    fun material_update() = runTest {
        val dao = db.materialDao()
        val id = dao.insert(Material(title = "Original"))
        val material = dao.getById(id)!!
        dao.update(material.copy(title = "Updated"))
        val updated = dao.getById(id)!!
        assertEquals("Updated", updated.title)
    }
}
