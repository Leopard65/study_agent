package com.example.mathagent.ui.screens.materials

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Info
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.mathagent.LocalViewModelFactory
import com.example.mathagent.data.local.entity.Material
import com.example.mathagent.ui.viewmodel.MaterialListViewModel

@Composable
fun MaterialListScreen(
    modifier: Modifier = Modifier,
    onMaterialClick: (Long) -> Unit,
    viewModel: MaterialListViewModel = viewModel(factory = LocalViewModelFactory.current)
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var showAddDialog by remember { mutableStateOf(false) }
    var editingMaterial by remember { mutableStateOf<Material?>(null) }
    var showFabMenu by remember { mutableStateOf(false) }

    // File picker for import
    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        if (uri != null) {
            viewModel.importFile(uri)
        }
    }

    Scaffold(
        modifier = modifier.testTag("screen-materials"),
        floatingActionButton = {
            Box {
                FloatingActionButton(onClick = { showFabMenu = true }) {
                    Icon(Icons.Default.Add, contentDescription = "新增资料")
                }
                DropdownMenu(
                    expanded = showFabMenu,
                    onDismissRequest = { showFabMenu = false }
                ) {
                    DropdownMenuItem(
                        text = { Text("手动添加") },
                        onClick = {
                            showFabMenu = false
                            showAddDialog = true
                        }
                    )
                    DropdownMenuItem(
                        text = { Text("导入文件") },
                        modifier = Modifier.testTag("import-file-menu"),
                        onClick = {
                            showFabMenu = false
                            // Use */* to allow all file types; MaterialImportService
                            // performs the actual type validation and rejects unsupported formats.
                            importLauncher.launch(arrayOf("*/*"))
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        if (state.isImporting) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator()
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = "正在导入…",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        } else if (state.materials.isEmpty() && !state.isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "暂无学习资料\n点击右下角 + 添加或导入",
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                item { Spacer(modifier = Modifier.height(8.dp)) }
                items(state.materials, key = { it.id }) { material ->
                    MaterialItem(
                        material = material,
                        onClick = { onMaterialClick(material.id) },
                        onEdit = { editingMaterial = material },
                        onDelete = { viewModel.deleteMaterial(material) }
                    )
                }
                item { Spacer(modifier = Modifier.height(80.dp)) }
            }
        }
    }

    if (showAddDialog) {
        MaterialDialog(
            title = "新增学习资料",
            onDismiss = { showAddDialog = false },
            onConfirm = { t, s, d ->
                viewModel.addMaterial(t, s, d)
                showAddDialog = false
            }
        )
    }

    editingMaterial?.let { mat ->
        MaterialDialog(
            title = "编辑学习资料",
            initialTitle = mat.title,
            initialSubject = mat.subject,
            initialDescription = mat.description,
            onDismiss = { editingMaterial = null },
            onConfirm = { t, s, d ->
                viewModel.updateMaterial(mat.copy(title = t, subject = s, description = d))
                editingMaterial = null
            }
        )
    }

    // Show import/status message as snackbar-like text
    if (state.message != null) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            contentAlignment = Alignment.BottomCenter
        ) {
            Surface(
                shape = RoundedCornerShape(8.dp),
                color = if (state.message!!.startsWith("导入成功") || state.message!!.startsWith("添加成功"))
                    MaterialTheme.colorScheme.secondaryContainer
                else
                    MaterialTheme.colorScheme.errorContainer,
                tonalElevation = 2.dp
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 10.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = state.message!!,
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (state.message!!.startsWith("导入成功") || state.message!!.startsWith("添加成功"))
                            MaterialTheme.colorScheme.onSecondaryContainer
                        else
                            MaterialTheme.colorScheme.onErrorContainer,
                        modifier = Modifier.weight(1f)
                    )
                    TextButton(onClick = { viewModel.clearMessage() }) {
                        Text("关闭")
                    }
                }
            }
        }
    }
}

@Composable
private fun MaterialItem(
    material: Material,
    onClick: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    Surface(
        modifier = Modifier.clickable(onClick = onClick).testTag("material-item-${material.id}"),
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 1.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Icon(
                Icons.Default.Info,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(end = 12.dp)
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = material.title,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurface
                )
                if (material.subject.isNotBlank()) {
                    Text(
                        text = material.subject,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                if (material.description.isNotBlank()) {
                    Text(
                        text = material.description,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                if (material.filePath.isNotBlank()) {
                    Text(
                        text = "已导入",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                }
            }
            IconButton(onClick = onEdit) {
                Icon(
                    Icons.Default.Edit,
                    contentDescription = "编辑",
                    tint = MaterialTheme.colorScheme.primary
                )
            }
            IconButton(onClick = onDelete) {
                Icon(
                    Icons.Default.Delete,
                    contentDescription = "删除",
                    tint = MaterialTheme.colorScheme.error
                )
            }
        }
    }
}

@Composable
private fun MaterialDialog(
    title: String,
    initialTitle: String = "",
    initialSubject: String = "",
    initialDescription: String = "",
    onDismiss: () -> Unit,
    onConfirm: (title: String, subject: String, description: String) -> Unit
) {
    var editTitle by remember { mutableStateOf(initialTitle) }
    var editSubject by remember { mutableStateOf(initialSubject) }
    var editDescription by remember { mutableStateOf(initialDescription) }

    AlertDialog(
        modifier = Modifier.testTag("edit-material-dialog"),
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = editTitle,
                    onValueChange = { editTitle = it },
                    label = { Text("资料标题 *") },
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = editSubject,
                    onValueChange = { editSubject = it },
                    label = { Text("科目") },
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = editDescription,
                    onValueChange = { editDescription = it },
                    label = { Text("描述") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 2
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = { onConfirm(editTitle, editSubject, editDescription) },
                enabled = editTitle.isNotBlank()
            ) { Text("保存") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        }
    )
}
