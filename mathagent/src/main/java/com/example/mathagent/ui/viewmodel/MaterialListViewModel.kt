package com.example.mathagent.ui.viewmodel

import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.data.material.ImportException
import com.example.mathagent.data.material.MaterialImportService
import com.example.mathagent.data.repository.MaterialRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.launch

data class MaterialListUiState(
    val materials: List<Material> = emptyList(),
    val isLoading: Boolean = true,
    val isImporting: Boolean = false,
    val message: String? = null
)

class MaterialListViewModel(
    private val materialRepository: MaterialRepository,
    private val importService: MaterialImportService
) : ViewModel() {

    private val _uiState = MutableStateFlow(MaterialListUiState())
    val uiState: StateFlow<MaterialListUiState> = _uiState.asStateFlow()

    init {
        viewModelScope.launch {
            materialRepository.getAllMaterials()
                .catch { e -> _uiState.value = _uiState.value.copy(message = e.message) }
                .collect { materials ->
                    _uiState.value = _uiState.value.copy(materials = materials, isLoading = false)
                }
        }
    }

    fun importFile(uri: Uri) {
        if (_uiState.value.isImporting) return
        _uiState.value = _uiState.value.copy(isImporting = true, message = null)

        viewModelScope.launch {
            try {
                val material = importService.importFile(uri)
                _uiState.value = _uiState.value.copy(
                    isImporting = false,
                    message = "导入成功: ${material.title}"
                )
            } catch (e: ImportException) {
                _uiState.value = _uiState.value.copy(
                    isImporting = false,
                    message = e.message
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isImporting = false,
                    message = "导入失败: ${e.message}"
                )
            }
        }
    }

    fun addMaterial(title: String, subject: String, description: String) {
        viewModelScope.launch {
            try {
                materialRepository.insertMaterial(
                    Material(title = title, subject = subject, description = description)
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "添加失败: ${e.message}")
            }
        }
    }

    fun updateMaterial(material: Material) {
        viewModelScope.launch {
            try {
                materialRepository.updateMaterial(material.copy(updatedAt = System.currentTimeMillis()))
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "更新失败: ${e.message}")
            }
        }
    }

    fun deleteMaterial(material: Material) {
        viewModelScope.launch {
            try {
                importService.deleteMaterial(material)
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(message = "删除失败: ${e.message}")
            }
        }
    }

    fun clearMessage() {
        _uiState.value = _uiState.value.copy(message = null)
    }
}
