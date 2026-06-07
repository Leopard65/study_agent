package com.example.mathagent.data.repository

import com.example.mathagent.data.local.dao.ErrorEntryDao
import com.example.mathagent.data.local.dao.MaterialChunkDao
import com.example.mathagent.data.local.dao.MaterialDao
import com.example.mathagent.data.local.dao.StudyPlanDao
import com.example.mathagent.data.local.entity.MaterialChunk
import com.example.mathagent.ui.navigation.Screen

/**
 * Result of a local search across errors, plans, materials, and material chunks.
 *
 * @param id primary key of the matched entity
 * @param type "error", "plan", "material", or "chunk"
 * @param title display title
 * @param subtitle display subtitle (may contain matched snippet)
 * @param route navigation route (parameterized for detail screens)
 * @param materialId for chunk results: the parent material's id (null otherwise)
 * @param matchedChunkIndex for chunk results: the chunk index (null otherwise)
 * @param sortKey lower = higher priority (0 = title hit, 1 = desc hit, 2 = chunk hit)
 */
data class SearchResult(
    val id: Long,
    val type: String,
    val title: String,
    val subtitle: String,
    val route: String,
    val materialId: Long? = null,
    val matchedChunkIndex: Int? = null,
    val sortKey: Int = 0
)

class SearchRepository(
    private val errorEntryDao: ErrorEntryDao,
    private val studyPlanDao: StudyPlanDao,
    private val materialDao: MaterialDao,
    private val materialChunkDao: MaterialChunkDao
) {
    /**
     * Search across all local data. Returns combined results sorted by relevance:
     * 1. Title/subject exact hits (errors, plans, materials)
     * 2. Description/analysis hits
     * 3. Chunk content hits (max 3 per material)
     */
    suspend fun search(query: String): List<SearchResult> {
        if (query.isBlank()) return emptyList()
        val q = query.trim()
        val qLower = q.lowercase()

        val errors = errorEntryDao.search(q).map { entry ->
            val titleHit = qLower in entry.question.lowercase() || qLower in entry.subject.lowercase()
            SearchResult(
                id = entry.id,
                type = "error",
                title = entry.question,
                subtitle = buildSubtitle(entry.subject, entry.analysis),
                route = Screen.ErrorDetail.route(entry.id),
                sortKey = if (titleHit) 0 else 1
            )
        }

        val plans = studyPlanDao.search(q).map { plan ->
            val titleHit = qLower in plan.title.lowercase() || qLower in plan.subject.lowercase()
            SearchResult(
                id = plan.id,
                type = "plan",
                title = plan.title,
                subtitle = buildSubtitle(plan.subject, plan.description),
                route = Screen.Plans.route,
                sortKey = if (titleHit) 0 else 1
            )
        }

        val materials = materialDao.search(q).map { mat ->
            val titleHit = qLower in mat.title.lowercase() || qLower in mat.subject.lowercase()
            SearchResult(
                id = mat.id,
                type = "material",
                title = mat.title,
                subtitle = buildSubtitle(mat.subject, mat.description),
                route = Screen.MaterialDetail.route(mat.id),
                sortKey = if (titleHit) 0 else 1
            )
        }

        val chunkResults = buildChunkResults(q)

        return (errors + plans + materials + chunkResults).sortedBy { it.sortKey }
    }

    /** Build chunk search results, sorted by relevance, max [maxPerMaterial] per parent material. */
    internal suspend fun buildChunkResults(query: String, maxPerMaterial: Int = 3): List<SearchResult> {
        val rawChunks = materialChunkDao.search(query, limit = 30)
        // Score and sort before grouping — best chunks per material survive the take()
        val scored = rawChunks.map { chunk ->
            ChunkScore(chunk, computeChunkScore(chunk, query))
        }.sortedByDescending { it.score }

        val grouped = scored.groupBy { it.chunk.materialId }
        val limitedChunks = grouped.flatMap { (_, entries) -> entries.take(maxPerMaterial) }

        return limitedChunks.mapNotNull { (chunk, _) ->
            val mat = materialDao.getById(chunk.materialId) ?: return@mapNotNull null
            buildChunkSearchResult(chunk, mat.title, query)
        }
    }

    /** Internal holder for chunk + score, used only during sorting. */
    private data class ChunkScore(val chunk: MaterialChunk, val score: Int)

    companion object {
        /** Pure function: build a [SearchResult] for a chunk hit. */
        fun buildChunkSearchResult(
            chunk: MaterialChunk,
            materialTitle: String,
            query: String
        ): SearchResult {
            val snippet = extractSnippet(chunk.content, query)
            return SearchResult(
                id = chunk.id,
                type = "chunk",
                title = materialTitle,
                subtitle = "片段 ${chunk.chunkIndex + 1}：$snippet",
                route = Screen.MaterialDetail.route(chunk.materialId, chunk.chunkIndex),
                materialId = chunk.materialId,
                matchedChunkIndex = chunk.chunkIndex,
                sortKey = 2
            )
        }

        /**
         * Compute a relevance score for a chunk match.
         * Higher = more relevant.
         *
         * Factors:
         * - Hit position: earlier hit in content → higher score (max 100)
         * - Chunk index: lower index → slightly higher score (max 10)
         */
        fun computeChunkScore(chunk: MaterialChunk, query: String): Int {
            val hitPos = chunk.content.indexOf(query, ignoreCase = true)
            val positionScore = if (hitPos >= 0) (100 - hitPos.coerceAtMost(99)) else 0
            val indexScore = (10 - chunk.chunkIndex.coerceAtMost(9)).coerceAtLeast(0)
            return positionScore + indexScore
        }

        /** Extract a snippet around the first match of [query] in [content]. */
        fun extractSnippet(content: String, query: String, contextLen: Int = 40): String {
            val idx = content.indexOf(query, ignoreCase = true)
            if (idx < 0) return content.take(contextLen * 2) + "…"
            val start = (idx - contextLen).coerceAtLeast(0)
            val end = (idx + query.length + contextLen).coerceAtMost(content.length)
            val prefix = if (start > 0) "…" else ""
            val suffix = if (end < content.length) "…" else ""
            return prefix + content.substring(start, end) + suffix
        }

        private fun buildSubtitle(subject: String, detail: String): String = buildString {
            if (subject.isNotBlank()) append(subject)
            if (subject.isNotBlank() && detail.isNotBlank()) append(" · ")
            if (detail.isNotBlank()) append(detail.take(50))
        }
    }
}
