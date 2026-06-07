package com.example.mathagent.data.local.dao

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.example.mathagent.data.local.entity.ChatMessage
import kotlinx.coroutines.flow.Flow

@Dao
interface ChatMessageDao {

    @Query("SELECT * FROM chat_messages WHERE id = :id")
    suspend fun getById(id: Long): ChatMessage?

    @Query("SELECT * FROM chat_messages ORDER BY createdAt DESC")
    fun getAll(): Flow<List<ChatMessage>>

    @Query("SELECT * FROM chat_messages ORDER BY createdAt ASC")
    fun getAllAsc(): Flow<List<ChatMessage>>

    @Query("SELECT * FROM chat_messages WHERE subject = :subject ORDER BY createdAt DESC")
    fun getBySubject(subject: String): Flow<List<ChatMessage>>

    @Query("SELECT * FROM chat_messages ORDER BY createdAt DESC LIMIT :limit")
    fun getRecent(limit: Int): Flow<List<ChatMessage>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(message: ChatMessage): Long

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertAll(messages: List<ChatMessage>)

    @Delete
    suspend fun delete(message: ChatMessage)

    @Query("DELETE FROM chat_messages")
    suspend fun deleteAll()

    @Query("SELECT COUNT(*) FROM chat_messages")
    fun count(): Flow<Int>

    @Query("SELECT * FROM chat_messages")
    suspend fun getAllSync(): List<ChatMessage>
}
