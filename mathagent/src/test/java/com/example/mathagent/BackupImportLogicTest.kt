package com.example.mathagent

import com.example.mathagent.data.backup.ImportMode
import com.example.mathagent.ui.screens.settings.ImportAction
import com.example.mathagent.ui.screens.settings.cancelImportDialog
import com.example.mathagent.ui.screens.settings.confirmReplaceImport
import com.example.mathagent.ui.screens.settings.handleImportedJson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit tests for backup import logic.
 * Tests pure functions without UI dependencies.
 */
class BackupImportLogicTest {

    @Test
    fun handleImportedJson_defaultMode_isMergeSkipExisting() {
        // Default import mode should be MERGE_SKIP_EXISTING
        val action = handleImportedJson(ImportMode.MERGE_SKIP_EXISTING, "{}")
        assertTrue(action is ImportAction.ImportNow)
        assertEquals(ImportMode.MERGE_SKIP_EXISTING, (action as ImportAction.ImportNow).mode)
    }

    @Test
    fun handleImportedJson_mergeMode_importsImmediately() {
        val json = """{"materials": []}"""
        val action = handleImportedJson(ImportMode.MERGE_SKIP_EXISTING, json)

        assertTrue(action is ImportAction.ImportNow)
        assertEquals(json, (action as ImportAction.ImportNow).json)
        assertEquals(ImportMode.MERGE_SKIP_EXISTING, action.mode)
    }

    @Test
    fun handleImportedJson_replaceMode_showsConfirmDialog() {
        val json = """{"materials": []}"""
        val action = handleImportedJson(ImportMode.REPLACE_ALL, json)

        assertTrue(action is ImportAction.ShowConfirmDialog)
        assertEquals(json, (action as ImportAction.ShowConfirmDialog).json)
    }

    @Test
    fun handleImportedJson_replaceMode_doesNotImportImmediately() {
        val json = """{"materials": []}"""
        val action = handleImportedJson(ImportMode.REPLACE_ALL, json)

        // Should NOT be ImportNow - should be ShowConfirmDialog
        assertTrue(action !is ImportAction.ImportNow)
    }

    @Test
    fun handleImportedJson_nullJson_returnsNoOp() {
        val action = handleImportedJson(ImportMode.MERGE_SKIP_EXISTING, null)
        assertTrue(action is ImportAction.NoOp)
    }

    @Test
    fun handleImportedJson_blankJson_returnsNoOp() {
        val action = handleImportedJson(ImportMode.MERGE_SKIP_EXISTING, "  ")
        assertTrue(action is ImportAction.NoOp)
    }

    @Test
    fun confirmReplaceImport_returnsImportNowWithReplaceAll() {
        val json = """{"materials": [{"id": 1}]}"""
        val action = confirmReplaceImport(json)

        assertTrue(action is ImportAction.ImportNow)
        val importNow = action as ImportAction.ImportNow
        assertEquals(json, importNow.json)
        assertEquals(ImportMode.REPLACE_ALL, importNow.mode)
    }

    @Test
    fun cancelImportDialog_returnsNoOp() {
        val action = cancelImportDialog()
        assertTrue(action is ImportAction.NoOp)
    }

    @Test
    fun handleImportedJson_mergeMode_ignoresPendingState() {
        // MERGE mode should always import immediately, regardless of any pending state
        val json = """{"test": true}"""
        val action1 = handleImportedJson(ImportMode.MERGE_SKIP_EXISTING, json)
        val action2 = handleImportedJson(ImportMode.MERGE_SKIP_EXISTING, json)

        // Both should be ImportNow, no state leaking between calls
        assertTrue(action1 is ImportAction.ImportNow)
        assertTrue(action2 is ImportAction.ImportNow)
    }
}
