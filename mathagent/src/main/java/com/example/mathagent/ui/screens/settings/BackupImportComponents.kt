package com.example.mathagent.ui.screens.settings

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import com.example.mathagent.data.backup.ImportMode

/**
 * Import mode selector - extracts the radio button group for testability.
 */
@Composable
fun ImportModeSelector(
    selectedMode: ImportMode,
    onModeSelected: (ImportMode) -> Unit,
    modifier: Modifier = Modifier
) {
    Column(modifier = modifier) {
        Text(
            text = "导入模式",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .fillMaxWidth()
                .clickable { onModeSelected(ImportMode.MERGE_SKIP_EXISTING) }
                .testTag("import-mode-merge-row")
        ) {
            RadioButton(
                selected = selectedMode == ImportMode.MERGE_SKIP_EXISTING,
                onClick = { onModeSelected(ImportMode.MERGE_SKIP_EXISTING) },
                modifier = Modifier.testTag("import-mode-merge")
            )
            Column(modifier = Modifier.weight(1f)) {
                Text("合并导入（推荐）", style = MaterialTheme.typography.bodyMedium)
                Text("跳过已存在的数据，保留本机内容", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier
                .fillMaxWidth()
                .clickable { onModeSelected(ImportMode.REPLACE_ALL) }
                .testTag("import-mode-replace-row")
        ) {
            RadioButton(
                selected = selectedMode == ImportMode.REPLACE_ALL,
                onClick = { onModeSelected(ImportMode.REPLACE_ALL) },
                modifier = Modifier.testTag("import-mode-replace")
            )
            Column(modifier = Modifier.weight(1f)) {
                Text("替换全部数据", style = MaterialTheme.typography.bodyMedium)
                Text("删除本机所有学习数据后导入备份", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

/**
 * Handles imported JSON based on selected mode.
 * Returns: ImportAction indicating what to do next.
 */
sealed class ImportAction {
    data object NoOp : ImportAction()
    data class ImportNow(val json: String, val mode: ImportMode) : ImportAction()
    data class ShowConfirmDialog(val json: String) : ImportAction()
}

/**
 * Pure function: determines import action based on mode and JSON content.
 * This is easily testable without UI.
 */
fun handleImportedJson(
    selectedMode: ImportMode,
    json: String?
): ImportAction {
    if (json.isNullOrBlank()) return ImportAction.NoOp
    return when (selectedMode) {
        ImportMode.MERGE_SKIP_EXISTING -> ImportAction.ImportNow(json, ImportMode.MERGE_SKIP_EXISTING)
        ImportMode.REPLACE_ALL -> ImportAction.ShowConfirmDialog(json)
    }
}

/**
 * Pure function: confirms REPLACE_ALL import.
 */
fun confirmReplaceImport(json: String): ImportAction.ImportNow {
    return ImportAction.ImportNow(json, ImportMode.REPLACE_ALL)
}

/**
 * Pure function: cancels import dialog.
 */
fun cancelImportDialog(): ImportAction.NoOp {
    return ImportAction.NoOp
}
