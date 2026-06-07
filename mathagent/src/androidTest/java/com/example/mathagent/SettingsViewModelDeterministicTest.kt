package com.example.mathagent

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.SecureSettingsStore
import com.example.mathagent.data.repository.SettingsRepository
import com.example.mathagent.ui.viewmodel.SettingsViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Deterministic tests for SettingsViewModel.
 * Uses polling-based waiting instead of Thread.sleep for deterministic execution.
 * No Thread.sleep required.
 */
@RunWith(AndroidJUnit4::class)
class SettingsViewModelDeterministicTest {

    private lateinit var db: MathAgentDatabase
    private lateinit var settingsRepo: SettingsRepository
    private lateinit var secureStore: SecureSettingsStore

    @Before
    fun setup() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(context, MathAgentDatabase::class.java)
            .allowMainThreadQueries().build()
        settingsRepo = SettingsRepository(db.appSettingDao())
        secureStore = SecureSettingsStore(context)
    }

    @After
    fun teardown() {
        runBlocking {
            withContext(Dispatchers.IO) {
                secureStore.clearApiKey()
            }
        }
        db.close()
    }

    /**
     * Polls until the predicate is true or timeout expires.
     * No Thread.sleep — uses coroutine delay for cooperative waiting.
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
                kotlinx.coroutines.delay(intervalMs)
            }
        }
    }

    /**
     * Creates a ViewModel and waits for initial load to complete.
     */
    private suspend fun createAndLoadVm(): SettingsViewModel {
        val vm = SettingsViewModel(settingsRepo, secureStore)
        vm.loadSettings()
        waitFor { !vm.uiState.value.isLoading }
        return vm
    }

    @Test
    fun save_emptyApiKey_clearsSecureStore_notRoom() = runBlocking {
        withContext(Dispatchers.IO) {
            secureStore.setApiKey("sk-old-key")
        }

        val vm = createAndLoadVm()

        vm.updateApiKey("")
        vm.save()
        waitFor { vm.uiState.value.message != null }

        val storedKey = withContext(Dispatchers.IO) { secureStore.getApiKey() }
        val roomKey = withContext(Dispatchers.IO) { db.appSettingDao().getValue("ai_api_key") }

        assertNull("SecureStore should have no API key", storedKey)
        assertNull("Room should not have ai_api_key", roomKey)
        assertFalse(vm.uiState.value.isSaving)
        assertEquals("保存成功", vm.uiState.value.message)
    }

    @Test
    fun save_withApiKey_storesInSecureStore_notRoom() = runBlocking {
        val vm = createAndLoadVm()

        vm.updateApiKey("sk-new-secret-key")
        vm.updateBaseUrl("https://api.example.com/v1")
        vm.updateModel("gpt-4o")
        vm.save()
        waitFor { vm.uiState.value.message != null }

        val storedKey = withContext(Dispatchers.IO) { secureStore.getApiKey() }
        val baseUrl = withContext(Dispatchers.IO) { settingsRepo.getBaseUrl() }
        val model = withContext(Dispatchers.IO) { settingsRepo.getModel() }
        val roomKey = withContext(Dispatchers.IO) { db.appSettingDao().getValue("ai_api_key") }

        assertEquals("sk-new-secret-key", storedKey)
        assertEquals("https://api.example.com/v1", baseUrl)
        assertEquals("gpt-4o", model)
        assertNull(roomKey)
        assertEquals("保存成功", vm.uiState.value.message)
    }

    @Test
    fun save_trimFields() = runBlocking {
        val vm = createAndLoadVm()

        vm.updateApiKey("  sk-trimmed  ")
        vm.updateBaseUrl("  https://api.example.com  ")
        vm.updateModel("  gpt-4o-mini  ")
        vm.save()
        waitFor { vm.uiState.value.message != null }

        val storedKey = withContext(Dispatchers.IO) { secureStore.getApiKey() }
        val baseUrl = withContext(Dispatchers.IO) { settingsRepo.getBaseUrl() }
        val model = withContext(Dispatchers.IO) { settingsRepo.getModel() }

        assertEquals("sk-trimmed", storedKey)
        assertEquals("https://api.example.com", baseUrl)
        assertEquals("gpt-4o-mini", model)
    }

    @Test
    fun save_setsIsSavingAndMessage() = runBlocking {
        val vm = createAndLoadVm()

        assertFalse(vm.uiState.value.isSaving)
        assertNull(vm.uiState.value.message)

        vm.save()
        waitFor { vm.uiState.value.message != null }

        assertFalse(vm.uiState.value.isSaving)
        assertEquals("保存成功", vm.uiState.value.message)
    }

    @Test
    fun clearMessage_clearsState() = runBlocking {
        val vm = createAndLoadVm()

        vm.save()
        waitFor { vm.uiState.value.message != null }
        assertEquals("保存成功", vm.uiState.value.message)

        vm.clearMessage()
        assertNull(vm.uiState.value.message)
    }

    @Test
    fun loadSettings_readsFromStore() = runBlocking {
        withContext(Dispatchers.IO) {
            settingsRepo.setBaseUrl("https://loaded.url")
            settingsRepo.setModel("loaded-model")
            secureStore.setApiKey("loaded-key")
        }

        val vm = createAndLoadVm()
        val state = vm.uiState.value

        assertFalse(state.isLoading)
        assertEquals("https://loaded.url", state.baseUrl)
        assertEquals("loaded-model", state.model)
        assertEquals("loaded-key", state.apiKey)
    }
}
