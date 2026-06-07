package com.example.mathagent.di

import android.content.Context
import com.example.mathagent.data.ai.AiRepository
import com.example.mathagent.data.ai.MaterialChunkContextBuilder
import com.example.mathagent.data.backup.BackupService
import com.example.mathagent.data.local.LegacyApiKeyMigrator
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.SecureSettingsStore
import com.example.mathagent.data.repository.BackupRepository
import com.example.mathagent.data.repository.ChatRepository
import com.example.mathagent.data.repository.ErrorEntryRepository
import com.example.mathagent.data.repository.ExamRepository
import com.example.mathagent.data.material.MaterialImportService
import com.example.mathagent.data.repository.MaterialRepository
import com.example.mathagent.data.repository.ProblemRepository
import com.example.mathagent.data.repository.ReviewRepository
import com.example.mathagent.data.repository.SearchRepository
import com.example.mathagent.data.repository.SettingsRepository
import com.example.mathagent.data.repository.StudyPlanRepository

/**
 * Minimal manual dependency injection container.
 * Created once in MainActivity; holds all repositories and shared stores.
 *
 * @param databaseOverride if non-null, use this database instead of opening
 *                         the real one (for instrumented tests).
 */
class AppContainer(
    private val context: Context,
    databaseOverride: MathAgentDatabase? = null
) {

    val database: MathAgentDatabase = databaseOverride ?: MathAgentDatabase.getInstance(context)

    val secureSettingsStore: SecureSettingsStore = SecureSettingsStore(context)

    val errorEntryRepository = ErrorEntryRepository(
        database = database,
        errorEntryDao = database.errorEntryDao(),
        reviewRecordDao = database.reviewRecordDao()
    )

    val reviewRepository = ReviewRepository(
        reviewRecordDao = database.reviewRecordDao()
    )

    val settingsRepository = SettingsRepository(
        appSettingDao = database.appSettingDao()
    )

    val studyPlanRepository = StudyPlanRepository(
        studyPlanDao = database.studyPlanDao()
    )

    val materialRepository = MaterialRepository(
        database.materialDao(),
        database.materialChunkDao()
    )

    val materialImportService = MaterialImportService(
        context = context,
        materialDao = database.materialDao(),
        chunkDao = database.materialChunkDao(),
        database = database
    )

    val chatRepository = ChatRepository(
        chatMessageDao = database.chatMessageDao()
    )

    val problemRepository = ProblemRepository(
        problemRecordDao = database.problemRecordDao()
    )

    val examRepository = ExamRepository(
        database.examQuestionDao(),
        database.examAttemptDao()
    )

    val searchRepository = SearchRepository(
        errorEntryDao = database.errorEntryDao(),
        studyPlanDao = database.studyPlanDao(),
        materialDao = database.materialDao(),
        materialChunkDao = database.materialChunkDao()
    )

    val backupService = BackupService(database)

    val backupRepository = BackupRepository(
        backupLogDao = database.backupLogDao()
    )

    val aiRepository = AiRepository(
        settingsRepository = settingsRepository,
        errorEntryDao = database.errorEntryDao(),
        apiKeyProvider = { secureSettingsStore.getApiKey() },
        chunkContextBuilder = MaterialChunkContextBuilder(
            materialChunkDao = database.materialChunkDao(),
            materialDao = database.materialDao()
        )
    )

    init {
        LegacyApiKeyMigrator.migrate(settingsRepository, secureSettingsStore)
    }
}
