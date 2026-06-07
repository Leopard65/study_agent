package com.example.mathagent.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "exam_attempts")
data class ExamAttempt(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val subject: String = "",
    val totalScore: Int = 0,
    val maxScore: Int = 0,
    val durationSeconds: Int = 0,
    val questionIds: String = "",
    val answers: String = "",
    val createdAt: Long = System.currentTimeMillis()
)
