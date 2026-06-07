package com.example.mathagent.ui.screens.plans

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
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.AlertDialog
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
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.mathagent.LocalViewModelFactory
import com.example.mathagent.data.local.entity.StudyPlan
import com.example.mathagent.ui.viewmodel.PlanListViewModel

@Composable
fun PlanListScreen(
    modifier: Modifier = Modifier,
    viewModel: PlanListViewModel = viewModel(factory = LocalViewModelFactory.current)
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var showAddDialog by remember { mutableStateOf(false) }
    var editingPlan by remember { mutableStateOf<StudyPlan?>(null) }

    Scaffold(
        modifier = modifier.testTag("screen-plans"),
        floatingActionButton = {
            FloatingActionButton(onClick = { showAddDialog = true }) {
                Icon(Icons.Default.Add, contentDescription = "新增计划")
            }
        }
    ) { innerPadding ->
        if (state.plans.isEmpty() && !state.isLoading) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "暂无学习计划\n点击右下角 + 添加",
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
                items(state.plans, key = { it.id }) { plan ->
                    PlanItem(
                        plan = plan,
                        onToggleCompleted = { viewModel.toggleCompleted(plan.id) },
                        onEdit = { editingPlan = plan },
                        onDelete = { viewModel.deletePlan(plan) }
                    )
                }
                item { Spacer(modifier = Modifier.height(80.dp)) }
            }
        }
    }

    if (showAddDialog) {
        PlanDialog(
            title = "新增学习计划",
            onDismiss = { showAddDialog = false },
            onConfirm = { t, s, d ->
                viewModel.addPlan(t, s, d)
                showAddDialog = false
            }
        )
    }

    editingPlan?.let { plan ->
        PlanDialog(
            title = "编辑学习计划",
            initialTitle = plan.title,
            initialSubject = plan.subject,
            initialDescription = plan.description,
            onDismiss = { editingPlan = null },
            onConfirm = { t, s, d ->
                viewModel.updatePlan(plan.copy(title = t, subject = s, description = d))
                editingPlan = null
            }
        )
    }
}

@Composable
private fun PlanItem(
    plan: StudyPlan,
    onToggleCompleted: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    Surface(
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
            IconButton(onClick = onToggleCompleted) {
                Icon(
                    imageVector = if (plan.completed) Icons.Default.CheckCircle else Icons.Default.Close,
                    contentDescription = if (plan.completed) "已完成" else "未完成",
                    tint = if (plan.completed) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = plan.title,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    color = MaterialTheme.colorScheme.onSurface,
                    textDecoration = if (plan.completed) TextDecoration.LineThrough else null
                )
                if (plan.subject.isNotBlank()) {
                    Text(
                        text = plan.subject,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                if (plan.description.isNotBlank()) {
                    Text(
                        text = plan.description,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
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
private fun PlanDialog(
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
        modifier = Modifier.testTag("edit-plan-dialog"),
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = editTitle,
                    onValueChange = { editTitle = it },
                    label = { Text("计划标题 *") },
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
