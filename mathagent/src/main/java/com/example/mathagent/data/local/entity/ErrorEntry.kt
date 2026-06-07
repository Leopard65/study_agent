package com.example.mathagent.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "error_entries")
data class ErrorEntry(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val subject: String = "",
    val chapter: String = "",
    val question: String,
    val wrongAnswer: String = "",
    val correctAnswer: String = "",
    val analysis: String = "",
    val difficulty: Int = 3,
    val mastered: Boolean = false,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
)
