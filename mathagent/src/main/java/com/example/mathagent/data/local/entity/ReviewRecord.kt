package com.example.mathagent.data.local.entity

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "review_records",
    foreignKeys = [ForeignKey(
        entity = ErrorEntry::class,
        parentColumns = ["id"],
        childColumns = ["errorEntryId"],
        onDelete = ForeignKey.CASCADE
    )],
    indices = [Index("errorEntryId")]
)
data class ReviewRecord(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val errorEntryId: Long = 0,
    val nextReviewAt: Long = System.currentTimeMillis(),
    val intervalDays: Int = 1,
    val easeFactor: Float = 2.5f,
    val repetitionCount: Int = 0,
    val lastReviewedAt: Long = 0,
    val createdAt: Long = System.currentTimeMillis()
)
