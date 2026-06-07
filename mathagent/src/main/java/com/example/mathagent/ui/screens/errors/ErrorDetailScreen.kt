package com.example.mathagent.ui.screens.errors

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.mathagent.LocalViewModelFactory
import com.example.mathagent.ui.viewmodel.ErrorDetailViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ErrorDetailScreen(
    errorId: Long,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: ErrorDetailViewModel = viewModel(factory = LocalViewModelFactory.current)
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(errorId) {
        viewModel.loadError(errorId)
    }

    Scaffold(
        modifier = modifier.testTag("screen-error-detail"),
        topBar = {
            TopAppBar(
                title = { Text("错题详情") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.surface
                )
            )
        }
    ) { innerPadding ->
        if (state.isLoading) {
            Box(modifier = Modifier.fillMaxSize().padding(innerPadding), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else if (state.errorEntry == null) {
            Box(modifier = Modifier.fillMaxSize().padding(innerPadding), contentAlignment = Alignment.Center) {
                Text("错题不存在", color = MaterialTheme.colorScheme.error)
            }
        } else {
            val entry = state.errorEntry!!
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Question
                InfoCard(label = "题目", value = entry.question)

                if (entry.subject.isNotBlank()) {
                    InfoCard(label = "科目", value = entry.subject)
                }
                if (entry.wrongAnswer.isNotBlank()) {
                    InfoCard(label = "我的答案", value = entry.wrongAnswer, isError = true)
                }
                if (entry.correctAnswer.isNotBlank()) {
                    InfoCard(label = "正确答案", value = entry.correctAnswer, isSuccess = true)
                }

                // Status
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = if (entry.mastered) Icons.Default.CheckCircle else Icons.Default.Close,
                        contentDescription = null,
                        tint = if (entry.mastered) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(end = 8.dp)
                    )
                    Text(
                        text = if (entry.mastered) "已掌握" else "未掌握",
                        style = MaterialTheme.typography.bodyMedium,
                        color = if (entry.mastered) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.error
                    )
                }

                // AI Analysis Section
                Surface(
                    modifier = Modifier.testTag("ai-analysis-section"),
                    shape = RoundedCornerShape(12.dp),
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    tonalElevation = 1.dp
                ) {
                    Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text(
                            text = "AI 解析",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )

                        if (state.aiAnalysis != null) {
                            Text(
                                text = state.aiAnalysis!!,
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                        } else if (state.isAiAnalyzing) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(12.dp)
                            ) {
                                CircularProgressIndicator(
                                    modifier = Modifier.testTag("ai-loading"),
                                    strokeWidth = 2.dp
                                )
                                Text(
                                    text = "AI 正在分析中…",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        } else {
                            Button(
                                onClick = { viewModel.requestAiAnalysis() },
                                enabled = state.isAiConfigured,
                                modifier = Modifier.fillMaxWidth().testTag("ai-analyze-button")
                            ) {
                                Text(if (state.isAiConfigured) "AI 解析此题" else "请先在设置中配置 API Key")
                            }
                            if (!state.isAiConfigured) {
                                Text(
                                    text = "配置 API Key 后可使用 AI 解析功能",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }

                        if (state.message != null) {
                            Text(
                                text = state.message!!,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.error,
                                modifier = Modifier.testTag("ai-error-message")
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun InfoCard(
    label: String,
    value: String,
    isError: Boolean = false,
    isSuccess: Boolean = false
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 1.dp
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
            Text(
                text = label,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.bodyMedium,
                color = when {
                    isError -> MaterialTheme.colorScheme.error
                    isSuccess -> MaterialTheme.colorScheme.secondary
                    else -> MaterialTheme.colorScheme.onSurface
                }
            )
        }
    }
}
