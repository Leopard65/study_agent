package com.example.mathagent.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.local.entity.ReviewRecord
import com.example.mathagent.data.repository.ErrorEntryRepository
import com.example.mathagent.data.repository.ReviewRepository
import com.example.mathagent.domain.model.ReviewQuality
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ReviewUiState(
    val dueReviews: List<ReviewRecord> = emptyList(),
    /** Lazily loaded error entries keyed by errorEntryId. */
    val errorEntries: Map<Long, ErrorEntry> = emptyMap(),
    val isLoading: Boolean = true,
    val message: String? = null
)

class ReviewViewModel(
    private val reviewRepository: ReviewRepository,
    private val errorEntryRepository: ErrorEntryRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ReviewUiState())
    val uiState: StateFlow<ReviewUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            reviewRepository.dueForReview.collect { reviews ->
                _uiState.value = _uiState.value.copy(
                    dueReviews = reviews,
                    isLoading = false
                )
                reviews.forEach { record ->
                    if (record.errorEntryId !in _uiState.value.errorEntries) {
                        loadErrorEntry(record.errorEntryId)
                    }
                }
            }
        }
    }

    private suspend fun loadErrorEntry(id: Long) {
        val entry = errorEntryRepository.getById(id) ?: return
        _uiState.value = _uiState.value.copy(
            errorEntries = _uiState.value.errorEntries + (id to entry)
        )
    }

    /** Call on screen resume to refresh time-sensitive data. */
    fun refresh() {
        reviewRepository.refreshTime()
    }

    /**
     * Mark a review as completed with the given quality level.
     *
     * @param record  The review record to update.
     * @param quality How well the student recalled the material.
     */
    fun markReviewed(record: ReviewRecord, quality: ReviewQuality) {
        viewModelScope.launch {
            try {
                reviewRepository.markReviewed(record, quality)
                reviewRepository.refreshTime()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "操作失败: ${e.message}")
            }
        }
    }

    /**
     * Skip this review — postpone it by 1 day without running the SM-2 algorithm.
     *
     * Unlike "Again" (which resets progress), skip simply delays the next
     * review without affecting easeFactor or repetitionCount.
     */
    fun skip(record: ReviewRecord) {
        viewModelScope.launch {
            try {
                val updated = record.copy(
                    nextReviewAt = System.currentTimeMillis() + 24 * 60 * 60 * 1000L
                )
                reviewRepository.update(updated)
                reviewRepository.refreshTime()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "操作失败: ${e.message}")
            }
        }
    }

    fun clearMessage() {
        _uiState.value = _uiState.value.copy(message = null)
    }
}
