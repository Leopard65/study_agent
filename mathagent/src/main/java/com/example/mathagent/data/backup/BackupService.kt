package com.example.mathagent.data.backup

import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.entity.AppSetting
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
import androidx.room.withTransaction
import org.json.JSONArray
import org.json.JSONObject

enum class ImportMode {
    REPLACE_ALL,
    MERGE_SKIP_EXISTING
}

data class BackupData(
    val schemaVersion: Int = 1,
    val exportedAt: Long = System.currentTimeMillis(),
    val appVersion: String = "1.0",
    val materials: List<Material> = emptyList(),
    val materialChunks: List<MaterialChunk> = emptyList(),
    val errorEntries: List<ErrorEntry> = emptyList(),
    val reviewRecords: List<ReviewRecord> = emptyList(),
    val studyPlans: List<StudyPlan> = emptyList(),
    val chatMessages: List<ChatMessage> = emptyList(),
    val problemRecords: List<ProblemRecord> = emptyList(),
    val examQuestions: List<ExamQuestion> = emptyList(),
    val examAttempts: List<ExamAttempt> = emptyList(),
    val appSettings: List<AppSetting> = emptyList()
)

class BackupService(private val database: MathAgentDatabase) {

    suspend fun exportToJson(): String {
        val data = BackupData(
            materials = database.materialDao().getAllSync(),
            materialChunks = database.materialChunkDao().getAllSync(),
            errorEntries = database.errorEntryDao().getAllSync(),
            reviewRecords = database.reviewRecordDao().getAllSync(),
            studyPlans = database.studyPlanDao().getAllSync(),
            chatMessages = database.chatMessageDao().getAllSync(),
            problemRecords = database.problemRecordDao().getAllSync(),
            examQuestions = database.examQuestionDao().getAllSync(),
            examAttempts = database.examAttemptDao().getAllSync(),
            appSettings = database.appSettingDao().getAllSync()
                .filter { it.key != KEY_API_KEY }
        )
        return serialize(data).toString()
    }

    suspend fun importFromJson(json: String, mode: ImportMode): Int {
        val root = try { JSONObject(json) } catch (e: Exception) {
            throw IllegalArgumentException("无效的 JSON 格式", e)
        }

        val version = root.optInt("schemaVersion", 0)
        if (version != CURRENT_SCHEMA_VERSION) {
            throw IllegalArgumentException("不支持的备份版本: $version (当前: $CURRENT_SCHEMA_VERSION)")
        }

        val dataObj = root.opt("data")
        if (dataObj !is JSONObject) {
            throw IllegalArgumentException("备份文件缺少 data 对象")
        }

        val data = deserialize(root, dataObj)
        // Always strip ai_api_key from imported settings
        val safeSettings = data.appSettings.filter { it.key != KEY_API_KEY }
        var count = 0

        database.withTransaction {
            if (mode == ImportMode.REPLACE_ALL) {
                database.chatMessageDao().deleteAll()
                database.problemRecordDao().deleteAllSync()
                database.examAttemptDao().deleteAllSync()
                database.examQuestionDao().deleteAllSync()
                database.reviewRecordDao().deleteAllSync()
                database.errorEntryDao().deleteAllSync()
                database.materialChunkDao().deleteAllSync()
                database.materialDao().deleteAllSync()
                database.studyPlanDao().deleteAllSync()
                database.appSettingDao().deleteAll()
            }

            // Parent tables first
            for (m in data.materials) {
                if (mode == ImportMode.MERGE_SKIP_EXISTING && database.materialDao().getById(m.id) != null) continue
                // Clear filePath — the backed-up file path is from the exporting device
                // and will not exist on this device.  Chunks are preserved for search,
                // material detail display, and AI context retrieval.
                database.materialDao().insert(m.copy(filePath = ""))
                count++
            }
            for (e in data.errorEntries) {
                if (mode == ImportMode.MERGE_SKIP_EXISTING && database.errorEntryDao().getById(e.id) != null) continue
                database.errorEntryDao().insert(e)
                count++
            }
            for (p in data.studyPlans) {
                if (mode == ImportMode.MERGE_SKIP_EXISTING && database.studyPlanDao().getById(p.id) != null) continue
                database.studyPlanDao().insert(p)
                count++
            }

            // Child tables — verify parent exists
            for (c in data.materialChunks) {
                if (database.materialDao().getById(c.materialId) == null) continue
                if (mode == ImportMode.MERGE_SKIP_EXISTING && database.materialChunkDao().getById(c.id) != null) continue
                database.materialChunkDao().insert(c)
                count++
            }
            for (r in data.reviewRecords) {
                if (database.errorEntryDao().getById(r.errorEntryId) == null) continue
                if (mode == ImportMode.MERGE_SKIP_EXISTING && database.reviewRecordDao().getById(r.id) != null) continue
                database.reviewRecordDao().insert(r)
                count++
            }

            // Independent tables
            for (m in data.chatMessages) {
                if (mode == ImportMode.MERGE_SKIP_EXISTING && database.chatMessageDao().getById(m.id) != null) continue
                database.chatMessageDao().insert(m)
                count++
            }
            for (p in data.problemRecords) {
                if (mode == ImportMode.MERGE_SKIP_EXISTING && database.problemRecordDao().getById(p.id) != null) continue
                database.problemRecordDao().insert(p)
                count++
            }
            for (q in data.examQuestions) {
                if (mode == ImportMode.MERGE_SKIP_EXISTING && database.examQuestionDao().getById(q.id) != null) continue
                database.examQuestionDao().insert(q)
                count++
            }
            for (a in data.examAttempts) {
                if (mode == ImportMode.MERGE_SKIP_EXISTING && database.examAttemptDao().getById(a.id) != null) continue
                database.examAttemptDao().insert(a)
                count++
            }
            for (s in safeSettings) {
                if (mode == ImportMode.MERGE_SKIP_EXISTING && database.appSettingDao().get(s.key) != null) continue
                database.appSettingDao().upsert(s)
                count++
            }
        }

        return count
    }

