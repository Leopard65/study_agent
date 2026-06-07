package com.example.mathagent.data.repository

import com.example.mathagent.data.local.dao.ChatMessageDao
import com.example.mathagent.data.local.entity.ChatMessage
import kotlinx.coroutines.flow.Flow

class ChatRepository(
    private val chatMessageDao: ChatMessageDao
) {
    fun getAll(): Flow<List<ChatMessage>> = chatMessageDao.getAll()

    fun getAllAsc(): Flow<List<ChatMessage>> = chatMessageDao.getAllAsc()

    fun getRecent(limit: Int = 20): Flow<List<ChatMessage>> = chatMessageDao.getRecent(limit)

    fun getBySubject(subject: String): Flow<List<ChatMessage>> =
        chatMessageDao.getBySubject(subject)

    suspend fun insert(message: ChatMessage): Long = chatMessageDao.insert(message)

    suspend fun deleteAll() = chatMessageDao.deleteAll()

    fun count(): Flow<Int> = chatMessageDao.count()
}
