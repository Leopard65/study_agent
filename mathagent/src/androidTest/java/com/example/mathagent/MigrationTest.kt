package com.example.mathagent

import androidx.room.Room
import androidx.room.testing.MigrationTestHelper
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mathagent.data.local.MathAgentDatabase
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.IOException

/**
 * Instrumented tests for Room MIGRATION_1_2.
 *
 * Uses MigrationTestHelper to:
 * 1. Create a v1 database with test data
 * 2. Run MIGRATION_1_2
 * 3. Validate the migrated schema matches v2
 * 4. Verify valid review_records survive and orphans are deleted
 */
@RunWith(AndroidJUnit4::class)
class MigrationTest {

    @get:Rule
    val helper = MigrationTestHelper(
        instrumentation = InstrumentationRegistry.getInstrumentation(),
        databaseClass = MathAgentDatabase::class.java
    )

    @Test
    @Throws(IOException::class)
    fun migration1To2_validDataPreserved() {
        // 1. Create v1 database
        val dbV1 = helper.createDatabase(MathAgentDatabase.DATABASE_NAME, 1)

        // Insert a valid error entry
        dbV1.execSQL(
            "INSERT INTO error_entries (id, subject, chapter, question, wrongAnswer, correctAnswer, analysis, difficulty, mastered, createdAt, updatedAt) " +
                "VALUES (1, 'Math', '', 'What is 1+1?', '', '2', '', 3, 0, 1000, 1000)"
        )

        // Insert a valid review record linked to error_entry 1
        dbV1.execSQL(
            "INSERT INTO review_records (id, errorEntryId, nextReviewAt, intervalDays, easeFactor, repetitionCount, lastReviewedAt, createdAt) " +
                "VALUES (1, 1, 2000, 1, 2.5, 0, 0, 1000)"
        )

        dbV1.close()

        // 2. Run migration
        val dbV2 = helper.runMigrationsAndValidate(
            MathAgentDatabase.DATABASE_NAME,
            2, /* dropAllTables = */
            true,
            MathAgentDatabase.MIGRATION_1_2
        )

        // 3. Verify data survived
        val cursor = dbV2.query("SELECT * FROM review_records WHERE errorEntryId = 1")
        assertTrue("Review record should exist after migration", cursor.moveToFirst())
        assertEquals(1, cursor.getLong(cursor.getColumnIndexOrThrow("errorEntryId")))
        assertEquals(1, cursor.getInt(cursor.getColumnIndexOrThrow("intervalDays")))
        assertEquals(2.5f, cursor.getFloat(cursor.getColumnIndexOrThrow("easeFactor")), 0.001f)
        cursor.close()

        dbV2.close()
    }

    @Test
    @Throws(IOException::class)
    fun migration1To2_orphanReviewRecordsDeleted() {
        // 1. Create v1 database
        val dbV1 = helper.createDatabase(MathAgentDatabase.DATABASE_NAME, 1)

        // Insert one valid error entry
        dbV1.execSQL(
            "INSERT INTO error_entries (id, subject, chapter, question, wrongAnswer, correctAnswer, analysis, difficulty, mastered, createdAt, updatedAt) " +
                "VALUES (1, 'Math', '', 'What is 1+1?', '', '2', '', 3, 0, 1000, 1000)"
        )

        // Insert a valid review record (linked to error_entry 1)
        dbV1.execSQL(
            "INSERT INTO review_records (id, errorEntryId, nextReviewAt, intervalDays, easeFactor, repetitionCount, lastReviewedAt, createdAt) " +
                "VALUES (1, 1, 2000, 1, 2.5, 0, 0, 1000)"
        )

        // Insert an orphan review record (errorEntryId = 999 does NOT exist)
        dbV1.execSQL(
            "INSERT INTO review_records (id, errorEntryId, nextReviewAt, intervalDays, easeFactor, repetitionCount, lastReviewedAt, createdAt) " +
                "VALUES (2, 999, 3000, 2, 2.0, 1, 1000, 1000)"
        )

        dbV1.close()

        // 2. Run migration
        val dbV2 = helper.runMigrationsAndValidate(
            MathAgentDatabase.DATABASE_NAME,
            2,
            true,
            MathAgentDatabase.MIGRATION_1_2
        )

        // 3. Verify orphan is gone
        val cursorOrphan = dbV2.query("SELECT * FROM review_records WHERE errorEntryId = 999")
        assertEquals("Orphan review record should be deleted", 0, cursorOrphan.count)
        cursorOrphan.close()

        // 4. Verify valid record survives
        val cursorValid = dbV2.query("SELECT * FROM review_records WHERE errorEntryId = 1")
        assertEquals("Valid review record should survive", 1, cursorValid.count)
        cursorValid.close()

        dbV2.close()
    }

