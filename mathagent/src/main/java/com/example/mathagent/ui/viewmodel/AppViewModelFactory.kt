package com.example.mathagent.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.example.mathagent.di.AppContainer

/**
 * Generic ViewModelFactory that creates ViewModels using AppContainer dependencies.
 * Each ViewModel registers its creator lambda in [creators].
 */
class AppViewModelFactory(private val container: AppContainer) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    private val creators: Map<Class<out ViewModel>, () -> ViewModel> = mapOf(
        DashboardViewModel::class.java to {
            DashboardViewModel(
                container.reviewRepository,
                container.errorEntryRepository,
                container.studyPlanRepository,
                container.materialRepository
            )
        },
        ErrorListViewModel::class.java to {
            ErrorListViewModel(container.errorEntryRepository)
        },
        ReviewViewModel::class.java to {
            ReviewViewModel(container.reviewRepository, container.errorEntryRepository)
        },
        PlanListViewModel::class.java to {
            PlanListViewModel(container.studyPlanRepository)
        },
        MaterialListViewModel::class.java to {
            MaterialListViewModel(container.materialRepository, container.materialImportService)
        },
        SettingsViewModel::class.java to {
            SettingsViewModel(container.settingsRepository, container.secureSettingsStore)
        },
        SearchViewModel::class.java to {
            SearchViewModel(container.searchRepository)
        },
        BackupViewModel::class.java to {
            BackupViewModel(container.backupService, container.database.backupLogDao())
        },
        ErrorDetailViewModel::class.java to {
            ErrorDetailViewModel(container.errorEntryRepository, container.aiRepository)
        },
        MaterialDetailViewModel::class.java to {
            MaterialDetailViewModel(container.materialRepository)
        }
    )

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        val creator = creators[modelClass]
            ?: throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
        return creator() as T
    }
}
