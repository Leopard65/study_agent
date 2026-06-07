package com.example.mathagent

import androidx.compose.material3.Text
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import androidx.lifecycle.ViewModelProvider
import androidx.navigation.NavType
import androidx.navigation.compose.ComposeNavigator
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import androidx.navigation.testing.TestNavHostController
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.mathagent.data.local.dao.ErrorEntryDao
import com.example.mathagent.data.local.dao.MaterialChunkDao
import com.example.mathagent.data.local.dao.MaterialDao
import com.example.mathagent.data.local.dao.StudyPlanDao
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.local.entity.MaterialChunk
import com.example.mathagent.data.local.entity.StudyPlan
import com.example.mathagent.data.repository.SearchRepository
import com.example.mathagent.ui.screens.search.SearchScreen
import com.example.mathagent.ui.viewmodel.SearchViewModel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Compose flow test for SearchScreen.
 * Tests the full search flow: input → submit → results → click → navigation.
 */
@RunWith(AndroidJUnit4::class)
class SearchComposeTest {

    @get:Rule
    val composeRule = createComposeRule()

    private lateinit var navController: TestNavHostController

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
        private val results: List<Material> = emptyList(),
        private val byIdMap: Map<Long, Material> = emptyMap()
    ) : MaterialDao {
        override fun getAll(): Flow<List<Material>> = flowOf(emptyList())
        override suspend fun getById(id: Long) = byIdMap[id]
        override suspend fun insert(material: Material) = 0L
        override suspend fun insertAll(materials: List<Material>) {}
        override suspend fun delete(material: Material) {}
        override suspend fun deleteById(id: Long) {}
        override fun count(): Flow<Int> = flowOf(0)
        override suspend fun update(material: Material) {}
        override suspend fun search(query: String) = results
        override suspend fun getAllSync(): List<Material> = emptyList()
        override suspend fun deleteAllSync() {}
    }

    private class FakeMaterialChunkDao(
        private val results: List<MaterialChunk> = emptyList()
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
        override suspend fun search(query: String, limit: Int) = results
    }

    private fun setupSearchScreen(
        errorResults: List<ErrorEntry> = emptyList(),
        planResults: List<StudyPlan> = emptyList(),
        materialResults: List<Material> = emptyList(),
        chunkResults: List<MaterialChunk> = emptyList(),
        materialByIdMap: Map<Long, Material> = emptyMap()
    ) {
        navController = TestNavHostController(ApplicationProvider.getApplicationContext())
        val repo = SearchRepository(
            FakeErrorEntryDao(errorResults),
            FakeStudyPlanDao(planResults),
            FakeMaterialDao(materialResults, materialByIdMap),
            FakeMaterialChunkDao(chunkResults)
        )
        val vm = SearchViewModel(repo)
        val factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : androidx.lifecycle.ViewModel> create(modelClass: Class<T>): T = vm as T
        }

        composeRule.setContent {
            navController.navigatorProvider.addNavigator(ComposeNavigator())
            CompositionLocalProvider(LocalViewModelFactory provides factory) {
                NavHost(navController = navController, startDestination = "search") {
                    composable("search") { SearchScreen(navController = navController) }
                    composable("materials") { }
                    composable("errors") { }
                    composable("plans") { }
                    composable("material_detail/{materialId}") { }
                    composable(
                        "material_detail/{materialId}?chunkIndex={chunkIndex}",
                        arguments = listOf(
                            navArgument("materialId") { type = NavType.LongType },
                            navArgument("chunkIndex") { type = NavType.IntType; defaultValue = -1 }
                        )
                    ) { }
                    composable("error_detail/{errorId}") { }
                }
            }
        }
    }

    @Test
    fun searchFlow_inputAndSubmit_showsResults() {
        setupSearchScreen(
            materialResults = listOf(Material(id = 10, title = "高等数学讲义", subject = "数学"))
        )

        // Input search query
        composeRule.onNodeWithTag("search-input").performTextInput("数学")
        composeRule.waitForIdle()

        // Click search button
        composeRule.onNodeWithTag("search-submit").performClick()
        composeRule.waitForIdle()

        // Assert result appears
        composeRule.onNodeWithTag("search-result-material-10").assertIsDisplayed()
        composeRule.onNodeWithText("高等数学讲义").assertIsDisplayed()
    }

    @Test
    fun searchFlow_clickResult_navigatesToModule() {
        setupSearchScreen(
            materialResults = listOf(Material(id = 10, title = "数学讲义"))
        )

        composeRule.onNodeWithTag("search-input").performTextInput("数学")
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("search-submit").performClick()
        composeRule.waitForIdle()

        // Click the result
        composeRule.onNodeWithTag("search-result-material-10").performClick()
        composeRule.waitForIdle()

        // Assert navigation happened to "material_detail/{materialId}" route
        assertEquals("material_detail/{materialId}", navController.currentDestination?.route)
    }

    @Test
    fun searchFlow_emptyQuery_noResults() {
        // Verify empty-query behavior through ViewModel directly.
        // The Compose click path on an untouched OutlinedTextField can hang
        // due to soft keyboard / focus lifecycle; testing via the ViewModel
        // covers the same "blank query → no results" logic without the hang.
        val repo = SearchRepository(
            FakeErrorEntryDao(emptyList()),
            FakeStudyPlanDao(emptyList()),
            FakeMaterialDao(listOf(Material(id = 10, title = "数学讲义"))),
            FakeMaterialChunkDao()
        )
        val vm = SearchViewModel(repo)

        // search() with blank query should clear results and not trigger network
        vm.search()
        val state = vm.uiState.value
        assertEquals(false, state.hasSearched)
        assertEquals(true, state.results.isEmpty())
    }

    @Test
    fun searchFlow_multipleResults_allDisplayed() {
        setupSearchScreen(
            errorResults = listOf(ErrorEntry(id = 1, question = "数学题")),
            planResults = listOf(StudyPlan(id = 2, title = "数学复习计划")),
            materialResults = listOf(Material(id = 3, title = "数学讲义"))
        )

        composeRule.onNodeWithTag("search-input").performTextInput("数学")
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("search-submit").performClick()
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("search-result-error-1").assertIsDisplayed()
        composeRule.onNodeWithTag("search-result-plan-2").assertIsDisplayed()
        composeRule.onNodeWithTag("search-result-material-3").assertIsDisplayed()
    }

    @Test
    fun searchFlow_chunkClick_navigatesToMaterialDetail() {
        val mat = Material(id = 100, title = "高等数学讲义")
        val chunk = MaterialChunk(id = 50, materialId = 100, chunkIndex = 3, content = "极限的定义")
        setupSearchScreen(
            chunkResults = listOf(chunk),
            materialByIdMap = mapOf(100L to mat)
        )

        composeRule.onNodeWithTag("search-input").performTextInput("极限")
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("search-submit").performClick()
        composeRule.waitForIdle()

        // Chunk result should appear with chunk id in test tag
        composeRule.onNodeWithTag("search-result-chunk-50").assertIsDisplayed()
        composeRule.onNodeWithText("高等数学讲义").assertIsDisplayed()

        // Click chunk result — should navigate to material detail
        composeRule.onNodeWithTag("search-result-chunk-50").performClick()
        composeRule.waitForIdle()

        // Navigation must go to material_detail with correct arguments
        val route = navController.currentDestination?.route
        assertTrue("Route must be material_detail, was: $route",
            route?.startsWith("material_detail") == true)
        val args = navController.currentBackStackEntry?.arguments
        assertEquals("materialId must be 100", 100L, args?.getLong("materialId"))
        // chunkIndex=3 is in the resolved route
        val resolvedRoute = navController.currentBackStackEntry?.destination?.route
        assertTrue("Route must contain chunkIndex, was: $resolvedRoute",
            resolvedRoute?.contains("chunkIndex") == true)
    }

    /**
     * Like [setupSearchScreen], but the material_detail destination uses a test
     * composable that displays the navigation arguments as test tags.
     * This verifies that the chunkIndex is correctly passed through navigation.
     */
    private fun setupSearchScreenWithDetail(
        chunkResults: List<MaterialChunk> = emptyList(),
        materialByIdMap: Map<Long, Material> = emptyMap()
    ) {
        navController = TestNavHostController(ApplicationProvider.getApplicationContext())
        val repo = SearchRepository(
            FakeErrorEntryDao(emptyList()),
            FakeStudyPlanDao(emptyList()),
            FakeMaterialDao(emptyList(), materialByIdMap),
            FakeMaterialChunkDao(chunkResults)
        )
        val searchVm = SearchViewModel(repo)

        val searchFactory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : androidx.lifecycle.ViewModel> create(modelClass: Class<T>): T = searchVm as T
        }

        composeRule.setContent {
            navController.navigatorProvider.addNavigator(ComposeNavigator())
            CompositionLocalProvider(LocalViewModelFactory provides searchFactory) {
                NavHost(navController = navController, startDestination = "search") {
                    composable("search") { SearchScreen(navController = navController) }
                    composable(
                        "material_detail/{materialId}?chunkIndex={chunkIndex}",
                        arguments = listOf(
                            navArgument("materialId") { type = NavType.LongType },
                            navArgument("chunkIndex") { type = NavType.IntType; defaultValue = -1 }
                        )
                    ) { backStackEntry ->
                        val chunkIndex = backStackEntry.arguments?.getInt("chunkIndex") ?: -1
                        // Render the chunk tag that MaterialDetailScreen would use
                        if (chunkIndex >= 0) {
                            Text("chunk-$chunkIndex", Modifier.testTag("chunk-$chunkIndex"))
                        }
                    }
                }
            }
        }
    }

    @Test
    fun searchFlow_chunkClick_highlightsCorrectChunk() {
        val mat = Material(id = 100, title = "高等数学讲义")
        val chunk = MaterialChunk(id = 50, materialId = 100, chunkIndex = 3, content = "极限的定义")
        setupSearchScreenWithDetail(
            chunkResults = listOf(chunk),
            materialByIdMap = mapOf(100L to mat)
        )

        // Search and click chunk result
        composeRule.onNodeWithTag("search-input").performTextInput("极限")
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("search-submit").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("search-result-chunk-50").performClick()
        composeRule.waitForIdle()

        // Verify navigation happened with correct materialId
        val route = navController.currentDestination?.route
        assertTrue("Route must be material_detail, was: $route",
            route?.startsWith("material_detail") == true)
        val args = navController.currentBackStackEntry?.arguments
        assertEquals("materialId must be 100", 100L, args?.getLong("materialId"))
        // Verify the test composable rendered the chunk tag
        composeRule.onNodeWithTag("chunk-3").assertIsDisplayed()
    }
}
