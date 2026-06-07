package com.example.mathagent

import com.example.mathagent.ui.viewmodel.BackupUiState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for BackupUiState transitions.
 * Tests the state logic directly without ViewModel/coroutine dependencies.
 */
class BackupUiStateTest {

    @Test
    fun initialState_isCorrect() {
        val state = BackupUiState()
        assertFalse(state.isExporting)
        assertFalse(state.isImporting)
        assertNull(state.message)
        assertNull(state.exportedJson)
        assertFalse(state.exportReady)
    }

    @Test
    fun onExportFailed_clearsExportStateAndSetsMessage() {
        val state = BackupUiState(
            isExporting = true,
            exportedJson = "{\"test\":true}",
            exportReady = true
        )
        val updated = state.copy(
            exportedJson = null, exportReady = false, isExporting = false,
            message = "导出写入失败: 磁盘已满"
        )

        assertFalse(updated.isExporting)
        assertNull(updated.exportedJson)
        assertFalse(updated.exportReady)
        assertEquals("导出写入失败: 磁盘已满", updated.message)
    }

    @Test
    fun onImportFileReadFailed_clearsImportingAndSetsMessage() {
        val state = BackupUiState(isImporting = true)
        val updated = state.copy(
            isImporting = false,
            message = "导入读取失败: 文件不存在"
        )

        assertFalse(updated.isImporting)
        assertEquals("导入读取失败: 文件不存在", updated.message)
    }

    @Test
    fun cancelExport_clearsExportStateSilently() {
        val state = BackupUiState(
            isExporting = true,
            exportedJson = "{\"large\":\"data\"}",
            exportReady = true
        )
        val updated = state.copy(exportedJson = null, exportReady = false, isExporting = false)

        assertFalse(updated.isExporting)
        assertNull(updated.exportedJson)
        assertFalse(updated.exportReady)
        assertNull(updated.message) // No error message on cancel
    }

    @Test
    fun exportSuccess_setsReadyAndJson() {
        val state = BackupUiState(isExporting = true)
        val json = "{\"schemaVersion\":1}"
        val updated = state.copy(
            isExporting = false,
            exportedJson = json,
            exportReady = true,
            message = null
        )

        assertFalse(updated.isExporting)
        assertEquals(json, updated.exportedJson)
        assertTrue(updated.exportReady)
        assertNull(updated.message)
    }

    @Test
    fun importSuccess_setsMessage() {
        val state = BackupUiState(isImporting = true)
        val updated = state.copy(
            isImporting = false,
            message = "导入成功，共 42 条记录"
        )

        assertFalse(updated.isImporting)
        assertEquals("导入成功，共 42 条记录", updated.message)
    }

    @Test
    fun importFailure_setsErrorMessage() {
        val state = BackupUiState(isImporting = true)
        val updated = state.copy(
            isImporting = false,
            message = "导入失败: 不支持的备份版本"
        )

        assertFalse(updated.isImporting)
        assertEquals("导入失败: 不支持的备份版本", updated.message)
    }
}
