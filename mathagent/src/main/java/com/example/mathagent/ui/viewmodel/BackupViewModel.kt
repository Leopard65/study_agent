package com.example.mathagent.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mathagent.data.backup.BackupService
import com.example.mathagent.data.backup.ImportMode
import com.example.mathagent.data.local.dao.BackupLogDao
import com.example.mathagent.data.local.entity.BackupLog
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class BackupUiState(
    val isExporting: Boolean = false,
    val isImporting: Boolean = false,
    val message: String? = null,
    /** Exported JSON string, consumed by the UI layer for file writing. */
    val exportedJson: String? = null,
    /** Set to true when export is ready; UI should reset after consuming. */
    val exportReady: Boolean = false
)

class BackupViewModel(
    private val backupService: BackupService,
    private val backupLogDao: BackupLogDao
) : ViewModel() {

    private val _uiState = MutableStateFlow(BackupUiState())
    val uiState: StateFlow<BackupUiState> = _uiState.asStateFlow()

    val latestLog: StateFlow<BackupLog?> = backupLogDao.getLatestFlow()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    fun export() {
        if (_uiState.value.isExporting) return
        _uiState.value = _uiState.value.copy(isExporting = true, message = null)

        viewModelScope.launch {
            try {
                val json = backupService.exportToJson()
                _uiState.value = _uiState.value.copy(
                    isExporting = false,
                    exportedJson = json,
                    exportReady = true,
                    message = null
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isExporting = false,
                    message = "导出失败: ${e.message}"
                )
            }
        }
    }

    /** Called after UI has consumed the exported JSON (written to file). */
    fun onExportConsumed(fileName: String, fileSize: Long) {
        _uiState.value = _uiState.value.copy(exportedJson = null, exportReady = false)
        viewModelScope.launch {
            backupLogDao.insert(
                BackupLog(fileName = fileName, fileSize = fileSize, operation = "export")
            )
        }
    }

    fun import(json: String, mode: ImportMode) {
        if (_uiState.value.isImporting) return
        _uiState.value = _uiState.value.copy(isImporting = true, message = null)

        viewModelScope.launch {
            try {
                val count = backupService.importFromJson(json, mode)
                backupLogDao.insert(
                    BackupLog(fileName = "import", operation = "import", message = "导入 $count 条记录")
                )
                _uiState.value = _uiState.value.copy(
                    isImporting = false,
                    message = "导入成功，共 $count 条记录"
                )
            } catch (e: Exception) {
                backupLogDao.insert(
                    BackupLog(fileName = "import", operation = "import", status = "failed", message = e.message ?: "unknown")
                )
                _uiState.value = _uiState.value.copy(
                    isImporting = false,
                    message = "导入失败: ${e.message}"
                )
            }
        }
    }

    /** Called when user cancels the export file picker. Clears export state silently. */
    fun cancelExport() {
        _uiState.value = _uiState.value.copy(exportedJson = null, exportReady = false, isExporting = false)
    }

    /** Called when the SAF file write fails during export. */
    fun onExportFailed(message: String) {
        _uiState.value = _uiState.value.copy(
            exportedJson = null, exportReady = false, isExporting = false,
            message = "导出写入失败: $message"
        )
    }

    /** Called when the SAF file read fails during import. */
    fun onImportFileReadFailed(message: String) {
        _uiState.value = _uiState.value.copy(
            isImporting = false,
            message = "导入读取失败: $message"
        )
    }

    fun clearMessage() {
        _uiState.value = _uiState.value.copy(message = null)
    }
}
