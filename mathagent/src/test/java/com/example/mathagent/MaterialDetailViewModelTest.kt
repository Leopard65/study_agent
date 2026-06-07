package com.example.mathagent

import com.example.mathagent.data.local.dao.MaterialChunkDao
import com.example.mathagent.data.local.dao.MaterialDao
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.local.entity.MaterialChunk
import com.example.mathagent.data.repository.MaterialRepository
import com.example.mathagent.ui.viewmodel.MaterialDetailViewModel
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
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class MaterialDetailViewModelTest {

    @Before
    fun setup() {
        Dispatchers.setMain(UnconfinedTestDispatcher())
    }

    @After
    fun teardown() {
        Dispatchers.resetMain()
    }

    // ---- Fake DAOs ----

    private class FakeMaterialDao(
        private val materials: Map<Long, Material> = emptyMap()
    ) : MaterialDao {
        override fun getAll(): Flow<List<Material>> = flowOf(emptyList())
        override suspend fun getById(id: Long) = materials[id]
        override suspend fun insert(material: Material) = 0L
        override suspend fun insertAll(materials: List<Material>) {}
        override suspend fun delete(material: Material) {}
        override suspend fun deleteById(id: Long) {}
        override fun count(): Flow<Int> = flowOf(0)
        override suspend fun update(material: Material) {}
        override suspend fun search(query: String) = emptyList<Material>()
        override suspend fun getAllSync() = emptyList<Material>()
        override suspend fun deleteAllSync() {}
    }

    private class FakeMaterialChunkDao(
        private val chunksByMaterial: Map<Long, List<MaterialChunk>> = emptyMap()
    ) : MaterialChunkDao {
        override fun getByMaterialId(materialId: Long) = flowOf(chunksByMaterial[materialId] ?: emptyList())
        override suspend fun getChunksByMaterialId(materialId: Long) = chunksByMaterial[materialId] ?: emptyList()
        override suspend fun getById(id: Long): MaterialChunk? = null
        override suspend fun insert(chunk: MaterialChunk) = 0L
        override suspend fun insertAll(chunks: List<MaterialChunk>) {}
        override suspend fun delete(chunk: MaterialChunk) {}
        override suspend fun deleteByMaterialId(materialId: Long) {}
        override fun countByMaterialId(materialId: Long): Flow<Int> = flowOf(0)
        override suspend fun getAllSync(): List<MaterialChunk> = emptyList()
        override suspend fun deleteAllSync() {}
        override suspend fun search(query: String, limit: Int) = emptyList<MaterialChunk>()
    }

    private fun createRepo(
        materials: Map<Long, Material> = emptyMap(),
        chunksByMaterial: Map<Long, List<MaterialChunk>> = emptyMap()
    ) = MaterialRepository(FakeMaterialDao(materials), FakeMaterialChunkDao(chunksByMaterial))

    // ---- Tests ----

    @Test
    fun loadMaterial_materialNotFound_showsMessage() = runTest {
        val vm = MaterialDetailViewModel(createRepo())
        vm.loadMaterial(999L)

        val state = vm.uiState.value
        assertNull(state.material)
        assertEquals("资料不存在", state.message)
        assertEquals(false, state.isLoading)
    }

    @Test
    fun loadMaterial_materialFound_showsChunks() = runTest {
        val mat = Material(id = 10, title = "高等数学", subject = "数学")
        val chunks = listOf(
            MaterialChunk(id = 1, materialId = 10, chunkIndex = 0, content = "第一章"),
            MaterialChunk(id = 2, materialId = 10, chunkIndex = 1, content = "第二章")
        )
        val vm = MaterialDetailViewModel(createRepo(
            materials = mapOf(10L to mat),
            chunksByMaterial = mapOf(10L to chunks)
        ))

        vm.loadMaterial(10L)

        val state = vm.uiState.value
        assertEquals(mat, state.material)
        assertEquals(2, state.chunks.size)
        assertEquals(false, state.isLoading)
        assertNull(state.highlightChunkIndex)
    }

    @Test
    fun loadMaterial_withHighlightChunkIndex_preserved() = runTest {
        val mat = Material(id = 10, title = "高等数学")
        val chunks = listOf(
            MaterialChunk(id = 1, materialId = 10, chunkIndex = 0, content = "第一章"),
            MaterialChunk(id = 2, materialId = 10, chunkIndex = 1, content = "第二章")
        )
        val vm = MaterialDetailViewModel(createRepo(
            materials = mapOf(10L to mat),
            chunksByMaterial = mapOf(10L to chunks)
        ))

        vm.loadMaterial(10L, highlightChunkIndex = 1)

        val state = vm.uiState.value
        assertEquals(1, state.highlightChunkIndex)
        // The highlighted chunk must exist in the list
        val highlightedChunk = state.chunks.find { it.chunkIndex == 1 }
        assertNotNull("Highlighted chunk must exist", highlightedChunk)
        assertEquals("第二章", highlightedChunk!!.content)
    }

    @Test
    fun loadMaterial_calledTwice_replacesState() = runTest {
        val mat1 = Material(id = 1, title = "数学")
        val mat2 = Material(id = 2, title = "物理")
        val vm = MaterialDetailViewModel(createRepo(
            materials = mapOf(1L to mat1, 2L to mat2),
            chunksByMaterial = emptyMap()
        ))

        vm.loadMaterial(1L)
        assertEquals("数学", vm.uiState.value.material?.title)

        vm.loadMaterial(2L)
        assertEquals("物理", vm.uiState.value.material?.title)
        // State should be completely replaced
        assertNull(vm.uiState.value.message)
    }

    @Test
    fun clearMessage_clearsMessage() = runTest {
        val vm = MaterialDetailViewModel(createRepo())
        vm.loadMaterial(999L) // triggers "资料不存在" message
        assertEquals("资料不存在", vm.uiState.value.message)

        vm.clearMessage()
        assertNull(vm.uiState.value.message)
    }
}
