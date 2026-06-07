package com.example.mathagent.domain.model

/**
 * Domain model type aliases.
 *
 * In Phase 1 the domain models are identical to the Room entities.
 * As the app evolves, these can become independent data classes with
 * mapping functions to/from the persistence layer.
 */

typealias Material = com.example.mathagent.data.local.entity.Material
typealias MaterialChunk = com.example.mathagent.data.local.entity.MaterialChunk
typealias ErrorEntry = com.example.mathagent.data.local.entity.ErrorEntry
typealias StudyPlan = com.example.mathagent.data.local.entity.StudyPlan
typealias ReviewRecord = com.example.mathagent.data.local.entity.ReviewRecord
typealias ChatMessage = com.example.mathagent.data.local.entity.ChatMessage
typealias ProblemRecord = com.example.mathagent.data.local.entity.ProblemRecord
typealias ExamQuestion = com.example.mathagent.data.local.entity.ExamQuestion
typealias ExamAttempt = com.example.mathagent.data.local.entity.ExamAttempt
typealias AppSetting = com.example.mathagent.data.local.entity.AppSetting
typealias BackupLog = com.example.mathagent.data.local.entity.BackupLog
