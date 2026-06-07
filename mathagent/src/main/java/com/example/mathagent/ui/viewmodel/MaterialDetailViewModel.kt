package com.example.mathagent.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.local.entity.MaterialChunk
import com.example.mathagent.data.repository.MaterialRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class MaterialDetailUiState(
    val material: Material? = null,
    val chunks: List<MaterialChunk> = emptyList(),
    val isLoading: Boolean = true,
    val highlightChunkIndex: Int? = null,
    val message: String? = null
)

class MaterialDetailViewModel(
    private val materialRepository: MaterialRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(MaterialDetailUiState())
    val uiState: StateFlow<MaterialDetailUiState> = _uiState.asStateFlow()

    /** Track the current load job so repeated calls cancel the previous one. */
    private var loadJob: Job? = null

    fun loadMaterial(materialId: Long, highlightChunkIndex: Int? = null) {
        // Cancel any in-flight load to prevent stale results
        loadJob?.cancel()
        loadJob = viewModelScope.launch {
            val material = materialRepository.getMaterial(materialId)
            if (material == null) {
                _uiState.value = MaterialDetailUiState(isLoading = false, message = "资料不存在")
                return@launch
            }
            // One-shot fetch — no lingering collector
            val chunks = materialRepository.getChunksSync(materialId)
            _uiState.value = MaterialDetailUiState(
                material = material,
                chunks = chunks,
                isLoading = false,
                highlightChunkIndex = highlightChunkIndex
            )
        }
    }

    fun clearMessage() {
        _uiState.value = _uiState.value.copy(message = null)
    }
}
