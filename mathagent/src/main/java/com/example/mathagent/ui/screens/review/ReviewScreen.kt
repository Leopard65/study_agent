package com.example.mathagent.ui.screens.review

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.mathagent.LocalViewModelFactory
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.local.entity.ReviewRecord
import com.example.mathagent.domain.model.ReviewQuality
import com.example.mathagent.ui.viewmodel.ReviewViewModel

@Composable
fun ReviewScreen(
    modifier: Modifier = Modifier,
    viewModel: ReviewViewModel = viewModel(factory = LocalViewModelFactory.current)
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val lifecycleOwner = LocalLifecycleOwner.current

    // Refresh time-sensitive data on every resume
    DisposableEffect(Unit) {
        val observer = androidx.lifecycle.LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                viewModel.refresh()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .testTag("screen-review")
            .background(MaterialTheme.colorScheme.background)
            .padding(20.dp)
    ) {
        Text(
            text = "今日复习",
            style = MaterialTheme.typography.headlineMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onBackground
        )

        Spacer(modifier = Modifier.height(8.dp))

        Text(
            text = "待复习 ${state.dueReviews.size} 项",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        Spacer(modifier = Modifier.height(16.dp))

        if (state.dueReviews.isEmpty() && !state.isLoading) {
            Box(
                modifier = Modifier.fillMaxSize(),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.Check,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.secondary,
                        modifier = Modifier.padding(bottom = 8.dp)
                    )
                    Text(
                        text = "今日复习已完成！",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = "添加错题后会自动安排复习",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        } else {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(state.dueReviews, key = { it.id }) { record ->
                    ReviewItem(
                        record = record,
                        errorEntry = state.errorEntries[record.errorEntryId],
                        onQuality = { quality ->
                            viewModel.markReviewed(record, quality)
                        },
                        onSkip = { viewModel.skip(record) }
                    )
                }
            }
        }
    }
}

@Composable
private fun ReviewItem(
    record: ReviewRecord,
    errorEntry: ErrorEntry?,
    onQuality: (ReviewQuality) -> Unit,
    onSkip: () -> Unit
) {
    Surface(
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surface,
        tonalElevation = 1.dp
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            if (errorEntry != null) {
                Text(
                    text = errorEntry.question,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.onSurface
                )
                if (errorEntry.subject.isNotBlank()) {
                    Text(
                        text = errorEntry.subject,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            } else {
                Text(
                    text = "复习记录 #${record.id}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "复习次数: ${record.repetitionCount} · 间隔: ${record.intervalDays}天",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            Spacer(modifier = Modifier.height(12.dp))

            // Quality buttons — student-facing labels
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                // 忘记 — red, full reset
                Button(
                    onClick = { onQuality(ReviewQuality.Again) },
                    modifier = Modifier
                        .weight(1f)
                        .testTag("review-again-${record.id}"),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                        contentColor = MaterialTheme.colorScheme.onError
                    )
                ) {
                    Text("忘记", style = MaterialTheme.typography.labelMedium)
                }

                // 困难 — outlined, conservative
                OutlinedButton(
                    onClick = { onQuality(ReviewQuality.Hard) },
                    modifier = Modifier
                        .weight(1f)
                        .testTag("review-hard-${record.id}")
                ) {
                    Text("困难", style = MaterialTheme.typography.labelMedium)
                }

                // 记得 — primary, standard
                Button(
                    onClick = { onQuality(ReviewQuality.Good) },
                    modifier = Modifier
                        .weight(1f)
                        .testTag("review-good-${record.id}")
                ) {
                    Text("记得", style = MaterialTheme.typography.labelMedium)
                }

                // 简单 — secondary, bonus
                OutlinedButton(
                    onClick = { onQuality(ReviewQuality.Easy) },
                    modifier = Modifier
                        .weight(1f)
                        .testTag("review-easy-${record.id}")
                ) {
                    Text("简单", style = MaterialTheme.typography.labelMedium)
                }
            }

            Spacer(modifier = Modifier.height(6.dp))

            // Skip — postpone 1 day, no algorithm
            OutlinedButton(
                onClick = onSkip,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag("review-skip-${record.id}")
            ) {
                Text("跳过（明天再复习）", style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}
