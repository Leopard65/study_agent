package com.example.mathagent.ui.screens.settings

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.RadioButton
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.mathagent.LocalViewModelFactory
import com.example.mathagent.data.backup.ImportMode
import com.example.mathagent.ui.viewmodel.BackupViewModel
import com.example.mathagent.ui.viewmodel.SettingsViewModel
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun SettingsScreen(
    modifier: Modifier = Modifier,
    settingsViewModel: SettingsViewModel = viewModel(factory = LocalViewModelFactory.current),
    backupViewModel: BackupViewModel = viewModel(factory = LocalViewModelFactory.current)
) {
    val settingsState by settingsViewModel.uiState.collectAsStateWithLifecycle()
    val backupState by backupViewModel.uiState.collectAsStateWithLifecycle()
    val latestLog by backupViewModel.latestLog.collectAsStateWithLifecycle()
    var showApiKey by remember { mutableStateOf(false) }
    val context = LocalContext.current

    // Import mode selection state
    var selectedImportMode by remember { mutableStateOf(ImportMode.MERGE_SKIP_EXISTING) }
    // Pending import JSON waiting for REPLACE_ALL confirmation
    var pendingReplaceJson by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        settingsViewModel.loadSettings()
    }

    // Export file launcher
    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/json")
    ) { uri: Uri? ->
        if (uri == null) {
            // User cancelled — clean up export state
            backupViewModel.cancelExport()
            return@rememberLauncherForActivityResult
        }
        val json = backupState.exportedJson ?: return@rememberLauncherForActivityResult
        try {
            val os = context.contentResolver.openOutputStream(uri)
            if (os == null) {
                backupViewModel.onExportFailed("无法打开导出文件")
                return@rememberLauncherForActivityResult
            }
            val bytes = json.toByteArray(Charsets.UTF_8)
            os.use { it.write(bytes) }
            backupViewModel.onExportConsumed(uri.lastPathSegment ?: "backup.json", bytes.size.toLong())
        } catch (e: Exception) {
            backupViewModel.onExportFailed(e.message ?: "未知错误")
        }
    }

    // Import file launcher
    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        try {
            val ips = context.contentResolver.openInputStream(uri)
            if (ips == null) {
                backupViewModel.onImportFileReadFailed("无法打开导入文件")
                return@rememberLauncherForActivityResult
            }
            val json = ips.use { it.bufferedReader().readText() }
            // Use pure logic from BackupImportComponents
            when (val action = handleImportedJson(selectedImportMode, json)) {
                is ImportAction.ImportNow -> {
                    backupViewModel.import(action.json, action.mode)
                }
                is ImportAction.ShowConfirmDialog -> {
                    pendingReplaceJson = action.json
                }
                is ImportAction.NoOp -> { /* no-op */ }
            }
        } catch (e: Exception) {
            backupViewModel.onImportFileReadFailed(e.message ?: "未知错误")
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .testTag("screen-settings")
            .background(MaterialTheme.colorScheme.background)
            .verticalScroll(rememberScrollState())
            .padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        Text(
            text = "设置",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onBackground
        )

        // ---- AI Config Section ----
        Surface(
            shape = RoundedCornerShape(12.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 1.dp
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "AI 配置（可选）",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface
                )

                Text(
                    text = "配置 OpenAI 兼容 API 后可解锁 AI 问答、解析和出题功能。不配置时本地功能照常可用。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                OutlinedTextField(
                    value = settingsState.baseUrl,
                    onValueChange = { settingsViewModel.updateBaseUrl(it) },
                    label = { Text("Base URL") },
                    placeholder = { Text("https://api.openai.com/v1") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                OutlinedTextField(
                    value = settingsState.apiKey,
                    onValueChange = { settingsViewModel.updateApiKey(it) },
                    label = { Text("API Key") },
                    placeholder = { Text("sk-...") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                    visualTransformation = if (showApiKey) VisualTransformation.None else PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    trailingIcon = {
                        IconButton(onClick = { showApiKey = !showApiKey }) {
                            Icon(
                                imageVector = Icons.Default.Lock,
                                contentDescription = if (showApiKey) "隐藏 API Key" else "显示 API Key",
                                tint = if (showApiKey) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }
                )

                OutlinedTextField(
                    value = settingsState.model,
                    onValueChange = { settingsViewModel.updateModel(it) },
                    label = { Text("模型") },
                    placeholder = { Text("gpt-4o-mini") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )

                Button(
                    onClick = { settingsViewModel.save() },
                    enabled = !settingsState.isSaving,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    if (settingsState.isSaving) {
                        CircularProgressIndicator(
                            modifier = Modifier.padding(end = 8.dp),
                            strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary
                        )
                    }
                    Text(if (settingsState.isSaving) "保存中…" else "保存")
                }

                if (settingsState.message != null) {
                    Text(
                        text = settingsState.message!!,
                        style = MaterialTheme.typography.bodySmall,
                        color = if (settingsState.message!!.startsWith("保存成功"))
                            MaterialTheme.colorScheme.secondary
                        else
                            MaterialTheme.colorScheme.error
                    )
                }
            }
        }

        // ---- Backup Section ----
        Surface(
            modifier = Modifier.testTag("backup-section"),
            shape = RoundedCornerShape(12.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 1.dp
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "数据备份",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface
                )

                Text(
                    text = "导出/导入学习数据为 JSON 文件。API Key 不会包含在备份中。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )

                Button(
                    onClick = { backupViewModel.export() },
                    enabled = !backupState.isExporting,
                    modifier = Modifier.fillMaxWidth().testTag("backup-export-button")
                ) {
                    if (backupState.isExporting) {
                        CircularProgressIndicator(
                            modifier = Modifier.padding(end = 8.dp),
                            strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary
                        )
                    }
                    Text(if (backupState.isExporting) "导出中…" else "导出备份")
                }

                // Import mode selection
                ImportModeSelector(
                    selectedMode = selectedImportMode,
                    onModeSelected = { selectedImportMode = it }
                )

                OutlinedButton(
                    onClick = { importLauncher.launch(arrayOf("application/json")) },
                    enabled = !backupState.isImporting,
                    modifier = Modifier.fillMaxWidth().testTag("backup-import-button")
                ) {
                    if (backupState.isImporting) {
                        CircularProgressIndicator(
                            modifier = Modifier.padding(end = 8.dp),
                            strokeWidth = 2.dp
                        )
                    }
                    Text(if (backupState.isImporting) "导入中…" else "导入备份")
                }

                // Trigger file save after export completes
                if (backupState.exportReady && backupState.exportedJson != null) {
                    val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
                    LaunchedEffect(backupState.exportedJson) {
                        exportLauncher.launch("mathagent_backup_$timestamp.json")
                    }
                }

                // Status message
                if (backupState.message != null) {
                    Text(
                        text = backupState.message!!,
                        style = MaterialTheme.typography.bodySmall,
                        color = if (backupState.message!!.startsWith("导入成功"))
                            MaterialTheme.colorScheme.secondary
                        else
                            MaterialTheme.colorScheme.error,
                        modifier = Modifier.testTag("backup-status-text")
                    )
                }

                // Latest backup log
                latestLog?.let { log ->
                    val dateStr = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault())
                        .format(Date(log.createdAt))
                    val opLabel = if (log.operation == "export") "导出" else "导入"
                    Text(
                        text = "最近${opLabel}: ${log.fileName} ($dateStr)",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.testTag("backup-status-text")
                    )
                }
            }
        }

        // ---- About Section ----
        Surface(
            shape = RoundedCornerShape(12.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 1.dp
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Text(
                    text = "关于",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = "Math Agent v1.0",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    text = "原生 Android 学习助手 · 离线优先",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    text = "数据存储在本地 SQLite 数据库中",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }

        Spacer(modifier = Modifier.height(32.dp))
    }

    // REPLACE_ALL confirmation dialog
    if (pendingReplaceJson != null) {
        AlertDialog(
            modifier = Modifier.testTag("import-confirm-dialog"),
            onDismissRequest = { pendingReplaceJson = null },
            title = { Text("确认替换全部数据") },
            text = {
                Text("此操作将删除本机所有学习数据（错题、复习记录、学习计划、资料等），然后从备份文件导入。此操作不可撤销。\n\n确定要继续吗？")
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        // Use pure logic from BackupImportComponents
                        val action = confirmReplaceImport(pendingReplaceJson!!)
                        pendingReplaceJson = null
                        backupViewModel.import(action.json, action.mode)
                    },
                    modifier = Modifier.testTag("import-confirm-ok")
                ) { Text("确认替换", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(
                    onClick = { pendingReplaceJson = null },
                    modifier = Modifier.testTag("import-confirm-cancel")
                ) { Text("取消") }
            }
        )
    }
}
