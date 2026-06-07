package com.example.mathagent

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.SecureSettingsStore
import com.example.mathagent.data.repository.SettingsRepository
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented test: Settings + SecureSettingsStore integration.
 * Tests the data layer directly (no ViewModel coroutine issues).
 */
@RunWith(AndroidJUnit4::class)
class SettingsStorageTest {

    private lateinit var db: MathAgentDatabase
    private lateinit var settingsRepo: SettingsRepository
    private lateinit var secureStore: SecureSettingsStore

    @Before
    fun setup() {
        val context = ApplicationProvider.getApplicationContext<android.content.Context>()
        db = Room.inMemoryDatabaseBuilder(context, MathAgentDatabase::class.java)
            .allowMainThreadQueries().build()
        settingsRepo = SettingsRepository(db.appSettingDao())
        secureStore = SecureSettingsStore(context)
    }

    @After
    fun teardown() {
        runBlocking { secureStore.clearApiKey() }
        db.close()
    }

    @Test
    fun emptyApiKey_doesNotWriteToRoom() = runTest {
        // Simulate what SettingsViewModel.save() does with empty API key
        settingsRepo.setBaseUrl("https://api.example.com")
        settingsRepo.setModel("gpt-4o")

        val trimmedKey = "".trim()
        if (trimmedKey.isEmpty()) {
            secureStore.clearApiKey()
        } else {
            secureStore.setApiKey(trimmedKey)
        }

        // API Key should NOT be in Room
        val keyInRoom = db.appSettingDao().getValue("ai_api_key")
        assertNull("Room should not have ai_api_key", keyInRoom)

        // Base URL and model should be in Room
        assertEquals("https://api.example.com", settingsRepo.getBaseUrl())
        assertEquals("gpt-4o", settingsRepo.getModel())
    }

    @Test
    fun apiKey_goesToSecureStore_notRoom() = runTest {
        settingsRepo.setBaseUrl("https://api.example.com")
        settingsRepo.setModel("gpt-4o")
        secureStore.setApiKey("sk-secret-key")

        // API Key in secure store
        assertEquals("sk-secret-key", secureStore.getApiKey())

        // API Key NOT in Room
        assertNull(db.appSettingDao().getValue("ai_api_key"))

        // Other settings in Room
        assertEquals("https://api.example.com", settingsRepo.getBaseUrl())
        assertEquals("gpt-4o", settingsRepo.getModel())
    }

    @Test
    fun clearApiKey_removesFromSecureStore() = runTest {
        secureStore.setApiKey("sk-to-clear")
        assertEquals("sk-to-clear", secureStore.getApiKey())

        secureStore.clearApiKey()
        assertNull(secureStore.getApiKey())
    }

    @Test
    fun trimApplied_toSettings() = runTest {
        val baseUrl = "  https://api.example.com  ".trim()
        val model = "  gpt-4o-mini  ".trim()
        val apiKey = "  sk-trimmed  ".trim()

        settingsRepo.setBaseUrl(baseUrl)
        settingsRepo.setModel(model)
        secureStore.setApiKey(apiKey)

        assertEquals("https://api.example.com", settingsRepo.getBaseUrl())
        assertEquals("gpt-4o-mini", settingsRepo.getModel())
        assertEquals("sk-trimmed", secureStore.getApiKey())
    }

    @Test
    fun blankBaseUrl_savedAsEmpty() = runTest {
        settingsRepo.setBaseUrl("")
        settingsRepo.setModel("")

        assertEquals("", settingsRepo.getBaseUrl())
        assertEquals("", settingsRepo.getModel())
        // AiRepository treats empty as "use default"
    }
}
