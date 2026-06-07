package com.example.mathagent.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.example.mathagent.data.local.entity.StudyPlan
import kotlinx.coroutines.flow.Flow

@Dao
interface StudyPlanDao {

    @Query("SELECT * FROM study_plans ORDER BY createdAt DESC")
    fun getAll(): Flow<List<StudyPlan>>

    @Query("SELECT * FROM study_plans WHERE id = :id")
    suspend fun getById(id: Long): StudyPlan?

    @Query("SELECT * FROM study_plans WHERE completed = 0 ORDER BY targetDate ASC")
    fun getActive(): Flow<List<StudyPlan>>

    @Query("SELECT * FROM study_plans WHERE completed = 1 ORDER BY updatedAt DESC")
    fun getCompleted(): Flow<List<StudyPlan>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(plan: StudyPlan): Long

    @Update
    suspend fun update(plan: StudyPlan)

    @Delete
    suspend fun delete(plan: StudyPlan)

    @Query("DELETE FROM study_plans WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("UPDATE study_plans SET completed = :completed, updatedAt = :updatedAt WHERE id = :id")
    suspend fun updateCompleted(id: Long, completed: Boolean, updatedAt: Long = System.currentTimeMillis())

    @Query("SELECT COUNT(*) FROM study_plans")
    fun count(): Flow<Int>

    @Query("SELECT COUNT(*) FROM study_plans WHERE completed = 0")
    fun countActive(): Flow<Int>

    @Query("SELECT * FROM study_plans WHERE title LIKE '%' || :query || '%' OR subject LIKE '%' || :query || '%' OR description LIKE '%' || :query || '%' ORDER BY createdAt DESC")
    suspend fun search(query: String): List<StudyPlan>

    @Query("SELECT * FROM study_plans")
    suspend fun getAllSync(): List<StudyPlan>

    @Query("DELETE FROM study_plans")
    suspend fun deleteAllSync()
}
