package com.example.mathagent.data.ai

import com.example.mathagent.data.local.dao.MaterialChunkDao
import com.example.mathagent.data.local.dao.MaterialDao
import com.example.mathagent.data.local.entity.ErrorEntry

/**
 * Builds supplementary context from local material chunks for AI prompts.
 *
 * Responsibilities:
 * - Extract keywords from an [ErrorEntry]
 * - Search local chunks for relevant content
 * - Deduplicate and truncate results
 * - Format as a prompt appendix
 *
 * Returns empty string when no relevant chunks are found (silent fallback).
 */
open class MaterialChunkContextBuilder(
    private val materialChunkDao: MaterialChunkDao,
    private val materialDao: MaterialDao,
    private val maxChunks: Int = 3,
    private val snippetLen: Int = 150
) {
    /**
     * Build a context string to append to the system prompt.
     * Returns empty string if no relevant chunks are found.
     */
    open suspend fun buildContext(entry: ErrorEntry): String {
        val keywords = extractKeywords(entry)
        if (keywords.isEmpty()) return ""

        val relevantChunks = searchAndDeduplicate(keywords)
        if (relevantChunks.isEmpty()) return ""

        return "\n\n参考资料（供参考，不一定与本题直接相关）：\n" +
            relevantChunks.joinToString("\n") { "- $it" }
    }

    /** Extract search keywords from the error entry. */
    internal fun extractKeywords(entry: ErrorEntry): List<String> = buildList {
        if (entry.subject.isNotBlank()) add(entry.subject)
        if (entry.chapter.isNotBlank()) add(entry.chapter)
        entry.question.split(Regex("[\\s，。、；：？！,.;:?!]+"))
            .filter { it.length >= 2 }
            .take(3)
            .forEach { add(it) }
    }

    /** Search chunks for keywords, deduplicate by chunk id, format as summaries. */
    internal suspend fun searchAndDeduplicate(keywords: List<String>): List<String> {
        val seen = mutableSetOf<Long>()
        val results = mutableListOf<String>()

        for (keyword in keywords) {
            val chunks = materialChunkDao.search(keyword, limit = 5)
            for (chunk in chunks) {
                if (chunk.id in seen) continue
                if (results.size >= maxChunks) break
                seen.add(chunk.id)
                val mat = materialDao.getById(chunk.materialId) ?: continue
                val snippet = chunk.content.take(snippetLen)
                results.add("【${mat.title}·片段${chunk.chunkIndex + 1}】$snippet")
            }
            if (results.size >= maxChunks) break
        }
        return results
    }
}
