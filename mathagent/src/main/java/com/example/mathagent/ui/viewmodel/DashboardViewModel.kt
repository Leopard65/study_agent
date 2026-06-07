package com.example.mathagent.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mathagent.data.repository.ErrorEntryRepository
import com.example.mathagent.data.repository.MaterialRepository
import com.example.mathagent.data.repository.ReviewRepository
import com.example.mathagent.data.repository.StudyPlanRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class DashboardUiState(
    val unmasteredErrorCount: Int = 0,
    val dueReviewCount: Int = 0,
    val activePlanCount: Int = 0,
    val materialCount: Int = 0,
    val isLoading: Boolean = true,
    val message: String? = null
)

class DashboardViewModel(
    private val reviewRepository: ReviewRepository,
    errorEntryRepository: ErrorEntryRepository,
    studyPlanRepository: StudyPlanRepository,
    materialRepository: MaterialRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(DashboardUiState())
    val uiState: StateFlow<DashboardUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            errorEntryRepository.countUnmastered().collect { count ->
                _uiState.value = _uiState.value.copy(
                    unmasteredErrorCount = count,
                    isLoading = false
                )
            }
        }
        viewModelScope.launch {
            reviewRepository.dueCount.collect { count ->
                _uiState.value = _uiState.value.copy(dueReviewCount = count)
            }
        }
        viewModelScope.launch {
            studyPlanRepository.countActive().collect { count ->
                _uiState.value = _uiState.value.copy(activePlanCount = count)
            }
        }
        viewModelScope.launch {
            materialRepository.materialCount().collect { count ->
                _uiState.value = _uiState.value.copy(materialCount = count)
            }
        }
    }

    /** Call on screen resume to refresh time-sensitive review count. */
    fun refresh() {
        viewModelScope.launch { reviewRepository.refreshTime() }
    }

    fun clearMessage() {
        _uiState.value = _uiState.value.copy(message = null)
    }
}
