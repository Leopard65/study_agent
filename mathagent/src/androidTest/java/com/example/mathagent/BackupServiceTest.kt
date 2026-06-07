package com.example.mathagent

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.mathagent.data.backup.BackupService
import com.example.mathagent.data.backup.ImportMode
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.entity.AppSetting
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
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class BackupServiceTest {

    private lateinit var db: MathAgentDatabase
    private lateinit var service: BackupService

    @Before
    fun setup() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        db = Room.inMemoryDatabaseBuilder(context, MathAgentDatabase::class.java)
            .allowMainThreadQueries().build()
        service = BackupService(db)
    }

    @After
    fun teardown() {
        db.close()
    }

    @Test
    fun export_doesNotContainApiKey() = runTest {
        db.appSettingDao().upsert(AppSetting(key = "ai_api_key", value = "sk-secret"))
        db.appSettingDao().upsert(AppSetting(key = "ai_base_url", value = "https://api.example.com"))

        val json = service.exportToJson()
        val root = JSONObject(json)
        val settings = root.getJSONObject("data").getJSONArray("app_settings")

        var hasApiKey = false
        for (i in 0 until settings.length()) {
            if (settings.getJSONObject(i).getString("key") == "ai_api_key") hasApiKey = true
        }
        assertFalse("API Key must not be in backup", hasApiKey)

        var hasBaseUrl = false
        for (i in 0 until settings.length()) {
            if (settings.getJSONObject(i).getString("key") == "ai_base_url") hasBaseUrl = true
        }
        assertTrue("Base URL should be in backup", hasBaseUrl)
    }

    @Test
    fun import_withApiKeyInJson_stripsIt() = runTest {
        val json = makeBackupJson(appSettings = listOf(
            mapOf("key" to "ai_api_key", "value" to "sk-stolen"),
            mapOf("key" to "ai_base_url", "value" to "https://api.example.com")
        ))

        service.importFromJson(json, ImportMode.REPLACE_ALL)

        assertNull("ai_api_key must not be imported", db.appSettingDao().getValue("ai_api_key"))
        assertEquals("https://api.example.com", db.appSettingDao().getValue("ai_base_url"))
    }

    @Test
    fun export_containsAllData() = runTest {
        db.errorEntryDao().insert(ErrorEntry(question = "Q1", subject = "Math"))
        db.studyPlanDao().insert(StudyPlan(title = "Plan1"))
        db.materialDao().insert(Material(title = "Mat1"))
        val matId = db.materialDao().getAllSync()[0].id
        db.materialChunkDao().insert(MaterialChunk(materialId = matId, chunkIndex = 0, content = "C1"))
        db.reviewRecordDao().insert(ReviewRecord(errorEntryId = 1))

        val json = service.exportToJson()
        val root = JSONObject(json)

        assertEquals(1, root.getInt("schemaVersion"))
        assertNotNull(root.getLong("exportedAt"))

        val data = root.getJSONObject("data")
        assertEquals(1, data.getJSONArray("error_entries").length())
        assertEquals(1, data.getJSONArray("study_plans").length())
        assertEquals(1, data.getJSONArray("materials").length())
        assertEquals(1, data.getJSONArray("material_chunks").length())
        assertEquals(1, data.getJSONArray("review_records").length())
    }

    @Test
    fun import_replaceAll_restoresData() = runTest {
        db.errorEntryDao().insert(ErrorEntry(question = "Original Q1"))
        db.studyPlanDao().insert(StudyPlan(title = "Original P1"))

        val exported = service.exportToJson()

        db.errorEntryDao().deleteAllSync()
        db.studyPlanDao().deleteAllSync()
        assertEquals(0, db.errorEntryDao().getAllSync().size)

        val count = service.importFromJson(exported, ImportMode.REPLACE_ALL)
        assertTrue(count > 0)

        assertEquals(1, db.errorEntryDao().getAllSync().size)
        assertEquals("Original Q1", db.errorEntryDao().getAllSync()[0].question)
        assertEquals(1, db.studyPlanDao().getAllSync().size)
    }

    @Test
    fun import_mergeSkipExisting_errorEntry_doesNotOverwrite() = runTest {
        db.errorEntryDao().insert(ErrorEntry(id = 0, question = "Existing Q"))
        val existingId = db.errorEntryDao().getAllSync()[0].id

        val json = makeBackupJson(
            errorEntries = listOf(
                mapOf("id" to existingId, "question" to "Overwritten Q"),
                mapOf("id" to 9999L, "question" to "New Q")
            )
        )

        service.importFromJson(json, ImportMode.MERGE_SKIP_EXISTING)

        val all = db.errorEntryDao().getAllSync()
        assertEquals("Existing Q", all.find { it.id == existingId }!!.question)
        assertEquals("New Q", all.find { it.id == 9999L }!!.question)
    }

    @Test
    fun import_mergeSkipExisting_materialChunk_doesNotOverwrite() = runTest {
        db.materialDao().insert(Material(title = "Parent"))
        val matId = db.materialDao().getAllSync()[0].id
        db.materialChunkDao().insert(MaterialChunk(materialId = matId, chunkIndex = 0, content = "Original"))
        val chunkId = db.materialChunkDao().getAllSync()[0].id

        val json = makeBackupJson(materialChunks = listOf(
            mapOf("id" to chunkId, "materialId" to matId, "chunkIndex" to 0, "content" to "Overwritten")
        ))

        service.importFromJson(json, ImportMode.MERGE_SKIP_EXISTING)

        assertEquals("Original", db.materialChunkDao().getById(chunkId)!!.content)
    }

    @Test
    fun import_mergeSkipExisting_chatMessage_doesNotOverwrite() = runTest {
        db.chatMessageDao().insert(ChatMessage(role = "user", content = "Original"))
        val msgId = db.chatMessageDao().getAllSync()[0].id

        val json = makeBackupJson(chatMessages = listOf(
            mapOf("id" to msgId, "role" to "user", "content" to "Overwritten")
        ))

        service.importFromJson(json, ImportMode.MERGE_SKIP_EXISTING)

        assertEquals("Original", db.chatMessageDao().getById(msgId)!!.content)
    }

    @Test
    fun import_mergeSkipExisting_problemRecord_doesNotOverwrite() = runTest {
        db.problemRecordDao().insert(ProblemRecord(question = "Original Q"))
        val recId = db.problemRecordDao().getAllSync()[0].id

        val json = makeBackupJson(problemRecords = listOf(
            mapOf("id" to recId, "question" to "Overwritten Q")
        ))

        service.importFromJson(json, ImportMode.MERGE_SKIP_EXISTING)

        assertEquals("Original Q", db.problemRecordDao().getById(recId)!!.question)
    }

    @Test
    fun import_mergeSkipExisting_examQuestion_doesNotOverwrite() = runTest {
        db.examQuestionDao().insert(ExamQuestion(question = "Original Q"))
        val qId = db.examQuestionDao().getAllSync()[0].id

        val json = makeBackupJson(examQuestions = listOf(
            mapOf("id" to qId, "question" to "Overwritten Q")
        ))

        service.importFromJson(json, ImportMode.MERGE_SKIP_EXISTING)

        assertEquals("Original Q", db.examQuestionDao().getById(qId)!!.question)
    }

    @Test
    fun import_mergeSkipExisting_examAttempt_doesNotOverwrite() = runTest {
        db.examAttemptDao().insert(ExamAttempt(subject = "Math", totalScore = 80))
        val attId = db.examAttemptDao().getAllSync()[0].id

        val json = makeBackupJson(examAttempts = listOf(
            mapOf("id" to attId, "subject" to "Math", "totalScore" to 100)
        ))

        service.importFromJson(json, ImportMode.MERGE_SKIP_EXISTING)

        assertEquals(80, db.examAttemptDao().getById(attId)!!.totalScore)
    }

    @Test
    fun import_mergeSkipExisting_appSetting_doesNotOverwrite() = runTest {
        db.appSettingDao().upsert(AppSetting(key = "ai_base_url", value = "https://original.com"))

        val json = makeBackupJson(appSettings = listOf(
            mapOf("key" to "ai_base_url", "value" to "https://overwritten.com")
        ))

        service.importFromJson(json, ImportMode.MERGE_SKIP_EXISTING)

        assertEquals("https://original.com", db.appSettingDao().getValue("ai_base_url"))
    }

    @Test
    fun import_unknownSchemaVersion_failsAndRollsBack() = runTest {
        db.errorEntryDao().insert(ErrorEntry(question = "Before"))

        val json = JSONObject().apply {
            put("schemaVersion", 999)
            put("exportedAt", System.currentTimeMillis())
            put("appVersion", "1.0")
            put("data", JSONObject())
        }.toString()

        try {
            service.importFromJson(json, ImportMode.REPLACE_ALL)
            fail("Should throw for unknown schema version")
        } catch (e: IllegalArgumentException) {
            assertTrue(e.message!!.contains("不支持的备份版本"))
        }

        assertEquals(1, db.errorEntryDao().getAllSync().size)
        assertEquals("Before", db.errorEntryDao().getAllSync()[0].question)
    }

    @Test
    fun import_invalidJson_throwsAndRollsBack() = runTest {
        db.errorEntryDao().insert(ErrorEntry(question = "Before"))

        try {
            service.importFromJson("not valid json", ImportMode.REPLACE_ALL)
            fail("Should throw")
        } catch (e: IllegalArgumentException) {
            assertTrue(e.message!!.contains("无效的 JSON"))
        }

        assertEquals(1, db.errorEntryDao().getAllSync().size)
    }

    @Test
    fun import_missingDataObject_failsAndRollsBack() = runTest {
        db.errorEntryDao().insert(ErrorEntry(question = "Existing data"))

        val json = JSONObject().apply {
            put("schemaVersion", 1)
            put("exportedAt", System.currentTimeMillis())
            put("appVersion", "1.0")
            // No "data" key at all
        }.toString()

        try {
            service.importFromJson(json, ImportMode.REPLACE_ALL)
            fail("Should throw for missing data object")
        } catch (e: IllegalArgumentException) {
            assertTrue(e.message!!.contains("data"))
        }

        // Original data must survive (transaction never started)
        val all = db.errorEntryDao().getAllSync()
        assertEquals(1, all.size)
        assertEquals("Existing data", all[0].question)
    }

    @Test
    fun import_missingArrays_handledAsEmpty() = runTest {
        val json = JSONObject().apply {
            put("schemaVersion", 1)
            put("exportedAt", System.currentTimeMillis())
            put("appVersion", "1.0")
            put("data", JSONObject().apply {
                put("error_entries", JSONArray().apply {
                    put(JSONObject().apply {
                        put("id", 1); put("question", "Q"); put("subject", "")
                        put("chapter", ""); put("wrongAnswer", ""); put("correctAnswer", "")
                        put("analysis", ""); put("difficulty", 3); put("mastered", false)
                        put("createdAt", 0); put("updatedAt", 0)
                    })
                })
            })
        }.toString()

        val count = service.importFromJson(json, ImportMode.REPLACE_ALL)
        assertEquals(1, count)
    }

    @Test
    fun import_foreignKeyChild_skipsIfParentMissing() = runTest {
        val json = makeBackupJson(
            reviewRecords = listOf(
                mapOf("id" to 1L, "errorEntryId" to 999L, "intervalDays" to 1)
            )
        )

        service.importFromJson(json, ImportMode.REPLACE_ALL)
        assertEquals(0, db.reviewRecordDao().getAllSync().size)
    }

    // ---- Backup semantics: materials with filePath ----

    @Test
    fun import_materialWithFilePath_clearsFilePath() = runTest {
        val json = makeBackupJson(
            materials = listOf(
                mapOf(
                    "id" to 100L,
                    "title" to "Imported Doc",
                    "subject" to "Math",
                    "filePath" to "materials/some_old_file.txt",
                    "fileType" to "text/plain",
                    "fileSize" to 1234L
                )
            )
        )

        service.importFromJson(json, ImportMode.REPLACE_ALL)

        val imported = db.materialDao().getById(100L)
        assertNotNull(imported)
        assertEquals("Imported Doc", imported!!.title)
        assertEquals(
            "filePath must be cleared on import (device-specific path)",
            "", imported.filePath
        )
    }

    @Test
    fun import_materialWithEmptyFilePath_staysEmpty() = runTest {
        val json = makeBackupJson(
            materials = listOf(
                mapOf("id" to 200L, "title" to "Manual Entry", "filePath" to "")
            )
        )

        service.importFromJson(json, ImportMode.REPLACE_ALL)

        val imported = db.materialDao().getById(200L)
        assertNotNull(imported)
        assertEquals("", imported!!.filePath)
    }

    @Test
    fun import_materialChunks_restoredWithParent() = runTest {
        val json = makeBackupJson(
            materials = listOf(
                mapOf("id" to 300L, "title" to "Parent Doc", "filePath" to "materials/parent.txt")
            ),
            materialChunks = listOf(
                mapOf("id" to 3001L, "materialId" to 300L, "chunkIndex" to 0, "content" to "First chunk"),
                mapOf("id" to 3002L, "materialId" to 300L, "chunkIndex" to 1, "content" to "Second chunk")
            )
        )

        service.importFromJson(json, ImportMode.REPLACE_ALL)

        // Material parent exists with cleared filePath
        val parent = db.materialDao().getById(300L)
        assertNotNull("Parent material must exist", parent)
        assertEquals("", parent!!.filePath)

        // Chunks are restored
        val chunks = db.materialChunkDao().getAllSync().filter { it.materialId == 300L }
        assertEquals(2, chunks.size)
        assertEquals("First chunk", chunks[0].content)
        assertEquals("Second chunk", chunks[1].content)
    }

    @Test
    fun import_materialChunk_skippedIfParentMissing() = runTest {
        val json = makeBackupJson(
            materialChunks = listOf(
                mapOf("id" to 4001L, "materialId" to 9999L, "chunkIndex" to 0, "content" to "Orphan chunk")
            )
        )

        service.importFromJson(json, ImportMode.REPLACE_ALL)

        val chunks = db.materialChunkDao().getAllSync()
        assertEquals(0, chunks.size)
    }

    @Test
    fun export_containsMaterialsWithFilePath() = runTest {
        db.materialDao().insert(Material(title = "Test Doc", filePath = "materials/test.txt"))
        val matId = db.materialDao().getAllSync()[0].id
        db.materialChunkDao().insert(MaterialChunk(materialId = matId, chunkIndex = 0, content = "chunk"))

        val json = service.exportToJson()
        val root = JSONObject(json)
        val materials = root.getJSONObject("data").getJSONArray("materials")

        assertEquals(1, materials.length())
        assertEquals("materials/test.txt", materials.getJSONObject(0).getString("filePath"))
    }

    @Test
    fun import_replaceAll_materialsRoundTrip() = runTest {
        // Insert material with chunks
        val matId = db.materialDao().insert(Material(title = "Round Trip", filePath = "materials/rt.txt"))
        db.materialChunkDao().insert(MaterialChunk(materialId = matId, chunkIndex = 0, content = "RT chunk"))

        // Export
        val exported = service.exportToJson()

        // Clear DB
        db.materialChunkDao().deleteAllSync()
        db.materialDao().deleteAllSync()
        assertEquals(0, db.materialDao().getAllSync().size)

        // Import
        val count = service.importFromJson(exported, ImportMode.REPLACE_ALL)
        assertTrue(count > 0)

        // Verify material restored with cleared filePath
        val restored = db.materialDao().getAllSync()
        assertEquals(1, restored.size)
        assertEquals("Round Trip", restored[0].title)
        assertEquals(
            "filePath should be cleared on import",
            "", restored[0].filePath
        )

        // Verify chunks restored
        val chunks = db.materialChunkDao().getByMaterialId(restored[0].id)
        assertEquals(1, chunks.first().size)
        assertEquals("RT chunk", chunks.first()[0].content)
    }

    @Test
    fun import_mergeSkipExisting_material_doesNotOverwrite() = runTest {
        db.materialDao().insert(Material(id = 500, title = "Existing Mat"))
        val existing = db.materialDao().getById(500L)!!

        val json = makeBackupJson(
            materials = listOf(
                mapOf("id" to 500L, "title" to "Overwritten Mat"),
                mapOf("id" to 501L, "title" to "New Mat")
            )
        )

        service.importFromJson(json, ImportMode.MERGE_SKIP_EXISTING)

        assertEquals("Existing Mat", db.materialDao().getById(500L)!!.title)
        assertEquals("New Mat", db.materialDao().getById(501L)!!.title)
    }

    // ---- Helpers ----

    private fun makeBackupJson(
        materials: List<Map<String, Any>> = emptyList(),
        errorEntries: List<Map<String, Any>> = emptyList(),
        reviewRecords: List<Map<String, Any>> = emptyList(),
        materialChunks: List<Map<String, Any>> = emptyList(),
        chatMessages: List<Map<String, Any>> = emptyList(),
        problemRecords: List<Map<String, Any>> = emptyList(),
        examQuestions: List<Map<String, Any>> = emptyList(),
        examAttempts: List<Map<String, Any>> = emptyList(),
        appSettings: List<Map<String, Any>> = emptyList()
    ): String {
        val root = JSONObject()
        root.put("schemaVersion", 1)
        root.put("exportedAt", System.currentTimeMillis())
        root.put("appVersion", "1.0")

        val data = JSONObject()
        data.put("materials", toArr(materials) { m ->
            JSONObject().apply {
                put("id", m.getOrDefault("id", 0L)); put("title", m.getOrDefault("title", ""))
                put("subject", m.getOrDefault("subject", "")); put("filePath", m.getOrDefault("filePath", ""))
                put("fileType", m.getOrDefault("fileType", "")); put("fileSize", m.getOrDefault("fileSize", 0L))
                put("description", m.getOrDefault("description", ""))
                put("createdAt", m.getOrDefault("createdAt", 0L)); put("updatedAt", m.getOrDefault("updatedAt", 0L))
            }
        })
        data.put("error_entries", toArr(errorEntries) { m ->
            JSONObject().apply {
                put("id", m.getOrDefault("id", 0L)); put("question", m.getOrDefault("question", ""))
                put("subject", m.getOrDefault("subject", "")); put("chapter", m.getOrDefault("chapter", ""))
                put("wrongAnswer", m.getOrDefault("wrongAnswer", "")); put("correctAnswer", m.getOrDefault("correctAnswer", ""))
                put("analysis", m.getOrDefault("analysis", "")); put("difficulty", m.getOrDefault("difficulty", 3))
                put("mastered", m.getOrDefault("mastered", false))
                put("createdAt", m.getOrDefault("createdAt", 0L)); put("updatedAt", m.getOrDefault("updatedAt", 0L))
            }
        })
        data.put("review_records", toArr(reviewRecords) { m ->
            JSONObject().apply {
                put("id", m.getOrDefault("id", 0L)); put("errorEntryId", m.getOrDefault("errorEntryId", 0L))
                put("nextReviewAt", m.getOrDefault("nextReviewAt", 0L)); put("intervalDays", m.getOrDefault("intervalDays", 1))
                put("easeFactor", (m.getOrDefault("easeFactor", 2.5) as Number).toDouble())
                put("repetitionCount", m.getOrDefault("repetitionCount", 0))
                put("lastReviewedAt", m.getOrDefault("lastReviewedAt", 0L)); put("createdAt", m.getOrDefault("createdAt", 0L))
            }
        })
        data.put("material_chunks", toArr(materialChunks) { m ->
            JSONObject().apply {
                put("id", m.getOrDefault("id", 0L)); put("materialId", m.getOrDefault("materialId", 0L))
                put("chunkIndex", m.getOrDefault("chunkIndex", 0)); put("content", m.getOrDefault("content", ""))
                put("embedding", m.getOrDefault("embedding", ""))
            }
        })
        data.put("study_plans", JSONArray())
        data.put("chat_messages", toArr(chatMessages) { m ->
            JSONObject().apply {
                put("id", m.getOrDefault("id", 0L)); put("role", m.getOrDefault("role", ""))
                put("content", m.getOrDefault("content", "")); put("subject", m.getOrDefault("subject", ""))
                put("tokenCount", m.getOrDefault("tokenCount", 0)); put("createdAt", m.getOrDefault("createdAt", 0L))
            }
        })
        data.put("problem_records", toArr(problemRecords) { m ->
            JSONObject().apply {
                put("id", m.getOrDefault("id", 0L)); put("subject", m.getOrDefault("subject", ""))
                put("chapter", m.getOrDefault("chapter", "")); put("question", m.getOrDefault("question", ""))
                put("userAnswer", m.getOrDefault("userAnswer", "")); put("correctAnswer", m.getOrDefault("correctAnswer", ""))
                put("isCorrect", m.getOrDefault("isCorrect", false)); put("score", m.getOrDefault("score", 0))
                put("timeSpentSeconds", m.getOrDefault("timeSpentSeconds", 0)); put("createdAt", m.getOrDefault("createdAt", 0L))
            }
        })
        data.put("exam_questions", toArr(examQuestions) { m ->
            JSONObject().apply {
                put("id", m.getOrDefault("id", 0L)); put("subject", m.getOrDefault("subject", ""))
                put("chapter", m.getOrDefault("chapter", ""))
                put("questionType", m.getOrDefault("questionType", "single_choice"))
                put("question", m.getOrDefault("question", "")); put("options", m.getOrDefault("options", ""))
                put("answer", m.getOrDefault("answer", "")); put("analysis", m.getOrDefault("analysis", ""))
                put("difficulty", m.getOrDefault("difficulty", 3)); put("points", m.getOrDefault("points", 1))
                put("createdAt", m.getOrDefault("createdAt", 0L))
            }
        })
        data.put("exam_attempts", toArr(examAttempts) { m ->
            JSONObject().apply {
                put("id", m.getOrDefault("id", 0L)); put("subject", m.getOrDefault("subject", ""))
                put("totalScore", m.getOrDefault("totalScore", 0)); put("maxScore", m.getOrDefault("maxScore", 0))
                put("durationSeconds", m.getOrDefault("durationSeconds", 0))
                put("questionIds", m.getOrDefault("questionIds", "")); put("answers", m.getOrDefault("answers", ""))
                put("createdAt", m.getOrDefault("createdAt", 0L))
            }
        })
        data.put("app_settings", toArr(appSettings) { m ->
            JSONObject().apply {
                put("key", m["key"]!!); put("value", m.getOrDefault("value", ""))
                put("updatedAt", m.getOrDefault("updatedAt", 0L))
            }
        })

        root.put("data", data)
        return root.toString()
    }

    private fun <T> toArr(list: List<T>, transform: (T) -> JSONObject): JSONArray {
        val arr = JSONArray()
        list.forEach { arr.put(transform(it)) }
        return arr
    }
}
