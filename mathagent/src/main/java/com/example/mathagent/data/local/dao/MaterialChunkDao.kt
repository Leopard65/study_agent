package com.example.mathagent.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.example.mathagent.data.local.entity.MaterialChunk
import kotlinx.coroutines.flow.Flow

@Dao
interface MaterialChunkDao {

    @Query("SELECT * FROM material_chunks WHERE materialId = :materialId ORDER BY chunkIndex ASC")
    fun getByMaterialId(materialId: Long): Flow<List<MaterialChunk>>

    @Query("SELECT * FROM material_chunks WHERE materialId = :materialId ORDER BY chunkIndex ASC")
    suspend fun getChunksByMaterialId(materialId: Long): List<MaterialChunk>

    @Query("SELECT * FROM material_chunks WHERE id = :id")
    suspend fun getById(id: Long): MaterialChunk?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(chunk: MaterialChunk): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(chunks: List<MaterialChunk>)

    @Delete
    suspend fun delete(chunk: MaterialChunk)

    @Query("DELETE FROM material_chunks WHERE materialId = :materialId")
    suspend fun deleteByMaterialId(materialId: Long)

    @Query("SELECT COUNT(*) FROM material_chunks WHERE materialId = :materialId")
    fun countByMaterialId(materialId: Long): Flow<Int>

    @Query("SELECT * FROM material_chunks")
    suspend fun getAllSync(): List<MaterialChunk>

    @Query("DELETE FROM material_chunks")
    suspend fun deleteAllSync()

    @Query("SELECT * FROM material_chunks WHERE content LIKE '%' || :query || '%' ORDER BY chunkIndex ASC LIMIT :limit")
    suspend fun search(query: String, limit: Int = 20): List<MaterialChunk>
}
