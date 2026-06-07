package com.example.mathagent

import com.example.mathagent.data.local.dao.ErrorEntryDao
import com.example.mathagent.data.local.dao.MaterialChunkDao
import com.example.mathagent.data.local.dao.MaterialDao
import com.example.mathagent.data.local.dao.StudyPlanDao
import com.example.mathagent.data.local.entity.MaterialChunk
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.local.entity.StudyPlan
import com.example.mathagent.data.repository.SearchRepository
import com.example.mathagent.ui.viewmodel.SearchViewModel
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
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class SearchViewModelTest {

    @Before
    fun setup() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
    }

    @After
    fun teardown() {
        Dispatchers.resetMain()
    }

    // ---- Tracking Fake DAOs ----

    private class TrackingErrorEntryDao(
        private val results: List<ErrorEntry> = emptyList()
    ) : ErrorEntryDao {
        var searchCallCount = 0
        var lastQuery: String? = null
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
        override suspend fun search(query: String): List<ErrorEntry> {
            searchCallCount++
            lastQuery = query
            return results
        }
        override suspend fun getAllSync(): List<ErrorEntry> = emptyList()
        override suspend fun deleteAllSync() {}
    }

    private class TrackingStudyPlanDao(
        private val results: List<StudyPlan> = emptyList()
    ) : StudyPlanDao {
        var searchCallCount = 0
        var lastQuery: String? = null
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
        override suspend fun search(query: String): List<StudyPlan> {
            searchCallCount++
            lastQuery = query
            return results
        }
        override suspend fun getAllSync(): List<StudyPlan> = emptyList()
        override suspend fun deleteAllSync() {}
    }

    private class TrackingMaterialDao(
        private val results: List<Material> = emptyList()
    ) : MaterialDao {
        var searchCallCount = 0
        var lastQuery: String? = null
        override fun getAll(): Flow<List<Material>> = flowOf(emptyList())
        override suspend fun getById(id: Long): Material? = null
        override suspend fun insert(material: Material) = 0L
        override suspend fun insertAll(materials: List<Material>) {}
        override suspend fun delete(material: Material) {}
        override suspend fun deleteById(id: Long) {}
        override fun count(): Flow<Int> = flowOf(0)
        override suspend fun update(material: Material) {}
        override suspend fun search(query: String): List<Material> {
            searchCallCount++
            lastQuery = query
            return results
        }
        override suspend fun getAllSync(): List<Material> = emptyList()
        override suspend fun deleteAllSync() {}
    }

    private class FakeMaterialChunkDao : MaterialChunkDao {
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
        override suspend fun search(query: String, limit: Int): List<MaterialChunk> = emptyList()
    }

    // ---- Tests ----

    @Test
    fun search_blankQuery_doesNotCallDao() = runTest {
        val errorDao = TrackingErrorEntryDao()
        val planDao = TrackingStudyPlanDao()
        val materialDao = TrackingMaterialDao()
        val repo = SearchRepository(errorDao, planDao, materialDao, FakeMaterialChunkDao())
        val vm = SearchViewModel(repo)

        vm.updateQuery("")
        vm.search()

        assertEquals(0, errorDao.searchCallCount)
        assertEquals(0, planDao.searchCallCount)
        assertEquals(0, materialDao.searchCallCount)
        assertFalse(vm.uiState.value.hasSearched)
        assertTrue(vm.uiState.value.results.isEmpty())
        assertNull(vm.uiState.value.message)
    }

    @Test
    fun search_whitespaceQuery_doesNotCallDao() = runTest {
        val errorDao = TrackingErrorEntryDao()
        val planDao = TrackingStudyPlanDao()
        val materialDao = TrackingMaterialDao()
        val repo = SearchRepository(errorDao, planDao, materialDao, FakeMaterialChunkDao())
        val vm = SearchViewModel(repo)

        vm.updateQuery("   ")
        vm.search()

        assertEquals(0, errorDao.searchCallCount)
        assertEquals(0, planDao.searchCallCount)
        assertEquals(0, materialDao.searchCallCount)
        assertFalse(vm.uiState.value.hasSearched)
    }

    @Test
    fun search_validQuery_trimPassedToDao() = runTest {
        val errorDao = TrackingErrorEntryDao(listOf(ErrorEntry(id = 1, question = "Q")))
        val planDao = TrackingStudyPlanDao(listOf(StudyPlan(id = 2, title = "P")))
        val materialDao = TrackingMaterialDao(listOf(Material(id = 3, title = "M")))
        val repo = SearchRepository(errorDao, planDao, materialDao, FakeMaterialChunkDao())
        val vm = SearchViewModel(repo)

        vm.updateQuery("  数学  ")
        vm.search()

        assertEquals("数学", errorDao.lastQuery)
        assertEquals("数学", planDao.lastQuery)
        assertEquals("数学", materialDao.lastQuery)
        assertEquals(1, errorDao.searchCallCount)
        assertEquals(1, planDao.searchCallCount)
        assertEquals(1, materialDao.searchCallCount)
        assertTrue(vm.uiState.value.hasSearched)
        assertEquals(3, vm.uiState.value.results.size)
    }

    @Test
    fun search_afterBlankQuery_clearsState() = runTest {
        val repo = SearchRepository(
            TrackingErrorEntryDao(listOf(ErrorEntry(id = 1, question = "Q"))),
            TrackingStudyPlanDao(),
            TrackingMaterialDao(),
            FakeMaterialChunkDao()
        )
        val vm = SearchViewModel(repo)

        // First: valid search
        vm.updateQuery("test")
        vm.search()
        assertTrue(vm.uiState.value.hasSearched)
        assertEquals(1, vm.uiState.value.results.size)

        // Then: blank search clears everything
        vm.updateQuery("")
        vm.search()
        assertFalse(vm.uiState.value.hasSearched)
        assertTrue(vm.uiState.value.results.isEmpty())
        assertNull(vm.uiState.value.message)
    }

    @Test
    fun search_resultsHaveCorrectTypes() = runTest {
        val repo = SearchRepository(
            TrackingErrorEntryDao(listOf(ErrorEntry(id = 1, question = "Q", subject = "Math"))),
            TrackingStudyPlanDao(listOf(StudyPlan(id = 2, title = "Plan"))),
            TrackingMaterialDao(listOf(Material(id = 3, title = "Material"))),
            FakeMaterialChunkDao()
        )
        val vm = SearchViewModel(repo)

        vm.updateQuery("test")
        vm.search()

        val types = vm.uiState.value.results.map { it.type }.toSet()
        assertTrue("error" in types)
        assertTrue("plan" in types)
        assertTrue("material" in types)
    }

    @Test
    fun search_noMatch_returnsEmptyResults() = runTest {
        val repo = SearchRepository(
            TrackingErrorEntryDao(emptyList()),
            TrackingStudyPlanDao(emptyList()),
            TrackingMaterialDao(emptyList()),
            FakeMaterialChunkDao()
        )
        val vm = SearchViewModel(repo)

        vm.updateQuery("xyz不存在")
        vm.search()

        assertTrue(vm.uiState.value.hasSearched)
        assertTrue(vm.uiState.value.results.isEmpty())
    }
}
