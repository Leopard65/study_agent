package com.example.mathagent.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.repository.ErrorEntryRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch

data class ErrorListUiState(
    val errors: List<ErrorEntry> = emptyList(),
    val isLoading: Boolean = true,
    val message: String? = null
)

class ErrorListViewModel(
    private val errorEntryRepository: ErrorEntryRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ErrorListUiState())
    val uiState: StateFlow<ErrorListUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            errorEntryRepository.getAll()
                .catch { e -> _uiState.value = _uiState.value.copy(message = e.message) }
                .collect { errors ->
                    _uiState.value = _uiState.value.copy(errors = errors, isLoading = false)
                }
        }
    }

    fun addError(question: String, subject: String, wrongAnswer: String, correctAnswer: String) {
        viewModelScope.launch {
            try {
                errorEntryRepository.insert(
                    ErrorEntry(
                        question = question,
                        subject = subject,
                        wrongAnswer = wrongAnswer,
                        correctAnswer = correctAnswer
                    )
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "添加失败: ${e.message}")
            }
        }
    }

    fun toggleMastered(id: Long) {
        viewModelScope.launch {
            try {
                errorEntryRepository.toggleMastered(id)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "操作失败: ${e.message}")
            }
        }
    }

    fun deleteError(error: ErrorEntry) {
        viewModelScope.launch {
            try {
                errorEntryRepository.delete(error)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "删除失败: ${e.message}")
            }
        }
    }

    fun clearMessage() {
        _uiState.value = _uiState.value.copy(message = null)
    }
}
