package com.example.mathagent.data.local.entity

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(
    tableName = "material_chunks",
    foreignKeys = [ForeignKey(
        entity = Material::class,
        parentColumns = ["id"],
        childColumns = ["materialId"],
        onDelete = ForeignKey.CASCADE
    )],
    indices = [Index("materialId")]
)
data class MaterialChunk(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val materialId: Long,
    val chunkIndex: Int,
    val content: String,
    val embedding: String = ""
)
