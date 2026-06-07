package com.example.mathagent.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mathagent.data.ai.AiErrorType
import com.example.mathagent.data.ai.AiException
import com.example.mathagent.data.ai.AiRepository
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.repository.ErrorEntryRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ErrorDetailUiState(
    val errorEntry: ErrorEntry? = null,
    val isLoading: Boolean = true,
    val isAiAnalyzing: Boolean = false,
    val isAiConfigured: Boolean = false,
    val aiAnalysis: String? = null,
    val message: String? = null
)

class ErrorDetailViewModel(
    private val errorEntryRepository: ErrorEntryRepository,
    private val aiRepository: AiRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(ErrorDetailUiState())
    val uiState: StateFlow<ErrorDetailUiState> = _uiState.asStateFlow()

    fun loadError(errorId: Long) {
        viewModelScope.launch {
            val entry = errorEntryRepository.getById(errorId)
            val isConfigured = aiRepository.isAiConfigured()
            _uiState.value = _uiState.value.copy(
                errorEntry = entry,
                isLoading = false,
                isAiConfigured = isConfigured,
                aiAnalysis = entry?.analysis?.ifBlank { null }
            )
        }
    }

    fun requestAiAnalysis() {
        val entry = _uiState.value.errorEntry ?: return
        if (_uiState.value.isAiAnalyzing) return

        _uiState.value = _uiState.value.copy(isAiAnalyzing = true, message = null)

        viewModelScope.launch {
            try {
                val analysis = aiRepository.explainAndSave(entry.id)
                _uiState.value = _uiState.value.copy(
                    isAiAnalyzing = false,
                    aiAnalysis = analysis,
                    errorEntry = _uiState.value.errorEntry?.copy(analysis = analysis)
                )
            } catch (e: AiException) {
                _uiState.value = _uiState.value.copy(
                    isAiAnalyzing = false,
                    message = mapAiError(e)
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isAiAnalyzing = false,
                    message = "未知错误: ${e.message}"
                )
            }
        }
    }

    fun clearMessage() {
        _uiState.value = _uiState.value.copy(message = null)
    }

    companion object {
        fun mapAiError(e: AiException): String = when (e.type) {
            AiErrorType.NOT_CONFIGURED -> "请先在设置中配置 API Key"
            AiErrorType.AUTH_ERROR -> "API Key 无效，请检查设置"
            AiErrorType.RATE_LIMIT -> "请求过于频繁，请稍后再试"
            AiErrorType.NETWORK_ERROR -> "网络连接失败，请检查网络"
            AiErrorType.SERVER_ERROR -> "AI 服务暂时不可用，请稍后再试"
            AiErrorType.EMPTY_RESPONSE -> "AI 返回了空结果"
            AiErrorType.PARSE_ERROR -> "AI 响应格式异常"
            AiErrorType.UNKNOWN -> e.message ?: "未知错误"
        }
    }
}
