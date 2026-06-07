package com.example.mathagent

import com.example.mathagent.data.ai.AiErrorType
import com.example.mathagent.data.ai.AiException
import com.example.mathagent.data.ai.AiRepository
import com.example.mathagent.data.ai.ChatMessage
import com.example.mathagent.data.ai.MaterialChunkContextBuilder
import com.example.mathagent.data.ai.OpenAiApi
import com.example.mathagent.data.ai.OpenAiClient
import com.example.mathagent.data.local.dao.ErrorEntryDao
import com.example.mathagent.data.local.dao.MaterialChunkDao
import com.example.mathagent.data.local.dao.MaterialDao
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.local.entity.MaterialChunk
import com.example.mathagent.data.repository.SettingsRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AiRepositoryTest {

    @Before
    fun setup() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
    }

    @After
    fun teardown() {
        Dispatchers.resetMain()
    }

    private class FakeErrorEntryDao(
        private val entries: Map<Long, ErrorEntry> = emptyMap()
    ) : ErrorEntryDao {
        override fun getAll(): Flow<List<ErrorEntry>> = flowOf(emptyList())
        override suspend fun getById(id: Long) = entries[id]
        override fun getUnmastered(): Flow<List<ErrorEntry>> = flowOf(emptyList())
        override fun getMastered(): Flow<List<ErrorEntry>> = flowOf(emptyList())
        override fun getBySubject(subject: String): Flow<List<ErrorEntry>> = flowOf(emptyList())
        override suspend fun insert(errorEntry: ErrorEntry) = 0L
        override suspend fun update(errorEntry: ErrorEntry) {}
        override suspend fun delete(errorEntry: ErrorEntry) {}
        override suspend fun deleteById(id: Long) {}
        override suspend fun updateMastered(id: Long, mastered: Boolean, updatedAt: Long) {}
        override suspend fun updateAnalysis(id: Long, analysis: String, updatedAt: Long) {}
        override fun count(): Flow<Int> = flowOf(0)
        override fun countUnmastered(): Flow<Int> = flowOf(0)
        override suspend fun search(query: String) = emptyList<ErrorEntry>()
        override suspend fun getAllSync() = emptyList<ErrorEntry>()
        override suspend fun deleteAllSync() {}
    }

    private class FakeAppSettingDao : com.example.mathagent.data.local.dao.AppSettingDao {
        private val store = mutableMapOf<String, String>()
        override suspend fun get(key: String) = store[key]?.let {
            com.example.mathagent.data.local.entity.AppSetting(key = key, value = it)
        }
        override suspend fun getValue(key: String) = store[key]
        override fun getAll(): Flow<List<com.example.mathagent.data.local.entity.AppSetting>> = flowOf(emptyList())
        override suspend fun upsert(setting: com.example.mathagent.data.local.entity.AppSetting) {
            store[setting.key] = setting.value
        }
        override suspend fun delete(key: String) { store.remove(key) }
        override suspend fun deleteAll() { store.clear() }
        override suspend fun getAllSync() = emptyList<com.example.mathagent.data.local.entity.AppSetting>()
    }

    /** Captures the baseUrl/model passed to the factory for assertion. */
    private var capturedBaseUrl: String? = null
    private var capturedModel: String? = null
    private var capturedMessages: List<ChatMessage>? = null

    private fun fakeClientFactory(
        capturedResponse: String = "AI analysis result"
    ): (String, String, String) -> OpenAiClient = { baseUrl, apiKey, model ->
        capturedBaseUrl = baseUrl
        capturedModel = model
        object : OpenAiClient {
            override suspend fun chatCompletion(messages: List<ChatMessage>): String {
                capturedMessages = messages
                return capturedResponse
            }
        }
    }

    /** A fake MaterialChunkContextBuilder that returns a fixed context string. */
    private class FakeChunkContextBuilder(
        private val context: String = ""
    ) : MaterialChunkContextBuilder(
        materialChunkDao = object : com.example.mathagent.data.local.dao.MaterialChunkDao {
            override fun getByMaterialId(materialId: Long) = flowOf(emptyList<com.example.mathagent.data.local.entity.MaterialChunk>())
            override suspend fun getChunksByMaterialId(materialId: Long) = emptyList<com.example.mathagent.data.local.entity.MaterialChunk>()
            override suspend fun getById(id: Long) = null
            override suspend fun insert(chunk: com.example.mathagent.data.local.entity.MaterialChunk) = 0L
            override suspend fun insertAll(chunks: List<com.example.mathagent.data.local.entity.MaterialChunk>) {}
            override suspend fun delete(chunk: com.example.mathagent.data.local.entity.MaterialChunk) {}
            override suspend fun deleteByMaterialId(materialId: Long) {}
            override fun countByMaterialId(materialId: Long) = flowOf(0)
            override suspend fun getAllSync() = emptyList<com.example.mathagent.data.local.entity.MaterialChunk>()
            override suspend fun deleteAllSync() {}
            override suspend fun search(query: String, limit: Int) = emptyList<com.example.mathagent.data.local.entity.MaterialChunk>()
        },
        materialDao = object : com.example.mathagent.data.local.dao.MaterialDao {
            override fun getAll() = flowOf(emptyList<com.example.mathagent.data.local.entity.Material>())
            override suspend fun getById(id: Long) = null
            override suspend fun insert(material: com.example.mathagent.data.local.entity.Material) = 0L
            override suspend fun insertAll(materials: List<com.example.mathagent.data.local.entity.Material>) {}
            override suspend fun delete(material: com.example.mathagent.data.local.entity.Material) {}
            override suspend fun deleteById(id: Long) {}
            override fun count() = flowOf(0)
            override suspend fun update(material: com.example.mathagent.data.local.entity.Material) {}
            override suspend fun search(query: String) = emptyList<com.example.mathagent.data.local.entity.Material>()
            override suspend fun getAllSync() = emptyList<com.example.mathagent.data.local.entity.Material>()
            override suspend fun deleteAllSync() {}
        }
    ) {
        override suspend fun buildContext(entry: ErrorEntry): String = context
    }

    @Test
    fun isAiConfigured_noKey_returnsFalse() = runTest {
        val settingsRepo = SettingsRepository(FakeAppSettingDao())
        val errorDao = FakeErrorEntryDao()
        val repo = AiRepository(settingsRepo, errorDao, { null })

        assertFalse(repo.isAiConfigured())
    }

    @Test
    fun isAiConfigured_withKey_returnsTrue() = runTest {
        val settingsRepo = SettingsRepository(FakeAppSettingDao())
        val errorDao = FakeErrorEntryDao()
        val repo = AiRepository(settingsRepo, errorDao, { "sk-test-key" })

        assertTrue(repo.isAiConfigured())
    }

    @Test
    fun isAiConfigured_blankKey_returnsFalse() = runTest {
        val settingsRepo = SettingsRepository(FakeAppSettingDao())
        val errorDao = FakeErrorEntryDao()
        val repo = AiRepository(settingsRepo, errorDao, { "   " })

        assertFalse(repo.isAiConfigured())
    }

    @Test
    fun explainErrorEntry_noKey_throwsNotConfigured() = runTest {
        val settingsRepo = SettingsRepository(FakeAppSettingDao())
        val errorDao = FakeErrorEntryDao()
        val repo = AiRepository(settingsRepo, errorDao, { null })

        try {
            repo.explainErrorEntry(1L)
            assertTrue(false)
        } catch (e: AiException) {
            assertEquals(AiErrorType.NOT_CONFIGURED, e.type)
            assertTrue(e.message!!.contains("API Key"))
        }
    }

    @Test
    fun explainErrorEntry_noErrorEntry_throwsIllegalArgument() = runTest {
        val settingsRepo = SettingsRepository(FakeAppSettingDao())
        val errorDao = FakeErrorEntryDao(emptyMap())
        val repo = AiRepository(settingsRepo, errorDao, { "sk-test-key" }, fakeClientFactory())

        try {
            repo.explainErrorEntry(999L)
            assertTrue(false)
        } catch (e: IllegalArgumentException) {
            assertTrue(e.message!!.contains("不存在"))
        }
    }

    @Test
    fun getConfigSummary_returnsDefaults() = runTest {
        val appDao = FakeAppSettingDao()
        val settingsRepo = SettingsRepository(appDao)
        val errorDao = FakeErrorEntryDao()
        val repo = AiRepository(settingsRepo, errorDao, { "sk-test" })

        val summary = repo.getConfigSummary()
        assertTrue(summary.isConfigured)
        assertEquals(OpenAiApi.DEFAULT_BASE_URL, summary.baseUrl)
        assertEquals(OpenAiApi.DEFAULT_MODEL, summary.model)
    }

    @Test
    fun getConfigSummary_customValues() = runTest {
        val appDao = FakeAppSettingDao()
        appDao.upsert(com.example.mathagent.data.local.entity.AppSetting(key = "ai_base_url", value = "https://custom.api.com/v1"))
        appDao.upsert(com.example.mathagent.data.local.entity.AppSetting(key = "ai_model", value = "gpt-4"))

        val settingsRepo = SettingsRepository(appDao)
        val errorDao = FakeErrorEntryDao()
        val repo = AiRepository(settingsRepo, errorDao, { "sk-test" })

        val summary = repo.getConfigSummary()
        assertEquals("https://custom.api.com/v1", summary.baseUrl)
        assertEquals("gpt-4", summary.model)
    }

    // ---- Blank baseUrl/model defaults to OpenAiApi.DEFAULT_* ----

    @Test
    fun getConfigSummary_blankBaseUrl_returnsDefault() = runTest {
        val appDao = FakeAppSettingDao()
        appDao.upsert(com.example.mathagent.data.local.entity.AppSetting(key = "ai_base_url", value = "  "))
        val settingsRepo = SettingsRepository(appDao)
        val errorDao = FakeErrorEntryDao()
        val repo = AiRepository(settingsRepo, errorDao, { "sk-test" })

        val summary = repo.getConfigSummary()
        assertEquals(OpenAiApi.DEFAULT_BASE_URL, summary.baseUrl)
    }

    @Test
    fun getConfigSummary_blankModel_returnsDefault() = runTest {
        val appDao = FakeAppSettingDao()
        appDao.upsert(com.example.mathagent.data.local.entity.AppSetting(key = "ai_model", value = ""))
        val settingsRepo = SettingsRepository(appDao)
        val errorDao = FakeErrorEntryDao()
        val repo = AiRepository(settingsRepo, errorDao, { "sk-test" })

        val summary = repo.getConfigSummary()
        assertEquals(OpenAiApi.DEFAULT_MODEL, summary.model)
    }

    @Test
    fun getConfigSummary_emptyBaseUrlAndModel_returnsDefaults() = runTest {
        val appDao = FakeAppSettingDao()
        appDao.upsert(com.example.mathagent.data.local.entity.AppSetting(key = "ai_base_url", value = ""))
        appDao.upsert(com.example.mathagent.data.local.entity.AppSetting(key = "ai_model", value = ""))
        val settingsRepo = SettingsRepository(appDao)
        val errorDao = FakeErrorEntryDao()
        val repo = AiRepository(settingsRepo, errorDao, { "sk-test" })

        val summary = repo.getConfigSummary()
        assertEquals(OpenAiApi.DEFAULT_BASE_URL, summary.baseUrl)
        assertEquals(OpenAiApi.DEFAULT_MODEL, summary.model)
    }

    @Test
    fun explainErrorEntry_blankBaseUrl_model_usesDefaults() = runTest {
        val appDao = FakeAppSettingDao()
        appDao.upsert(com.example.mathagent.data.local.entity.AppSetting(key = "ai_base_url", value = ""))
        appDao.upsert(com.example.mathagent.data.local.entity.AppSetting(key = "ai_model", value = "   "))
        val settingsRepo = SettingsRepository(appDao)
        val entry = ErrorEntry(id = 1L, question = "1+1=?")
        val errorDao = FakeErrorEntryDao(mapOf(1L to entry))
        val factory = fakeClientFactory()
        val repo = AiRepository(settingsRepo, errorDao, { "sk-test" }, factory)

        repo.explainErrorEntry(1L)

        assertEquals("Factory should receive default baseUrl", OpenAiApi.DEFAULT_BASE_URL, capturedBaseUrl)
        assertEquals("Factory should receive default model", OpenAiApi.DEFAULT_MODEL, capturedModel)
    }

    @Test
    fun aiException_doesNotContainApiKey() {
        val e = AiException("API Key 无效", AiErrorType.AUTH_ERROR)
        assertFalse(e.message!!.contains("sk-"))
    }

    // ---- Chunk context tests ----

    @Test
    fun explainErrorEntry_withChunkContext_appendsToSystemPrompt() = runTest {
        capturedMessages = null
        val settingsRepo = SettingsRepository(FakeAppSettingDao())
        val entry = ErrorEntry(id = 1L, question = "什么是极限？", subject = "数学")
        val errorDao = FakeErrorEntryDao(mapOf(1L to entry))
        val chunkBuilder = FakeChunkContextBuilder(context = "\n\n参考资料：\n- 【高数·片段1】极限的定义...")
        val factory = fakeClientFactory()
        val repo = AiRepository(settingsRepo, errorDao, { "sk-test" }, factory, chunkBuilder)

        repo.explainErrorEntry(1L)

        val systemMsg = capturedMessages?.firstOrNull { it.role == "system" }
        assertTrue("System prompt should contain chunk context",
            systemMsg?.content?.contains("参考资料") == true)
        assertTrue("System prompt should contain chunk snippet",
            systemMsg?.content?.contains("极限的定义") == true)
    }

    @Test
    fun explainErrorEntry_withoutChunkContext_originalPromptOnly() = runTest {
        capturedMessages = null
        val settingsRepo = SettingsRepository(FakeAppSettingDao())
        val entry = ErrorEntry(id = 1L, question = "1+1=?")
        val errorDao = FakeErrorEntryDao(mapOf(1L to entry))
        // Null chunkContextBuilder — no chunk context
        val factory = fakeClientFactory()
        val repo = AiRepository(settingsRepo, errorDao, { "sk-test" }, factory, null)

        repo.explainErrorEntry(1L)

        val systemMsg = capturedMessages?.firstOrNull { it.role == "system" }
        assertFalse("System prompt should NOT contain chunk context",
            systemMsg?.content?.contains("参考资料") == true)
        assertTrue("System prompt should still contain base prompt",
            systemMsg?.content?.contains("数学老师") == true)
    }

    @Test
    fun materialChunkContextBuilder_withRealChunks_containsRealContent() = runTest {
        val mat = Material(id = 10, title = "高等数学讲义", subject = "数学")
        val chunk = MaterialChunk(id = 1, materialId = 10, chunkIndex = 0,
            content = "极限是微积分中最基本的概念之一，描述函数在某一点附近的行为趋势")
        val fakeChunkDao = object : MaterialChunkDao {
            override fun getByMaterialId(materialId: Long) = flowOf(emptyList<MaterialChunk>())
            override suspend fun getChunksByMaterialId(materialId: Long) = emptyList<MaterialChunk>()
            override suspend fun getById(id: Long): MaterialChunk? = null
            override suspend fun insert(chunk: MaterialChunk) = 0L
            override suspend fun insertAll(chunks: List<MaterialChunk>) {}
            override suspend fun delete(chunk: MaterialChunk) {}
            override suspend fun deleteByMaterialId(materialId: Long) {}
            override fun countByMaterialId(materialId: Long) = flowOf(0)
            override suspend fun getAllSync() = emptyList<MaterialChunk>()
            override suspend fun deleteAllSync() {}
            override suspend fun search(query: String, limit: Int) = listOf(chunk)
        }
        val fakeMatDao = object : MaterialDao {
            override fun getAll() = flowOf(emptyList<Material>())
            override suspend fun getById(id: Long) = if (id == 10L) mat else null
            override suspend fun insert(material: Material) = 0L
            override suspend fun insertAll(materials: List<Material>) {}
            override suspend fun delete(material: Material) {}
            override suspend fun deleteById(id: Long) {}
            override fun count() = flowOf(0)
            override suspend fun update(material: Material) {}
            override suspend fun search(query: String) = emptyList<Material>()
            override suspend fun getAllSync() = emptyList<Material>()
            override suspend fun deleteAllSync() {}
        }
        val builder = MaterialChunkContextBuilder(fakeChunkDao, fakeMatDao)
        val entry = ErrorEntry(id = 1L, question = "什么是极限？", subject = "数学")

        val context = builder.buildContext(entry)

        assertTrue("Context must contain real material title",
            context.contains("高等数学讲义"))
        assertTrue("Context must contain real chunk content",
            context.contains("极限是微积分"))
        assertTrue("Context must contain chunk index",
            context.contains("片段1"))
        assertFalse("Context must NOT contain literal placeholder",
            context.contains("{mat.title}"))
        assertFalse("Context must NOT contain literal snippet placeholder",
            context.contains("{snippet}"))
    }

    @Test
    fun materialChunkContextBuilder_noChunks_returnsEmpty() = runTest {
        val fakeChunkDao = object : MaterialChunkDao {
            override fun getByMaterialId(materialId: Long) = flowOf(emptyList<MaterialChunk>())
            override suspend fun getChunksByMaterialId(materialId: Long) = emptyList<MaterialChunk>()
            override suspend fun getById(id: Long): MaterialChunk? = null
            override suspend fun insert(chunk: MaterialChunk) = 0L
            override suspend fun insertAll(chunks: List<MaterialChunk>) {}
            override suspend fun delete(chunk: MaterialChunk) {}
            override suspend fun deleteByMaterialId(materialId: Long) {}
            override fun countByMaterialId(materialId: Long) = flowOf(0)
            override suspend fun getAllSync() = emptyList<MaterialChunk>()
            override suspend fun deleteAllSync() {}
            override suspend fun search(query: String, limit: Int) = emptyList<MaterialChunk>()
        }
        val fakeMatDao = object : MaterialDao {
            override fun getAll() = flowOf(emptyList<Material>())
            override suspend fun getById(id: Long) = null
            override suspend fun insert(material: Material) = 0L
            override suspend fun insertAll(materials: List<Material>) {}
            override suspend fun delete(material: Material) {}
            override suspend fun deleteById(id: Long) {}
            override fun count() = flowOf(0)
            override suspend fun update(material: Material) {}
            override suspend fun search(query: String) = emptyList<Material>()
            override suspend fun getAllSync() = emptyList<Material>()
            override suspend fun deleteAllSync() {}
        }
        val builder = MaterialChunkContextBuilder(fakeChunkDao, fakeMatDao)
        val entry = ErrorEntry(id = 1L, question = "什么是极限？", subject = "数学")

        val context = builder.buildContext(entry)
        assertEquals("No chunks → empty context", "", context)
    }

    @Test
    fun explainErrorEntry_chunkContextFails_silentFallback() = runTest {
        capturedMessages = null
        val settingsRepo = SettingsRepository(FakeAppSettingDao())
        val entry = ErrorEntry(id = 1L, question = "1+1=?")
        val errorDao = FakeErrorEntryDao(mapOf(1L to entry))
        // A chunk builder that throws — should silently fallback
        val throwingBuilder = object : MaterialChunkContextBuilder(
            materialChunkDao = object : com.example.mathagent.data.local.dao.MaterialChunkDao {
                override fun getByMaterialId(materialId: Long) = flowOf(emptyList<com.example.mathagent.data.local.entity.MaterialChunk>())
                override suspend fun getChunksByMaterialId(materialId: Long) = emptyList<com.example.mathagent.data.local.entity.MaterialChunk>()
                override suspend fun getById(id: Long) = null
                override suspend fun insert(chunk: com.example.mathagent.data.local.entity.MaterialChunk) = 0L
                override suspend fun insertAll(chunks: List<com.example.mathagent.data.local.entity.MaterialChunk>) {}
                override suspend fun delete(chunk: com.example.mathagent.data.local.entity.MaterialChunk) {}
                override suspend fun deleteByMaterialId(materialId: Long) {}
                override fun countByMaterialId(materialId: Long) = flowOf(0)
                override suspend fun getAllSync() = emptyList<com.example.mathagent.data.local.entity.MaterialChunk>()
                override suspend fun deleteAllSync() {}
                override suspend fun search(query: String, limit: Int) = emptyList<com.example.mathagent.data.local.entity.MaterialChunk>()
            },
            materialDao = object : com.example.mathagent.data.local.dao.MaterialDao {
                override fun getAll() = flowOf(emptyList<com.example.mathagent.data.local.entity.Material>())
                override suspend fun getById(id: Long) = null
                override suspend fun insert(material: com.example.mathagent.data.local.entity.Material) = 0L
                override suspend fun insertAll(materials: List<com.example.mathagent.data.local.entity.Material>) {}
                override suspend fun delete(material: com.example.mathagent.data.local.entity.Material) {}
                override suspend fun deleteById(id: Long) {}
                override fun count() = flowOf(0)
                override suspend fun update(material: com.example.mathagent.data.local.entity.Material) {}
                override suspend fun search(query: String) = emptyList<com.example.mathagent.data.local.entity.Material>()
                override suspend fun getAllSync() = emptyList<com.example.mathagent.data.local.entity.Material>()
                override suspend fun deleteAllSync() {}
            }
        ) {
            override suspend fun buildContext(entry: ErrorEntry): String {
                throw RuntimeException("Simulated failure")
            }
        }
        val factory = fakeClientFactory()
        val repo = AiRepository(settingsRepo, errorDao, { "sk-test" }, factory, throwingBuilder)

        // Should NOT throw — silently falls back
        repo.explainErrorEntry(1L)

        val systemMsg = capturedMessages?.firstOrNull { it.role == "system" }
        assertFalse("System prompt should NOT contain chunk context after failure",
            systemMsg?.content?.contains("参考资料") == true)
    }
}
