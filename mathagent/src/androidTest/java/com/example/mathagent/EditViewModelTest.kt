package com.example.mathagent

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.material.MaterialImportService
import com.example.mathagent.data.repository.MaterialRepository
import com.example.mathagent.data.repository.StudyPlanRepository
import com.example.mathagent.ui.viewmodel.MaterialListViewModel
import com.example.mathagent.ui.viewmodel.PlanListViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import kotlin.math.min

/**
 * Instrumented tests for MaterialListViewModel and PlanListViewModel edit operations.
 * Uses real Dispatchers.Main (Android main looper) with deterministic waiting
 * via polling instead of Thread.sleep.
 * No Thread.sleep required.
 */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(AndroidJUnit4::class)
class EditViewModelTest {

    private lateinit var db: MathAgentDatabase

    @Before
    fun setup() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        db = Room.inMemoryDatabaseBuilder(context, MathAgentDatabase::class.java)
            .allowMainThreadQueries().build()
    }

    @After
    fun teardown() {
        db.close()
    }

    /**
     * Polls until the predicate is true or timeout expires.
     * No Thread.sleep — uses coroutine-friendly delay.
     */
    private suspend fun waitFor(
        timeoutMs: Long = 3000,
        intervalMs: Long = 20,
        predicate: () -> Boolean
    ) {
        val start = System.currentTimeMillis()
        while (!predicate()) {
            if (System.currentTimeMillis() - start > timeoutMs) {
                throw AssertionError("Timed out waiting for condition")
            }
            withContext(Dispatchers.IO) {
                kotlinx.coroutines.delay(min(intervalMs, timeoutMs))
            }
        }
    }

    // ---- MaterialListViewModel ----

    @Test
    fun materialVM_addAndEdit_updatesTitle() = runBlocking {
        val repo = MaterialRepository(db.materialDao(), db.materialChunkDao())
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val importService = MaterialImportService(context, db.materialDao(), db.materialChunkDao(), db)
        val vm = MaterialListViewModel(repo, importService)

        // Wait for initial load
        waitFor { vm.uiState.value.materials.isNotEmpty() || !vm.uiState.value.isLoading }

        // Add material
        vm.addMaterial("Original Title", "Math", "Description")
        waitFor { vm.uiState.value.materials.isNotEmpty() }

        val materials = vm.uiState.value.materials
        assertEquals(1, materials.size)
        assertEquals("Original Title", materials[0].title)

        // Edit material
        vm.updateMaterial(materials[0].copy(title = "Updated Title"))
        waitFor { vm.uiState.value.materials[0].title == "Updated Title" }

        val updated = vm.uiState.value.materials
        assertEquals(1, updated.size)
        assertEquals("Updated Title", updated[0].title)
        assertEquals("Math", updated[0].subject) // subject unchanged
    }

    @Test
    fun materialVM_editSubject_updatesCorrectly() = runBlocking {
        val repo = MaterialRepository(db.materialDao(), db.materialChunkDao())
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val importService = MaterialImportService(context, db.materialDao(), db.materialChunkDao(), db)
        val vm = MaterialListViewModel(repo, importService)

        waitFor { vm.uiState.value.materials.isNotEmpty() || !vm.uiState.value.isLoading }

        vm.addMaterial("Title", "Old Subject", "Desc")
        waitFor { vm.uiState.value.materials.isNotEmpty() }

        val material = vm.uiState.value.materials[0]
        vm.updateMaterial(material.copy(subject = "New Subject"))
        waitFor { vm.uiState.value.materials[0].subject == "New Subject" }

        assertEquals("New Subject", vm.uiState.value.materials[0].subject)
    }

    @Test
    fun materialVM_delete_removesFromList() = runBlocking {
        val repo = MaterialRepository(db.materialDao(), db.materialChunkDao())
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val importService = MaterialImportService(context, db.materialDao(), db.materialChunkDao(), db)
        val vm = MaterialListViewModel(repo, importService)

        waitFor { vm.uiState.value.materials.isNotEmpty() || !vm.uiState.value.isLoading }

        vm.addMaterial("To Delete", "", "")
        waitFor { vm.uiState.value.materials.isNotEmpty() }
        assertEquals(1, vm.uiState.value.materials.size)

        vm.deleteMaterial(vm.uiState.value.materials[0])
        waitFor { vm.uiState.value.materials.isEmpty() }

        assertTrue(vm.uiState.value.materials.isEmpty())
    }

    // ---- PlanListViewModel ----

    @Test
    fun planVM_addAndEdit_updatesTitle() = runBlocking {
        val repo = StudyPlanRepository(db.studyPlanDao())
        val vm = PlanListViewModel(repo)

        waitFor { vm.uiState.value.plans.isNotEmpty() || !vm.uiState.value.isLoading }

        vm.addPlan("Original Plan", "Math", "Desc")
        waitFor { vm.uiState.value.plans.isNotEmpty() }

        val plans = vm.uiState.value.plans
        assertEquals(1, plans.size)
        assertEquals("Original Plan", plans[0].title)

        vm.updatePlan(plans[0].copy(title = "Updated Plan"))
        waitFor { vm.uiState.value.plans[0].title == "Updated Plan" }

        val updated = vm.uiState.value.plans
        assertEquals(1, updated.size)
        assertEquals("Updated Plan", updated[0].title)
    }

    @Test
    fun planVM_toggleCompleted_flipsState() = runBlocking {
        val repo = StudyPlanRepository(db.studyPlanDao())
        val vm = PlanListViewModel(repo)

        waitFor { vm.uiState.value.plans.isNotEmpty() || !vm.uiState.value.isLoading }

        vm.addPlan("Plan", "", "")
        waitFor { vm.uiState.value.plans.isNotEmpty() }

        val plan = vm.uiState.value.plans[0]
        assertEquals(false, plan.completed)

        vm.toggleCompleted(plan.id)
        waitFor { vm.uiState.value.plans.isNotEmpty() && vm.uiState.value.plans[0].completed }

        assertEquals(true, vm.uiState.value.plans[0].completed)
    }

    @Test
    fun planVM_delete_removesFromList() = runBlocking {
        val repo = StudyPlanRepository(db.studyPlanDao())
        val vm = PlanListViewModel(repo)

        waitFor { vm.uiState.value.plans.isNotEmpty() || !vm.uiState.value.isLoading }

        vm.addPlan("To Delete", "", "")
        waitFor { vm.uiState.value.plans.isNotEmpty() }
        assertEquals(1, vm.uiState.value.plans.size)

        vm.deletePlan(vm.uiState.value.plans[0])
        waitFor { vm.uiState.value.plans.isEmpty() }

        assertTrue(vm.uiState.value.plans.isEmpty())
    }
}
