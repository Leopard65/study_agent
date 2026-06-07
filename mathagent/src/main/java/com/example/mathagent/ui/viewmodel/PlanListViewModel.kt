package com.example.mathagent.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mathagent.data.local.entity.StudyPlan
import com.example.mathagent.data.repository.StudyPlanRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch

data class PlanListUiState(
    val plans: List<StudyPlan> = emptyList(),
    val isLoading: Boolean = true,
    val message: String? = null
)

class PlanListViewModel(
    private val studyPlanRepository: StudyPlanRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(PlanListUiState())
    val uiState: StateFlow<PlanListUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            studyPlanRepository.getAll()
                .catch { e -> _uiState.value = _uiState.value.copy(message = e.message) }
                .collect { plans ->
                    _uiState.value = _uiState.value.copy(plans = plans, isLoading = false)
                }
        }
    }

    fun addPlan(title: String, subject: String, description: String) {
        viewModelScope.launch {
            try {
                studyPlanRepository.insert(
                    StudyPlan(title = title, subject = subject, description = description)
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "添加失败: ${e.message}")
            }
        }
    }

    fun updatePlan(plan: StudyPlan) {
        viewModelScope.launch {
            try {
                studyPlanRepository.update(plan.copy(updatedAt = System.currentTimeMillis()))
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "更新失败: ${e.message}")
            }
        }
    }

    fun toggleCompleted(id: Long) {
        viewModelScope.launch {
            try {
                studyPlanRepository.toggleCompleted(id)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "操作失败: ${e.message}")
            }
        }
    }

    fun deletePlan(plan: StudyPlan) {
        viewModelScope.launch {
            try {
                studyPlanRepository.delete(plan)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "删除失败: ${e.message}")
            }
        }
    }

    fun clearMessage() {
        _uiState.value = _uiState.value.copy(message = null)
    }
}
