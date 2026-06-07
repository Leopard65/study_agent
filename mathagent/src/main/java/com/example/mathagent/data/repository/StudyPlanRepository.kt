package com.example.mathagent.data.repository

import com.example.mathagent.data.local.dao.StudyPlanDao
import com.example.mathagent.data.local.entity.StudyPlan
import kotlinx.coroutines.flow.Flow

class StudyPlanRepository(
    private val studyPlanDao: StudyPlanDao
) {
    fun getAll(): Flow<List<StudyPlan>> = studyPlanDao.getAll()

    fun getActive(): Flow<List<StudyPlan>> = studyPlanDao.getActive()

    fun getCompleted(): Flow<List<StudyPlan>> = studyPlanDao.getCompleted()

    suspend fun getById(id: Long): StudyPlan? = studyPlanDao.getById(id)

    suspend fun insert(plan: StudyPlan): Long = studyPlanDao.insert(plan)

    suspend fun update(plan: StudyPlan) = studyPlanDao.update(plan)

    suspend fun delete(plan: StudyPlan) = studyPlanDao.delete(plan)

    suspend fun deleteById(id: Long) = studyPlanDao.deleteById(id)

    suspend fun toggleCompleted(id: Long) {
        val current = studyPlanDao.getById(id) ?: return
        studyPlanDao.updateCompleted(id, !current.completed)
    }

    fun count(): Flow<Int> = studyPlanDao.count()

    fun countActive(): Flow<Int> = studyPlanDao.countActive()
}