    @Test
    @Throws(IOException::class)
    fun migration1To2_schemaValidates() {
        // 1. Create minimal v1 database
        val dbV1 = helper.createDatabase(MathAgentDatabase.DATABASE_NAME, 1)

        // Insert one error entry and one review record so the table isn't empty
        dbV1.execSQL(
            "INSERT INTO error_entries (id, subject, chapter, question, wrongAnswer, correctAnswer, analysis, difficulty, mastered, createdAt, updatedAt) " +
                "VALUES (1, 'Test', '', 'Q', '', 'A', '', 3, 0, 1000, 1000)"
        )
        dbV1.execSQL(
            "INSERT INTO review_records (id, errorEntryId, nextReviewAt, intervalDays, easeFactor, repetitionCount, lastReviewedAt, createdAt) " +
                "VALUES (1, 1, 2000, 1, 2.5, 0, 0, 1000)"
        )

        dbV1.close()

        // 2. Validate schema: this checks column types, NOT NULL, FK constraints, indices
        //    dropAllTables=true means it recreates from schema, then applies migration
        helper.runMigrationsAndValidate(
            MathAgentDatabase.DATABASE_NAME,
            2,
            true,
            MathAgentDatabase.MIGRATION_1_2
        )
        // If we reach here without exception, schema validation passed
    }

    @Test
    @Throws(IOException::class)
    fun migration1To2_noReviewRecords_tableCreated() {
        // Test migration when v1 has error entries but no review records at all
        val dbV1 = helper.createDatabase(MathAgentDatabase.DATABASE_NAME, 1)

        dbV1.execSQL(
            "INSERT INTO error_entries (id, subject, chapter, question, wrongAnswer, correctAnswer, analysis, difficulty, mastered, createdAt, updatedAt) " +
                "VALUES (1, 'Test', '', 'Q', '', 'A', '', 3, 0, 1000, 1000)"
        )
        // No review_records inserted

        dbV1.close()

        val dbV2 = helper.runMigrationsAndValidate(
            MathAgentDatabase.DATABASE_NAME,
            2,
            true,
            MathAgentDatabase.MIGRATION_1_2
        )

        // Table should exist and be empty
        val cursor = dbV2.query("SELECT COUNT(*) FROM review_records")
        assertTrue(cursor.moveToFirst())
        assertEquals(0, cursor.getInt(0))
        cursor.close()

        dbV2.close()
    }

    // ---- v2 → v3: backup_logs new columns ----

    @Test
    @Throws(IOException::class)
    fun migration2To3_addsBackupLogColumns() {
        val dbV2 = helper.createDatabase(MathAgentDatabase.DATABASE_NAME, 2)
        dbV2.execSQL("INSERT INTO backup_logs (id, fileName, fileSize, backupType, status, createdAt) VALUES (1, 'test.json', 100, 'manual', 'success', 1000)")
        dbV2.close()

        val dbV3 = helper.runMigrationsAndValidate(
            MathAgentDatabase.DATABASE_NAME, 3, true,
            MathAgentDatabase.MIGRATION_1_2, MathAgentDatabase.MIGRATION_2_3
        )

        val cursor = dbV3.query("SELECT operation, message FROM backup_logs WHERE id = 1")
        assertTrue(cursor.moveToFirst())
        assertEquals("export", cursor.getString(cursor.getColumnIndexOrThrow("operation")))
        assertEquals("", cursor.getString(cursor.getColumnIndexOrThrow("message")))
        cursor.close()
        dbV3.close()
    }

