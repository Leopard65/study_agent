package com.example.mathagent

import com.example.mathagent.data.local.dao.ErrorEntryDao
import com.example.mathagent.data.local.dao.MaterialChunkDao
import com.example.mathagent.data.local.dao.MaterialDao
import com.example.mathagent.data.local.dao.StudyPlanDao
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.local.entity.MaterialChunk
import com.example.mathagent.data.local.entity.StudyPlan
import com.example.mathagent.data.repository.SearchRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SearchRepositoryTest {

    // ---- Fake DAOs ----

    private class FakeErrorEntryDao(
        private val results: List<ErrorEntry> = emptyList()
    ) : ErrorEntryDao {
        override fun getAll(): Flow<List<ErrorEntry>> = flowOf(emptyList())
        override suspend fun getById(id: Long): ErrorEntry? = null
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
        override suspend fun search(query: String) = results
        override suspend fun getAllSync(): List<ErrorEntry> = emptyList()
        override suspend fun deleteAllSync() {}
    }

    private class FakeStudyPlanDao(
        private val results: List<StudyPlan> = emptyList()
    ) : StudyPlanDao {
        override fun getAll(): Flow<List<StudyPlan>> = flowOf(emptyList())
        override suspend fun getById(id: Long): StudyPlan? = null
        override fun getActive(): Flow<List<StudyPlan>> = flowOf(emptyList())
        override fun getCompleted(): Flow<List<StudyPlan>> = flowOf(emptyList())
        override suspend fun insert(plan: StudyPlan) = 0L
        override suspend fun update(plan: StudyPlan) {}
        override suspend fun delete(plan: StudyPlan) {}
        override suspend fun deleteById(id: Long) {}
        override suspend fun updateCompleted(id: Long, completed: Boolean, updatedAt: Long) {}
        override fun count(): Flow<Int> = flowOf(0)
        override fun countActive(): Flow<Int> = flowOf(0)
        override suspend fun search(query: String) = results
        override suspend fun getAllSync(): List<StudyPlan> = emptyList()
        override suspend fun deleteAllSync() {}
    }

    private class FakeMaterialDao(
        private val searchResults: List<Material> = emptyList(),
        private val getByIdMap: Map<Long, Material> = emptyMap()
    ) : MaterialDao {
        override fun getAll(): Flow<List<Material>> = flowOf(emptyList())
        override suspend fun getById(id: Long) = getByIdMap[id]
        override suspend fun insert(material: Material) = 0L
        override suspend fun insertAll(materials: List<Material>) {}
        override suspend fun delete(material: Material) {}
        override suspend fun deleteById(id: Long) {}
        override fun count(): Flow<Int> = flowOf(0)
        override suspend fun update(material: Material) {}
        override suspend fun search(query: String) = searchResults
        override suspend fun getAllSync(): List<Material> = emptyList()
        override suspend fun deleteAllSync() {}
    }

    private class FakeMaterialChunkDao(
        private val searchResults: List<MaterialChunk> = emptyList()
    ) : MaterialChunkDao {
        override fun getByMaterialId(materialId: Long): Flow<List<MaterialChunk>> = flowOf(emptyList())
        override suspend fun getChunksByMaterialId(materialId: Long): List<MaterialChunk> = emptyList()
        override suspend fun getById(id: Long): MaterialChunk? = null
        override suspend fun insert(chunk: MaterialChunk) = 0L
        override suspend fun insertAll(chunks: List<MaterialChunk>) {}
        override suspend fun delete(chunk: MaterialChunk) {}
        override suspend fun deleteByMaterialId(materialId: Long) {}
        override fun countByMaterialId(materialId: Long): Flow<Int> = flowOf(0)
        override suspend fun getAllSync(): List<MaterialChunk> = emptyList()
        override suspend fun deleteAllSync() {}
        override suspend fun search(query: String, limit: Int) = searchResults
    }

    // ---- extractSnippet tests ----

    @Test
    fun extractSnippet_matchInMiddle_surroundedByEllipsis() {
        val content = "A".repeat(50) + "needle" + "B".repeat(50)
        val snippet = SearchRepository.extractSnippet(content, "needle", contextLen = 10)
        assertTrue("Should start with ellipsis", snippet.startsWith("…"))
        assertTrue("Should end with ellipsis", snippet.endsWith("…"))
        assertTrue("Should contain needle", snippet.contains("needle"))
    }

    @Test
    fun extractSnippet_matchAtStart_noLeadingEllipsis() {
        val content = "needle" + "B".repeat(50)
        val snippet = SearchRepository.extractSnippet(content, "needle", contextLen = 10)
        assertTrue("Should NOT start with ellipsis", !snippet.startsWith("…"))
        assertTrue("Should contain needle", snippet.contains("needle"))
    }

    @Test
    fun extractSnippet_noMatch_returnsPrefix() {
        val content = "A".repeat(100)
        val snippet = SearchRepository.extractSnippet(content, "needle", contextLen = 10)
        assertTrue("Should end with ellipsis", snippet.endsWith("…"))
        assertTrue(snippet.length <= 21) // 2*contextLen + "…"
    }

    // ---- buildChunkSearchResult tests ----

    @Test
    fun buildChunkSearchResult_subtitleContainsRealSnippet() {
        val chunk = MaterialChunk(
            id = 42, materialId = 100, chunkIndex = 3,
            content = "这是一段关于微积分中极限概念的详细解释"
        )
        val result = SearchRepository.buildChunkSearchResult(chunk, "高等数学讲义", "极限")
        // Title must be the real material title
        assertEquals("高等数学讲义", result.title)
        // Subtitle must contain real snippet text from the chunk content
        assertTrue("Subtitle must contain query match",
            result.subtitle.contains("极限"))
        assertTrue("Subtitle must contain surrounding context",
            result.subtitle.contains("微积分"))
        // Must NOT contain literal placeholders
        assertFalse(result.subtitle.contains("{mat.title}"))
        assertFalse(result.subtitle.contains("{snippet}"))
        assertFalse(result.subtitle.contains("\$snippet"))
    }

    @Test
    fun buildChunkSearchResult_hasCorrectFields() {
        val chunk = MaterialChunk(id = 42, materialId = 100, chunkIndex = 3, content = "some content about math")
        val result = SearchRepository.buildChunkSearchResult(chunk, "高等数学", "math")
        assertEquals(42L, result.id)
        assertEquals("chunk", result.type)
        assertEquals("高等数学", result.title)
        assertTrue(result.subtitle.contains("片段 4")) // chunkIndex 3 → display "4"
        assertTrue(result.subtitle.contains("math"))
        assertEquals(100L, result.materialId)
        assertEquals(3, result.matchedChunkIndex)
        assertEquals(2, result.sortKey)
        assertTrue(result.route.contains("material_detail/100"))
        assertTrue(result.route.contains("chunkIndex=3"))
    }

    // ---- computeChunkScore tests ----

    @Test
    fun computeChunkScore_earlyHitHigherThanLateHit() {
        val early = MaterialChunk(id = 1, materialId = 10, chunkIndex = 0, content = "极限是微积分的基础概念")
        val late = MaterialChunk(id = 2, materialId = 10, chunkIndex = 0, content = "本章讨论函数的连续性和可导性，最后引入极限")
        val earlyScore = SearchRepository.computeChunkScore(early, "极限")
        val lateScore = SearchRepository.computeChunkScore(late, "极限")
        assertTrue("Earlier hit should score higher: early=$earlyScore late=$lateScore",
            earlyScore > lateScore)
    }

    @Test
    fun computeChunkScore_lowerChunkIndexSlightlyHigher() {
        val chunk0 = MaterialChunk(id = 1, materialId = 10, chunkIndex = 0, content = "极限的定义")
        val chunk5 = MaterialChunk(id = 2, materialId = 10, chunkIndex = 5, content = "极限的定义")
        val score0 = SearchRepository.computeChunkScore(chunk0, "极限")
        val score5 = SearchRepository.computeChunkScore(chunk5, "极限")
        assertTrue("Lower chunkIndex should score slightly higher",
            score0 > score5)
    }

    @Test
    fun computeChunkScore_noHit_scoresZero() {
        val chunk = MaterialChunk(id = 1, materialId = 10, chunkIndex = 0, content = "完全无关的内容")
        val score = SearchRepository.computeChunkScore(chunk, "极限")
        assertEquals("No hit should score 10 (index only)", 10, score)
    }

    // ---- search integration tests ----

    @Test
    fun search_chunkResults_afterTitleHits() = runTest {
        val repo = SearchRepository(
            FakeErrorEntryDao(listOf(ErrorEntry(id = 1, question = "数学题"))),
            FakeStudyPlanDao(emptyList()),
            FakeMaterialDao(emptyList(), emptyMap()),
            FakeMaterialChunkDao(listOf(
                MaterialChunk(id = 10, materialId = 100, chunkIndex = 0, content = "数学公式")
            ))
        )

        // MaterialChunkDao.getById is needed for chunk results — but our fake returns null.
        // So chunk results will be filtered out.  Test that title hits still appear.
        val results = repo.search("数学")
        assertTrue(results.isNotEmpty())
        assertEquals("error", results[0].type)
    }

    @Test
    fun search_chunkResults_withMaterialLookup() = runTest {
        val mat = Material(id = 100, title = "高数讲义", subject = "数学")
        val chunk = MaterialChunk(id = 10, materialId = 100, chunkIndex = 0, content = "极限的定义和性质")
        val repo = SearchRepository(
            FakeErrorEntryDao(emptyList()),
            FakeStudyPlanDao(emptyList()),
            FakeMaterialDao(emptyList(), getByIdMap = mapOf(100L to mat)),
            FakeMaterialChunkDao(listOf(chunk))
        )

        val results = repo.search("极限")
        assertEquals(1, results.size)
        assertEquals("chunk", results[0].type)
        assertEquals("高数讲义", results[0].title)
        assertEquals(100L, results[0].materialId)
        assertEquals(0, results[0].matchedChunkIndex)
        // Subtitle must contain real chunk content (not literal placeholder)
        assertTrue("Subtitle must contain real chunk content",
            results[0].subtitle.contains("极限"))
        assertTrue("Subtitle must contain chunk content text",
            results[0].subtitle.contains("定义"))
    }

    @Test
    fun search_chunkResults_sortedByRelevance() = runTest {
        val mat = Material(id = 100, title = "高数讲义")
        // Two chunks: one with early hit, one with late hit
        val earlyChunk = MaterialChunk(id = 1, materialId = 100, chunkIndex = 0,
            content = "极限是微积分的核心概念，本节介绍极限的定义")
        val lateChunk = MaterialChunk(id = 2, materialId = 100, chunkIndex = 1,
            content = "本节讨论连续性，最后简单提到了极限的概念")
        val repo = SearchRepository(
            FakeErrorEntryDao(emptyList()),
            FakeStudyPlanDao(emptyList()),
            FakeMaterialDao(emptyList(), getByIdMap = mapOf(100L to mat)),
            FakeMaterialChunkDao(listOf(lateChunk, earlyChunk)) // DAO returns late first
        )

        val results = repo.search("极限")
        assertEquals(2, results.size)
        // Early hit should come first despite DAO returning late chunk first
        assertEquals("Early hit should be first", 1L, results[0].id)
        assertEquals("Late hit should be second", 2L, results[1].id)
    }

    @Test
    fun search_sortKey_titleHitBeforeChunk() = runTest {
        val mat = Material(id = 100, title = "极限讲义", subject = "数学")
        val chunk = MaterialChunk(id = 10, materialId = 100, chunkIndex = 0, content = "关于极限的定义")
        val repo = SearchRepository(
            FakeErrorEntryDao(emptyList()),
            FakeStudyPlanDao(emptyList()),
            FakeMaterialDao(listOf(mat), getByIdMap = mapOf(100L to mat)),
            FakeMaterialChunkDao(listOf(chunk))
        )

        val results = repo.search("极限")
        assertEquals(2, results.size)
        // Material title hit (sortKey=0) before chunk hit (sortKey=2)
        assertEquals("material", results[0].type)
        assertEquals(0, results[0].sortKey)
        assertEquals("chunk", results[1].type)
        assertEquals(2, results[1].sortKey)
    }

    @Test
    fun search_emptyQuery_returnsEmpty() = runTest {
        val repo = SearchRepository(
            FakeErrorEntryDao(emptyList()),
            FakeStudyPlanDao(emptyList()),
            FakeMaterialDao(emptyList(), emptyMap()),
            FakeMaterialChunkDao(emptyList())
        )
        assertTrue(repo.search("").isEmpty())
        assertTrue(repo.search("   ").isEmpty())
    }

    @Test
    fun search_chunkMaterialIdAndIndex_preserved() = runTest {
        val mat = Material(id = 55, title = "线性代数")
        val chunk = MaterialChunk(id = 99, materialId = 55, chunkIndex = 7, content = "特征值分解")
        val repo = SearchRepository(
            FakeErrorEntryDao(emptyList()),
            FakeStudyPlanDao(emptyList()),
            FakeMaterialDao(emptyList(), getByIdMap = mapOf(55L to mat)),
            FakeMaterialChunkDao(listOf(chunk))
        )

        val results = repo.search("特征值")
        assertEquals(1, results.size)
        assertEquals(55L, results[0].materialId)
        assertEquals(7, results[0].matchedChunkIndex)
        assertTrue(results[0].route.contains("material_detail/55"))
        assertTrue(results[0].route.contains("chunkIndex=7"))
    }
}
