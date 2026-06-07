package com.example.mathagent.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "backup_logs")
data class BackupLog(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val fileName: String,
    val fileSize: Long = 0,
    val backupType: String = "manual",
    val operation: String = "export",
    val status: String = "success",
    val message: String = "",
    val createdAt: Long = System.currentTimeMillis()
)