    // ---- v3 → v4: no-op migration (key preserved for runtime migration) ----

    @Test
    @Throws(IOException::class)
    fun migration3To4_noOp_keyPreserved() {
        val dbV3 = helper.createDatabase(MathAgentDatabase.DATABASE_NAME, 3)
        dbV3.execSQL("INSERT INTO app_settings (`key`, value, updatedAt) VALUES ('ai_api_key', 'sk-secret', 1000)")
        dbV3.execSQL("INSERT INTO app_settings (`key`, value, updatedAt) VALUES ('ai_base_url', 'https://api.example.com', 1000)")
        dbV3.close()

        val dbV4 = helper.runMigrationsAndValidate(
            MathAgentDatabase.DATABASE_NAME, 4, true,
            MathAgentDatabase.MIGRATION_1_2, MathAgentDatabase.MIGRATION_2_3, MathAgentDatabase.MIGRATION_3_4
        )

        // ai_api_key preserved (cleanup happens at runtime in AppContainer)
        val cursorKey = dbV4.query("SELECT value FROM app_settings WHERE `key` = 'ai_api_key'")
        assertTrue(cursorKey.moveToFirst())
        assertEquals("sk-secret", cursorKey.getString(0))
        cursorKey.close()

        // ai_base_url also preserved
        val cursorUrl = dbV4.query("SELECT value FROM app_settings WHERE `key` = 'ai_base_url'")
        assertTrue(cursorUrl.moveToFirst())
        assertEquals("https://api.example.com", cursorUrl.getString(0))
        cursorUrl.close()

        dbV4.close()
    }

    // ---- v1 → v4: full migration chain ----

    @Test
    @Throws(IOException::class)
    fun migration1To4_fullChain() {
        val dbV1 = helper.createDatabase(MathAgentDatabase.DATABASE_NAME, 1)

        // Insert data across tables
        dbV1.execSQL("INSERT INTO error_entries (id, subject, chapter, question, wrongAnswer, correctAnswer, analysis, difficulty, mastered, createdAt, updatedAt) VALUES (1, 'Math', '', 'Q1', '', '', '', 3, 0, 1000, 1000)")
        dbV1.execSQL("INSERT INTO review_records (id, errorEntryId, nextReviewAt, intervalDays, easeFactor, repetitionCount, lastReviewedAt, createdAt) VALUES (1, 1, 2000, 1, 2.5, 0, 0, 1000)")
        dbV1.execSQL("INSERT INTO app_settings (`key`, value, updatedAt) VALUES ('ai_api_key', 'sk-old', 1000)")
        dbV1.execSQL("INSERT INTO app_settings (`key`, value, updatedAt) VALUES ('ai_model', 'gpt-4', 1000)")

        dbV1.close()

        val dbV4 = helper.runMigrationsAndValidate(
            MathAgentDatabase.DATABASE_NAME, 4, true,
            MathAgentDatabase.MIGRATION_1_2, MathAgentDatabase.MIGRATION_2_3, MathAgentDatabase.MIGRATION_3_4
        )

        // Review record survived v1→v2 migration
        val cursorReview = dbV4.query("SELECT * FROM review_records WHERE errorEntryId = 1")
        assertTrue(cursorReview.moveToFirst())
        cursorReview.close()

        // ai_api_key preserved (runtime cleanup by AppContainer, not migration)
        val cursorKey = dbV4.query("SELECT value FROM app_settings WHERE `key` = 'ai_api_key'")
        assertTrue(cursorKey.moveToFirst())
        assertEquals("sk-old", cursorKey.getString(0))
        cursorKey.close()

        // ai_model survived
        val cursorModel = dbV4.query("SELECT value FROM app_settings WHERE `key` = 'ai_model'")
        assertTrue(cursorModel.moveToFirst())
        assertEquals("gpt-4", cursorModel.getString(0))
        cursorModel.close()

        dbV4.close()
    }
}
