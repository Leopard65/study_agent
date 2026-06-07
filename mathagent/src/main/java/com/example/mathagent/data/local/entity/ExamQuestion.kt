package com.example.mathagent.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "exam_questions")
data class ExamQuestion(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val subject: String = "",
    val chapter: String = "",
    val questionType: String = "single_choice",
    val question: String,
    val options: String = "",
    val answer: String = "",
    val analysis: String = "",
    val difficulty: Int = 3,
    val points: Int = 1,
    val createdAt: Long = System.currentTimeMillis()
)
