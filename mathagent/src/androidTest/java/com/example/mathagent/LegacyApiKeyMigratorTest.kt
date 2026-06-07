package com.example.mathagent

import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.example.mathagent.data.local.LegacyApiKeyMigrator
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.SecureSettingsStore
import com.example.mathagent.data.repository.SettingsRepository
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Instrumented tests for [LegacyApiKeyMigrator].
 *
 * Verifies the runtime migration path: Room ai_api_key → SecureSettingsStore,
 * including the verify-before-delete safety check.
 */
@RunWith(AndroidJUnit4::class)
class LegacyApiKeyMigratorTest {

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
        // Clean slate for secure store
        runBlocking { secureStore.clearApiKey() }
    }

    @After
    fun teardown() {
        runBlocking { secureStore.clearApiKey() }
        db.close()
    }

    @Test
    fun migrate_keyInRoom_movesToSecureStore() = runBlocking {
        // Arrange: put legacy key in Room
        settingsRepo.set("ai_api_key", "sk-legacy-12345")
        settingsRepo.set("ai_base_url", "https://api.example.com")

        // Act
        val migrated = LegacyApiKeyMigrator.migrate(settingsRepo, secureStore)

        // Assert
        assertTrue("Should report migration happened", migrated)
        assertEquals("sk-legacy-12345", secureStore.getApiKey())
        assertNull("Room ai_api_key should be deleted", settingsRepo.getValue("ai_api_key"))
        // Other settings untouched
        assertEquals("https://api.example.com", settingsRepo.getValue("ai_base_url"))
    }

    @Test
    fun migrate_noKeyInRoom_noOp() = runBlocking {
        // Arrange: no ai_api_key in Room
        settingsRepo.set("ai_base_url", "https://api.example.com")

        // Act
        val migrated = LegacyApiKeyMigrator.migrate(settingsRepo, secureStore)

        // Assert
        assertFalse("Should report no migration needed", migrated)
        assertNull("SecureStore should remain empty", secureStore.getApiKey())
    }

    @Test
    fun migrate_blankKeyInRoom_noOp() = runBlocking {
        // Arrange: blank key in Room (should be treated as no key)
        settingsRepo.set("ai_api_key", "   ")

        // Act
        val migrated = LegacyApiKeyMigrator.migrate(settingsRepo, secureStore)

        // Assert
        assertFalse("Should not migrate blank key", migrated)
        assertNull(secureStore.getApiKey())
    }

    @Test
    fun migrate_verifyFails_roomKeyPreserved() = runBlocking {
        // Arrange: put legacy key in Room
        settingsRepo.set("ai_api_key", "sk-legacy-verify-fail")

        // Act: inject a verify function that returns null (simulating write failure)
        val migrated = LegacyApiKeyMigrator.migrate(
            settingsRepo, secureStore,
            verifyWrite = { null }
        )

        // Assert: migration reported as failed, Room key preserved
        assertFalse("Should report migration failed", migrated)
        assertEquals(
            "Room ai_api_key should be preserved when verify fails",
            "sk-legacy-verify-fail",
            settingsRepo.getValue("ai_api_key")
        )
    }

    @Test
    fun migrate_calledTwice_secondCallNoOp() = runBlocking {
        // Arrange
        settingsRepo.set("ai_api_key", "sk-once-only")

        // Act: first call migrates
        val first = LegacyApiKeyMigrator.migrate(settingsRepo, secureStore)
        assertTrue(first)
        assertEquals("sk-once-only", secureStore.getApiKey())
        assertNull(settingsRepo.getValue("ai_api_key"))

        // Act: second call is a no-op
        val second = LegacyApiKeyMigrator.migrate(settingsRepo, secureStore)
        assertFalse("Second call should be no-op", second)
        assertEquals("sk-once-only", secureStore.getApiKey())
    }
}
