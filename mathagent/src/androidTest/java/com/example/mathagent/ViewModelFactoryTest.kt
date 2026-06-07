package com.example.mathagent

import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.di.AppContainer
import com.example.mathagent.ui.viewmodel.AppViewModelFactory
import com.example.mathagent.ui.viewmodel.DashboardViewModel
import com.example.mathagent.ui.viewmodel.ErrorListViewModel
import com.example.mathagent.ui.viewmodel.MaterialListViewModel
import com.example.mathagent.ui.viewmodel.PlanListViewModel
import com.example.mathagent.ui.viewmodel.ReviewViewModel
import com.example.mathagent.ui.viewmodel.SearchViewModel
import com.example.mathagent.ui.viewmodel.BackupViewModel
import com.example.mathagent.ui.viewmodel.SettingsViewModel
import org.junit.Assert.assertNotNull
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented test: AppViewModelFactory can create all ViewModels.
 * Uses in-memory database to avoid dirty persistent DB on emulator.
 *
 * Uses ViewModelStore + ViewModelProvider so that ViewModelStore.clear()
 * cancels all viewModelScope coroutines (e.g. DashboardViewModel's Flow
 * collects) BEFORE the in-memory database is closed.
 */
@RunWith(AndroidJUnit4::class)
class ViewModelFactoryTest {

    @Test
    fun factory_createsAllViewModels() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val db = Room.inMemoryDatabaseBuilder(context, MathAgentDatabase::class.java)
            .allowMainThreadQueries().build()
        val container = AppContainer(context, databaseOverride = db)
        val factory = AppViewModelFactory(container)
        val store = ViewModelStore()
        val provider = ViewModelProvider(store, factory)

        // Each ViewModel should be created without throwing
        assertNotNull(provider[DashboardViewModel::class.java])
        assertNotNull(provider[ErrorListViewModel::class.java])
        assertNotNull(provider[ReviewViewModel::class.java])
        assertNotNull(provider[PlanListViewModel::class.java])
        assertNotNull(provider[MaterialListViewModel::class.java])
        assertNotNull(provider[SettingsViewModel::class.java])
        assertNotNull(provider[SearchViewModel::class.java])
        assertNotNull(provider[BackupViewModel::class.java])

        // Clear ViewModelStore — cancels viewModelScope coroutines.
        // Do NOT call db.close() here: Room Flow collectors on Dispatchers.IO
        // may still be in-flight after scope cancellation.  The in-memory DB
        // is released automatically when the test process exits; explicitly
        // closing it while IO is pending causes
        // "IllegalStateException: connection pool has been closed".
        store.clear()
    }

    @Test(expected = IllegalArgumentException::class)
    fun factory_throwsForUnknownViewModel() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        val db = Room.inMemoryDatabaseBuilder(context, MathAgentDatabase::class.java)
            .allowMainThreadQueries().build()
        val container = AppContainer(context, databaseOverride = db)
        val factory = AppViewModelFactory(container)

        factory.create(UnknownViewModel::class.java)
        // db intentionally not closed — no active Flow collectors; GC handles cleanup
    }

    /** Dummy ViewModel to test unknown class handling. */
    private class UnknownViewModel : androidx.lifecycle.ViewModel()
}
