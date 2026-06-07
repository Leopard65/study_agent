package com.example.mathagent.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mathagent.data.local.SecureSettingsStore
import com.example.mathagent.data.repository.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class SettingsUiState(
    /** Current form values (may differ from saved values). */
    val baseUrl: String = "",
    val apiKey: String = "",
    val model: String = "",
    /** Whether the initial load has completed. */
    val isLoading: Boolean = true,
    /** Whether a save operation is in progress. */
    val isSaving: Boolean = false,
    /** Non-null means show this message to the user (success or error). */
    val message: String? = null
)

class SettingsViewModel(
    private val settingsRepository: SettingsRepository,
    private val secureSettingsStore: SecureSettingsStore
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    /** Load saved settings into form fields. Call from LaunchedEffect. */
    fun loadSettings() {
        viewModelScope.launch {
            try {
                val baseUrl = settingsRepository.getBaseUrl() ?: ""
                val apiKey = secureSettingsStore.getApiKey() ?: ""
                val model = settingsRepository.getModel() ?: ""
                _uiState.value = _uiState.value.copy(
                    baseUrl = baseUrl,
                    apiKey = apiKey,
                    model = model,
                    isLoading = false
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isLoading = false,
                    message = "加载设置失败: ${e.message}"
                )
            }
        }
    }

    fun updateBaseUrl(value: String) {
        _uiState.value = _uiState.value.copy(baseUrl = value)
    }

    fun updateApiKey(value: String) {
        _uiState.value = _uiState.value.copy(apiKey = value)
    }

    fun updateModel(value: String) {
        _uiState.value = _uiState.value.copy(model = value)
    }

    /** Save all settings. Base URL, model → Room; API Key → SecureSettingsStore.
     *  Blank baseUrl/model are saved as empty string; AiRepository treats
     *  empty/null as "use default" when calling the AI API. */
    fun save() {
        val state = _uiState.value
        if (state.isSaving) return

        _uiState.value = state.copy(isSaving = true, message = null)

        viewModelScope.launch {
            try {
                settingsRepository.setBaseUrl(state.baseUrl.trim())
                settingsRepository.setModel(state.model.trim())

                val trimmedKey = state.apiKey.trim()
                if (trimmedKey.isEmpty()) {
                    secureSettingsStore.clearApiKey()
                } else {
                    secureSettingsStore.setApiKey(trimmedKey)
                }

                _uiState.value = _uiState.value.copy(
                    isSaving = false,
                    message = "保存成功"
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isSaving = false,
                    message = "保存失败: ${e.message}"
                )
            }
        }
    }

    fun clearMessage() {
        _uiState.value = _uiState.value.copy(message = null)
    }
}
