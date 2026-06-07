package com.example.mathagent.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.example.mathagent.data.local.entity.ReviewRecord
import kotlinx.coroutines.flow.Flow

@Dao
interface ReviewRecordDao {

    @Query("SELECT * FROM review_records ORDER BY nextReviewAt ASC")
    fun getAll(): Flow<List<ReviewRecord>>

    @Query("SELECT * FROM review_records WHERE nextReviewAt <= :now ORDER BY nextReviewAt ASC")
    fun getDueForReview(now: Long = System.currentTimeMillis()): Flow<List<ReviewRecord>>

    @Query("SELECT * FROM review_records WHERE id = :id")
    suspend fun getById(id: Long): ReviewRecord?

    @Query("SELECT * FROM review_records WHERE errorEntryId = :errorEntryId")
    suspend fun getByErrorEntryId(errorEntryId: Long): ReviewRecord?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(record: ReviewRecord): Long

    @Update
    suspend fun update(record: ReviewRecord)

    @Delete
    suspend fun delete(record: ReviewRecord)

    @Query("DELETE FROM review_records WHERE errorEntryId = :errorEntryId")
    suspend fun deleteByErrorEntryId(errorEntryId: Long)

    @Query("SELECT COUNT(*) FROM review_records WHERE nextReviewAt <= :now")
    fun countDueForReview(now: Long = System.currentTimeMillis()): Flow<Int>

    @Query("SELECT * FROM review_records")
    suspend fun getAllSync(): List<ReviewRecord>

    @Query("DELETE FROM review_records")
    suspend fun deleteAllSync()
}
