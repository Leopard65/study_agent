package com.example.mathagent.ui.screens.materials

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
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
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
import com.example.mathagent.data.local.entity.MaterialChunk
import com.example.mathagent.ui.viewmodel.MaterialDetailViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MaterialDetailScreen(
    materialId: Long,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    highlightChunkIndex: Int? = null,
    viewModel: MaterialDetailViewModel = viewModel(factory = LocalViewModelFactory.current)
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    LaunchedEffect(materialId, highlightChunkIndex) {
        viewModel.loadMaterial(materialId, highlightChunkIndex)
    }

    Scaffold(
        modifier = modifier.testTag("screen-material-detail"),
        topBar = {
            TopAppBar(
                title = { Text("资料详情") },
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
        } else if (state.material == null) {
            Box(modifier = Modifier.fillMaxSize().padding(innerPadding), contentAlignment = Alignment.Center) {
                Text(state.message ?: "资料不存在", color = MaterialTheme.colorScheme.error)
            }
        } else {
            val material = state.material!!
            val listState = rememberLazyListState()

            // Auto-scroll to highlighted chunk
            LaunchedEffect(state.highlightChunkIndex, state.chunks) {
                val targetIdx = state.highlightChunkIndex ?: return@LaunchedEffect
                val chunkPos = state.chunks.indexOfFirst { it.chunkIndex == targetIdx }
                if (chunkPos >= 0) {
                    // +1 for the header item
                    listState.animateScrollToItem(chunkPos + 1)
                }
            }

            LazyColumn(
                state = listState,
                modifier = Modifier
                    .fillMaxSize()
                    .padding(innerPadding)
                    .padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                // Header: material info
                item(key = "header") {
                    Column(
                        modifier = Modifier.padding(top = 16.dp, bottom = 8.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text(
                            text = material.title,
                            style = MaterialTheme.typography.headlineSmall,
                            fontWeight = FontWeight.Bold
                        )
                        if (material.subject.isNotBlank()) {
                            InfoRow(label = "科目", value = material.subject)
                        }
                        if (material.description.isNotBlank()) {
                            InfoRow(label = "描述", value = material.description)
                        }
                        InfoRow(label = "类型", value = material.fileType.ifBlank { "未知" })
                        if (material.fileSize > 0) {
                            InfoRow(label = "大小", value = formatFileSize(material.fileSize))
                        }
                        if (material.filePath.isBlank()) {
                            Surface(
                                shape = RoundedCornerShape(8.dp),
                                color = MaterialTheme.colorScheme.surfaceVariant
                            ) {
                                Text(
                                    text = "备份恢复资料（无本地文件）",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    modifier = Modifier.padding(8.dp)
                                )
                            }
                        }
                    }
                }

                // Chunks
                if (state.chunks.isNotEmpty()) {
                    item(key = "chunks-header") {
                        Text(
                            text = "内容片段 (${state.chunks.size})",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                    items(state.chunks, key = { it.id }) { chunk ->
                        ChunkCard(
                            chunk = chunk,
                            isHighlighted = chunk.chunkIndex == state.highlightChunkIndex
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth()) {
        Text(
            text = "$label：",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontWeight = FontWeight.Medium
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface
        )
    }
}

@Composable
private fun ChunkCard(chunk: MaterialChunk, isHighlighted: Boolean) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("chunk-${chunk.chunkIndex}"),
        shape = RoundedCornerShape(8.dp),
        color = if (isHighlighted)
            MaterialTheme.colorScheme.primaryContainer
        else
            MaterialTheme.colorScheme.surfaceVariant,
        tonalElevation = if (isHighlighted) 4.dp else 0.dp
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Text(
                text = "片段 ${chunk.chunkIndex + 1}",
                style = MaterialTheme.typography.labelSmall,
                color = if (isHighlighted)
                    MaterialTheme.colorScheme.onPrimaryContainer
                else
                    MaterialTheme.colorScheme.onSurfaceVariant,
                fontWeight = FontWeight.SemiBold
            )
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = chunk.content,
                style = MaterialTheme.typography.bodySmall,
                color = if (isHighlighted)
                    MaterialTheme.colorScheme.onPrimaryContainer
                else
                    MaterialTheme.colorScheme.onSurface
            )
        }
    }
}

private fun formatFileSize(bytes: Long): String = when {
    bytes < 1024 -> "$bytes B"
    bytes < 1024 * 1024 -> "${bytes / 1024} KB"
    else -> "${"%.1f".format(bytes / (1024.0 * 1024.0))} MB"
}
