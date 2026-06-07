package com.example.mathagent.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.example.mathagent.data.local.entity.Material
import kotlinx.coroutines.flow.Flow

@Dao
interface MaterialDao {

    @Query("SELECT * FROM materials ORDER BY updatedAt DESC")
    fun getAll(): Flow<List<Material>>

    @Query("SELECT * FROM materials WHERE id = :id")
    suspend fun getById(id: Long): Material?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(material: Material): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(materials: List<Material>)

    @Delete
    suspend fun delete(material: Material)

    @Query("DELETE FROM materials WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("SELECT COUNT(*) FROM materials")
    fun count(): Flow<Int>

    @Update
    suspend fun update(material: Material)

    @Query("SELECT * FROM materials WHERE title LIKE '%' || :query || '%' OR subject LIKE '%' || :query || '%' OR description LIKE '%' || :query || '%' ORDER BY updatedAt DESC")
    suspend fun search(query: String): List<Material>

    @Query("SELECT * FROM materials")
    suspend fun getAllSync(): List<Material>

    @Query("DELETE FROM materials")
    suspend fun deleteAllSync()
}