    companion object {
        const val CURRENT_SCHEMA_VERSION = 1
        private const val KEY_API_KEY = "ai_api_key"

        private fun serialize(data: BackupData): JSONObject {
            val json = JSONObject()
            json.put("schemaVersion", data.schemaVersion)
            json.put("exportedAt", data.exportedAt)
            json.put("appVersion", data.appVersion)

            val d = JSONObject()
            d.put("materials", toJsonArray(data.materials) { materialToJson(it) })
            d.put("material_chunks", toJsonArray(data.materialChunks) { materialChunkToJson(it) })
            d.put("error_entries", toJsonArray(data.errorEntries) { errorEntryToJson(it) })
            d.put("review_records", toJsonArray(data.reviewRecords) { reviewRecordToJson(it) })
            d.put("study_plans", toJsonArray(data.studyPlans) { studyPlanToJson(it) })
            d.put("chat_messages", toJsonArray(data.chatMessages) { chatMessageToJson(it) })
            d.put("problem_records", toJsonArray(data.problemRecords) { problemRecordToJson(it) })
            d.put("exam_questions", toJsonArray(data.examQuestions) { examQuestionToJson(it) })
            d.put("exam_attempts", toJsonArray(data.examAttempts) { examAttemptToJson(it) })
            d.put("app_settings", toJsonArray(data.appSettings) { appSettingToJson(it) })
            json.put("data", d)

            return json
        }

        private fun deserialize(root: JSONObject, data: JSONObject): BackupData {
            return BackupData(
                schemaVersion = root.optInt("schemaVersion", 0),
                exportedAt = root.optLong("exportedAt", 0),
                appVersion = root.optString("appVersion", "unknown"),
                materials = optJsonArray(data, "materials") { materialFromJson(it) },
                materialChunks = optJsonArray(data, "material_chunks") { materialChunkFromJson(it) },
                errorEntries = optJsonArray(data, "error_entries") { errorEntryFromJson(it) },
                reviewRecords = optJsonArray(data, "review_records") { reviewRecordFromJson(it) },
                studyPlans = optJsonArray(data, "study_plans") { studyPlanFromJson(it) },
                chatMessages = optJsonArray(data, "chat_messages") { chatMessageFromJson(it) },
                problemRecords = optJsonArray(data, "problem_records") { problemRecordFromJson(it) },
                examQuestions = optJsonArray(data, "exam_questions") { examQuestionFromJson(it) },
                examAttempts = optJsonArray(data, "exam_attempts") { examAttemptFromJson(it) },
                appSettings = optJsonArray(data, "app_settings") { appSettingFromJson(it) }
            )
        }

        private fun <T> toJsonArray(list: List<T>, toObj: (T) -> JSONObject): JSONArray {
            val arr = JSONArray()
            list.forEach { arr.put(toObj(it)) }
            return arr
        }

        private fun <T> fromJsonArray(arr: JSONArray, fromObj: (JSONObject) -> T): List<T> {
            val list = mutableListOf<T>()
            for (i in 0 until arr.length()) list.add(fromObj(arr.getJSONObject(i)))
            return list
        }

        /** Safe: missing arrays default to empty list. */
        private fun <T> optJsonArray(obj: JSONObject, key: String, fromObj: (JSONObject) -> T): List<T> {
            val arr = obj.optJSONArray(key) ?: return emptyList()
            return fromJsonArray(arr, fromObj)
        }

        private fun materialToJson(m: Material) = JSONObject().apply {
            put("id", m.id); put("title", m.title); put("subject", m.subject)
            put("filePath", m.filePath); put("fileType", m.fileType); put("fileSize", m.fileSize)
            put("description", m.description); put("createdAt", m.createdAt); put("updatedAt", m.updatedAt)
        }
        private fun materialFromJson(j: JSONObject) = Material(
            id = j.getLong("id"), title = j.getString("title"), subject = j.optString("subject", ""),
            filePath = j.optString("filePath", ""), fileType = j.optString("fileType", ""),
            fileSize = j.optLong("fileSize", 0), description = j.optString("description", ""),
            createdAt = j.optLong("createdAt", 0), updatedAt = j.optLong("updatedAt", 0)
        )

        private fun materialChunkToJson(c: MaterialChunk) = JSONObject().apply {
            put("id", c.id); put("materialId", c.materialId); put("chunkIndex", c.chunkIndex)
            put("content", c.content); put("embedding", c.embedding)
        }
        private fun materialChunkFromJson(j: JSONObject) = MaterialChunk(
            id = j.getLong("id"), materialId = j.getLong("materialId"),
            chunkIndex = j.getInt("chunkIndex"), content = j.getString("content"),
            embedding = j.optString("embedding", "")
        )

        private fun errorEntryToJson(e: ErrorEntry) = JSONObject().apply {
            put("id", e.id); put("subject", e.subject); put("chapter", e.chapter)
            put("question", e.question); put("wrongAnswer", e.wrongAnswer)
            put("correctAnswer", e.correctAnswer); put("analysis", e.analysis)
            put("difficulty", e.difficulty); put("mastered", e.mastered)
            put("createdAt", e.createdAt); put("updatedAt", e.updatedAt)
        }
        private fun errorEntryFromJson(j: JSONObject) = ErrorEntry(
            id = j.getLong("id"), subject = j.optString("subject", ""),
            chapter = j.optString("chapter", ""), question = j.getString("question"),
            wrongAnswer = j.optString("wrongAnswer", ""), correctAnswer = j.optString("correctAnswer", ""),
            analysis = j.optString("analysis", ""), difficulty = j.optInt("difficulty", 3),
            mastered = j.optBoolean("mastered", false),
            createdAt = j.optLong("createdAt", 0), updatedAt = j.optLong("updatedAt", 0)
        )

        private fun reviewRecordToJson(r: ReviewRecord) = JSONObject().apply {
            put("id", r.id); put("errorEntryId", r.errorEntryId); put("nextReviewAt", r.nextReviewAt)
            put("intervalDays", r.intervalDays); put("easeFactor", r.easeFactor.toDouble())
            put("repetitionCount", r.repetitionCount); put("lastReviewedAt", r.lastReviewedAt)
            put("createdAt", r.createdAt)
        }
        private fun reviewRecordFromJson(j: JSONObject) = ReviewRecord(
            id = j.getLong("id"), errorEntryId = j.getLong("errorEntryId"),
            nextReviewAt = j.optLong("nextReviewAt", 0), intervalDays = j.optInt("intervalDays", 1),
            easeFactor = j.optDouble("easeFactor", 2.5).toFloat(),
            repetitionCount = j.optInt("repetitionCount", 0),
            lastReviewedAt = j.optLong("lastReviewedAt", 0), createdAt = j.optLong("createdAt", 0)
        )

        private fun studyPlanToJson(p: StudyPlan) = JSONObject().apply {
            put("id", p.id); put("title", p.title); put("subject", p.subject)
            put("description", p.description); put("targetDate", p.targetDate)
            put("completed", p.completed); put("createdAt", p.createdAt); put("updatedAt", p.updatedAt)
        }
        private fun studyPlanFromJson(j: JSONObject) = StudyPlan(
            id = j.getLong("id"), title = j.getString("title"), subject = j.optString("subject", ""),
            description = j.optString("description", ""), targetDate = j.optLong("targetDate", 0),
            completed = j.optBoolean("completed", false),
            createdAt = j.optLong("createdAt", 0), updatedAt = j.optLong("updatedAt", 0)
        )

        private fun chatMessageToJson(m: ChatMessage) = JSONObject().apply {
            put("id", m.id); put("role", m.role); put("content", m.content)
            put("subject", m.subject); put("tokenCount", m.tokenCount); put("createdAt", m.createdAt)
        }
        private fun chatMessageFromJson(j: JSONObject) = ChatMessage(
            id = j.getLong("id"), role = j.getString("role"), content = j.getString("content"),
            subject = j.optString("subject", ""), tokenCount = j.optInt("tokenCount", 0),
            createdAt = j.optLong("createdAt", 0)
        )

        private fun problemRecordToJson(p: ProblemRecord) = JSONObject().apply {
            put("id", p.id); put("subject", p.subject); put("chapter", p.chapter)
            put("question", p.question); put("userAnswer", p.userAnswer); put("correctAnswer", p.correctAnswer)
            put("isCorrect", p.isCorrect); put("score", p.score)
            put("timeSpentSeconds", p.timeSpentSeconds); put("createdAt", p.createdAt)
        }
        private fun problemRecordFromJson(j: JSONObject) = ProblemRecord(
            id = j.getLong("id"), subject = j.optString("subject", ""),
            chapter = j.optString("chapter", ""), question = j.getString("question"),
            userAnswer = j.optString("userAnswer", ""), correctAnswer = j.optString("correctAnswer", ""),
            isCorrect = j.optBoolean("isCorrect", false), score = j.optInt("score", 0),
            timeSpentSeconds = j.optInt("timeSpentSeconds", 0), createdAt = j.optLong("createdAt", 0)
        )

        private fun examQuestionToJson(q: ExamQuestion) = JSONObject().apply {
            put("id", q.id); put("subject", q.subject); put("chapter", q.chapter)
            put("questionType", q.questionType); put("question", q.question)
            put("options", q.options); put("answer", q.answer); put("analysis", q.analysis)
            put("difficulty", q.difficulty); put("points", q.points); put("createdAt", q.createdAt)
        }
        private fun examQuestionFromJson(j: JSONObject) = ExamQuestion(
            id = j.getLong("id"), subject = j.optString("subject", ""),
            chapter = j.optString("chapter", ""),
            questionType = j.optString("questionType", "single_choice"),
            question = j.getString("question"), options = j.optString("options", ""),
            answer = j.optString("answer", ""), analysis = j.optString("analysis", ""),
            difficulty = j.optInt("difficulty", 3), points = j.optInt("points", 1),
            createdAt = j.optLong("createdAt", 0)
        )

        private fun examAttemptToJson(a: ExamAttempt) = JSONObject().apply {
            put("id", a.id); put("subject", a.subject); put("totalScore", a.totalScore)
            put("maxScore", a.maxScore); put("durationSeconds", a.durationSeconds)
            put("questionIds", a.questionIds); put("answers", a.answers); put("createdAt", a.createdAt)
        }
        private fun examAttemptFromJson(j: JSONObject) = ExamAttempt(
            id = j.getLong("id"), subject = j.optString("subject", ""),
            totalScore = j.optInt("totalScore", 0), maxScore = j.optInt("maxScore", 0),
            durationSeconds = j.optInt("durationSeconds", 0),
            questionIds = j.optString("questionIds", ""), answers = j.optString("answers", ""),
            createdAt = j.optLong("createdAt", 0)
        )

        private fun appSettingToJson(s: AppSetting) = JSONObject().apply {
            put("key", s.key); put("value", s.value); put("updatedAt", s.updatedAt)
        }
        private fun appSettingFromJson(j: JSONObject) = AppSetting(
            key = j.getString("key"), value = j.optString("value", ""),
            updatedAt = j.optLong("updatedAt", 0)
        )
    }
}
