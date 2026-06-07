package com.example.mathagent.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "problem_records")
data class ProblemRecord(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val subject: String = "",
    val chapter: String = "",
    val question: String,
    val userAnswer: String = "",
    val correctAnswer: String = "",
    val isCorrect: Boolean = false,
    val score: Int = 0,
    val timeSpentSeconds: Int = 0,
    val createdAt: Long = System.currentTimeMillis()
)
