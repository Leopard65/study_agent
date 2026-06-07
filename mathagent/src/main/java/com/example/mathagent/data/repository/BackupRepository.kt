package com.example.mathagent.data.repository

import com.example.mathagent.data.local.dao.BackupLogDao
import com.example.mathagent.data.local.entity.BackupLog
import kotlinx.coroutines.flow.Flow

class BackupRepository(
    private val backupLogDao: BackupLogDao
) {
    fun getAll(): Flow<List<BackupLog>> = backupLogDao.getAll()

    suspend fun getLatest(): BackupLog? = backupLogDao.getLatest()

    suspend fun insert(log: BackupLog): Long = backupLogDao.insert(log)

    suspend fun delete(log: BackupLog) = backupLogDao.delete(log)

    fun count(): Flow<Int> = backupLogDao.count()
}
