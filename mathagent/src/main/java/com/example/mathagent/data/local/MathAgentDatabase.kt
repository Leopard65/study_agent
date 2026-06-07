package com.example.mathagent.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import com.example.mathagent.data.local.dao.AppSettingDao
import com.example.mathagent.data.local.dao.BackupLogDao
import com.example.mathagent.data.local.dao.ChatMessageDao
import com.example.mathagent.data.local.dao.ErrorEntryDao
import com.example.mathagent.data.local.dao.ExamAttemptDao
import com.example.mathagent.data.local.dao.ExamQuestionDao
import com.example.mathagent.data.local.dao.MaterialChunkDao
import com.example.mathagent.data.local.dao.MaterialDao
import com.example.mathagent.data.local.dao.ProblemRecordDao
import com.example.mathagent.data.local.dao.ReviewRecordDao
import com.example.mathagent.data.local.dao.StudyPlanDao
import com.example.mathagent.data.local.entity.AppSetting
import com.example.mathagent.data.local.entity.BackupLog
import com.example.mathagent.data.local.entity.ChatMessage
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.local.entity.ExamAttempt
import com.example.mathagent.data.local.entity.ExamQuestion
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.local.entity.MaterialChunk
import com.example.mathagent.data.local.entity.ProblemRecord
import com.example.mathagent.data.local.entity.ReviewRecord
import com.example.mathagent.data.local.entity.StudyPlan

@Database(
    entities = [
        Material::class,
        MaterialChunk::class,
        ErrorEntry::class,
        StudyPlan::class,
        ReviewRecord::class,
        ChatMessage::class,
        ProblemRecord::class,
        ExamQuestion::class,
        ExamAttempt::class,
        AppSetting::class,
        BackupLog::class
    ],
    version = 4,
    exportSchema = true
)
abstract class MathAgentDatabase : RoomDatabase() {

    abstract fun materialDao(): MaterialDao
    abstract fun materialChunkDao(): MaterialChunkDao
    abstract fun errorEntryDao(): ErrorEntryDao
    abstract fun studyPlanDao(): StudyPlanDao
    abstract fun reviewRecordDao(): ReviewRecordDao
    abstract fun chatMessageDao(): ChatMessageDao
    abstract fun problemRecordDao(): ProblemRecordDao
    abstract fun examQuestionDao(): ExamQuestionDao
    abstract fun examAttemptDao(): ExamAttemptDao
    abstract fun appSettingDao(): AppSettingDao
    abstract fun backupLogDao(): BackupLogDao

    companion object {
        const val DATABASE_NAME = "math_agent.db"

        @Volatile
        private var INSTANCE: MathAgentDatabase? = null

        /**
         * Migration from v1 to v2:
         * - Preserve valid review_records (matching existing error_entries)
         * - Delete orphan review_records that would violate the new FK constraint
         * - Recreate table with FOREIGN KEY + INDEX, matching Room v2 schema exactly
         */
        val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                // 1. Delete orphaned review records (no matching error_entry)
                db.execSQL(
                    "DELETE FROM review_records WHERE errorEntryId NOT IN (SELECT id FROM error_entries)"
                )
                // 2. Rename old table
                db.execSQL("ALTER TABLE review_records RENAME TO _review_records_old")
                // 3. Create new table matching Room v2 schema exactly (no DEFAULTs)
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS `review_records` (" +
                        "`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                        "`errorEntryId` INTEGER NOT NULL, " +
                        "`nextReviewAt` INTEGER NOT NULL, " +
                        "`intervalDays` INTEGER NOT NULL, " +
                        "`easeFactor` REAL NOT NULL, " +
                        "`repetitionCount` INTEGER NOT NULL, " +
                        "`lastReviewedAt` INTEGER NOT NULL, " +
                        "`createdAt` INTEGER NOT NULL, " +
                        "FOREIGN KEY(`errorEntryId`) REFERENCES `error_entries`(`id`) " +
                        "ON UPDATE NO ACTION ON DELETE CASCADE)"
                )
                // 4. Copy surviving data
                db.execSQL(
                    "INSERT INTO review_records (id, errorEntryId, nextReviewAt, intervalDays, " +
                        "easeFactor, repetitionCount, lastReviewedAt, createdAt) " +
                        "SELECT id, errorEntryId, nextReviewAt, intervalDays, " +
                        "easeFactor, repetitionCount, lastReviewedAt, createdAt " +
                        "FROM _review_records_old"
                )
                // 5. Drop old table
                db.execSQL("DROP TABLE _review_records_old")
                // 6. Create index for FK column
                db.execSQL("CREATE INDEX IF NOT EXISTS `index_review_records_errorEntryId` ON `review_records` (`errorEntryId`)")
            }
        }

        /**
         * Migration from v2 to v3:
         * - Add 'operation' and 'message' columns to backup_logs
         */
        val MIGRATION_2_3 = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("ALTER TABLE backup_logs ADD COLUMN operation TEXT NOT NULL DEFAULT 'export'")
                db.execSQL("ALTER TABLE backup_logs ADD COLUMN message TEXT NOT NULL DEFAULT ''")
            }
        }

        /**
         * Migration from v3 to v4:
         * - Schema is unchanged (app_settings table structure identical).
         * - ai_api_key cleanup is handled at runtime by AppContainer.migrateLegacyApiKey()
         *   AFTER Room migration completes, ensuring the key can be read from Room
         *   and written to SecureSettingsStore before deletion.
         */
        val MIGRATION_3_4 = object : Migration(3, 4) {
            override fun migrate(db: SupportSQLiteDatabase) {
                // No-op: schema unchanged. Data migration handled at app startup.
            }
        }

        fun getInstance(context: Context): MathAgentDatabase {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    MathAgentDatabase::class.java,
                    DATABASE_NAME
                ).addMigrations(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4).build().also { INSTANCE = it }
            }
        }

        /**
         * For testing: creates an in-memory database that does not persist.
         */
        fun createInMemory(context: Context): MathAgentDatabase {
            return Room.inMemoryDatabaseBuilder(
                context.applicationContext,
                MathAgentDatabase::class.java
            ).allowMainThreadQueries().build()
        }
    }
}
