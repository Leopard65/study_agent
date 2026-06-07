package com.example.mathagent

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
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MathAgentModuleTest {

    @Test
    fun packageName_isStable() {
        assertEquals("com.example.mathagent", MainActivity::class.java.`package`?.name)
    }

    @Test
    fun material_defaultValues() {
        val m = Material(title = "Test")
        assertEquals("Test", m.title)
        assertEquals("", m.subject)
        assertEquals(0L, m.id)
        assertTrue(m.createdAt > 0)
    }

    @Test
    fun errorEntry_defaultValues() {
        val e = ErrorEntry(question = "1+1=?")
        assertEquals("1+1=?", e.question)
        assertFalse(e.mastered)
        assertEquals(3, e.difficulty)
    }

    @Test
    fun studyPlan_defaultValues() {
        val p = StudyPlan(title = "复习高数")
        assertEquals("复习高数", p.title)
        assertFalse(p.completed)
    }

    @Test
    fun reviewRecord_defaultValues() {
        val r = ReviewRecord(errorEntryId = 1L)
        assertEquals(1L, r.errorEntryId)
        assertEquals(2.5f, r.easeFactor)
        assertEquals(0, r.repetitionCount)
    }

    @Test
    fun chatMessage_role() {
        val user = ChatMessage(role = "user", content = "你好")
        val assistant = ChatMessage(role = "assistant", content = "你好！")
        assertEquals("user", user.role)
        assertEquals("assistant", assistant.role)
    }

    @Test
    fun problemRecord_isCorrect() {
        val correct = ProblemRecord(question = "1+1", isCorrect = true, score = 10)
        val wrong = ProblemRecord(question = "1+1", isCorrect = false, score = 0)
        assertTrue(correct.isCorrect)
        assertFalse(wrong.isCorrect)
    }

    @Test
    fun examQuestion_defaultType() {
        val q = ExamQuestion(question = "选择题")
        assertEquals("single_choice", q.questionType)
        assertEquals(3, q.difficulty)
        assertEquals(1, q.points)
    }

    @Test
    fun examAttempt_scores() {
        val a = ExamAttempt(subject = "数学", totalScore = 85, maxScore = 100)
        assertEquals(85, a.totalScore)
        assertEquals(100, a.maxScore)
    }

    @Test
    fun appSetting_keyValue() {
        val s = com.example.mathagent.data.local.entity.AppSetting(key = "theme", value = "dark")
        assertEquals("theme", s.key)
        assertEquals("dark", s.value)
    }

    @Test
    fun backupLog_defaultType() {
        val b = BackupLog(fileName = "backup.db")
        assertEquals("manual", b.backupType)
        assertEquals("success", b.status)
    }

    @Test
    fun materialChunk_ordering() {
        val chunks = listOf(
            MaterialChunk(materialId = 1, chunkIndex = 2, content = "B"),
            MaterialChunk(materialId = 1, chunkIndex = 0, content = "A"),
            MaterialChunk(materialId = 1, chunkIndex = 1, content = "C")
        )
        val sorted = chunks.sortedBy { it.chunkIndex }
        assertEquals("A", sorted[0].content)
        assertEquals("C", sorted[1].content)
        assertEquals("B", sorted[2].content)
    }
}
