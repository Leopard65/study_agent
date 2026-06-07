package com.example.mathagent.data.ai

import com.example.mathagent.data.local.dao.ErrorEntryDao
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.repository.SettingsRepository

/**
 * Repository for AI-powered features.
 * API Key is always read from SecureSettingsStore, never from Room.
 *
 * @param clientFactory creates an [OpenAiClient] for each request; inject a test
 *                      factory (e.g. MockWebServer-backed) for unit tests.
 * @param chunkContextBuilder optional helper that appends local material chunk
 *                            context to the AI prompt.  Null = no chunk context.
 */
class AiRepository(
    private val settingsRepository: SettingsRepository,
    private val errorEntryDao: ErrorEntryDao,
    private val apiKeyProvider: suspend () -> String?,
    private val clientFactory: (baseUrl: String, apiKey: String, model: String) -> OpenAiClient =
        { baseUrl, apiKey, model -> OpenAiApi(baseUrl = baseUrl, apiKey = apiKey, model = model) },
    private val chunkContextBuilder: MaterialChunkContextBuilder? = null
) {
    /**
     * Check if AI is configured (API Key exists).
     * Does NOT check network connectivity.
     */
    suspend fun isAiConfigured(): Boolean {
        val key = apiKeyProvider()
        return !key.isNullOrBlank()
    }

    /**
     * Get AI configuration summary for display (never includes API Key).
     * Blank or null baseUrl/model are replaced with defaults.
     */
    suspend fun getConfigSummary(): AiConfigSummary {
        val key = apiKeyProvider()
        val baseUrl = resolveBaseUrl()
        val model = resolveModel()
        return AiConfigSummary(
            isConfigured = !key.isNullOrBlank(),
            baseUrl = baseUrl,
            model = model
        )
    }

    /**
     * Request AI analysis for an error entry.
     * @return analysis text from AI
     * @throws AiException if not configured or API call fails
     */
    suspend fun explainErrorEntry(errorEntryId: Long): String {
        val apiKey = apiKeyProvider()
        if (apiKey.isNullOrBlank()) {
            throw AiException("未配置 API Key，请在设置中配置", AiErrorType.NOT_CONFIGURED)
        }

        val entry = errorEntryDao.getById(errorEntryId)
            ?: throw IllegalArgumentException("错题不存在: $errorEntryId")

        val baseUrl = resolveBaseUrl()
        val model = resolveModel()

        val client = clientFactory(baseUrl, apiKey, model)

        // Append local chunk context if available (silent fallback on failure)
        val chunkContext = try {
            chunkContextBuilder?.buildContext(entry) ?: ""
        } catch (_: Exception) {
            ""
        }

        val messages = listOf(
            ChatMessage("system", SYSTEM_PROMPT + chunkContext),
            ChatMessage("user", buildPrompt(entry))
        )

        return client.chatCompletion(messages)
    }

    /**
     * Request AI analysis and save it to the error entry's analysis field.
     */
    suspend fun explainAndSave(errorEntryId: Long): String {
        val analysis = explainErrorEntry(errorEntryId)
        errorEntryDao.updateAnalysis(errorEntryId, analysis)
        return analysis
    }

    private suspend fun resolveBaseUrl(): String {
        val stored = settingsRepository.getBaseUrl()
        return if (stored.isNullOrBlank()) OpenAiApi.DEFAULT_BASE_URL else stored
    }

    private suspend fun resolveModel(): String {
        val stored = settingsRepository.getModel()
        return if (stored.isNullOrBlank()) OpenAiApi.DEFAULT_MODEL else stored
    }

    companion object {
        private const val SYSTEM_PROMPT =
            "你是一位耐心的数学老师。请分析学生做错的题目，用简洁的中文解释：\n" +
            "1. 这道题考查什么知识点\n" +
            "2. 学生的错误在哪里\n" +
            "3. 正确的解题思路\n" +
            "4. 类似题目的注意事项\n" +
            "请用 Markdown 格式回答，语言简洁明了。"

        internal fun buildPrompt(entry: ErrorEntry): String = buildString {
            appendLine("**题目：** ${entry.question}")
            if (entry.subject.isNotBlank()) appendLine("**科目：** ${entry.subject}")
            if (entry.chapter.isNotBlank()) appendLine("**章节：** ${entry.chapter}")
            if (entry.wrongAnswer.isNotBlank()) appendLine("**我的答案：** ${entry.wrongAnswer}")
            if (entry.correctAnswer.isNotBlank()) appendLine("**正确答案：** ${entry.correctAnswer}")
            if (entry.analysis.isNotBlank()) appendLine("**已有解析：** ${entry.analysis}")
            appendLine()
            appendLine("请分析这道题。")
        }
    }
}

data class AiConfigSummary(
    val isConfigured: Boolean,
    val baseUrl: String,
    val model: String
)
