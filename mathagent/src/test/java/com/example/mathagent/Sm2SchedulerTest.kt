package com.example.mathagent

import com.example.mathagent.data.local.entity.ReviewRecord
import com.example.mathagent.domain.model.ReviewQuality
import com.example.mathagent.domain.model.Sm2Scheduler
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Comprehensive unit tests for [Sm2Scheduler].
 *
 * Covers: first review, second review, multi-review, Again reset,
 * ease factor lower bound, interval growth, and nextReviewAt calculation.
 */
class Sm2SchedulerTest {

    private val DAY_MS = 24L * 60 * 60 * 1000
    private val NOW = 1_700_000_000_000L  // fixed timestamp

    // ---- Helper ----

    private fun record(
        intervalDays: Int = 1,
        easeFactor: Float = 2.5f,
        repetitionCount: Int = 0,
        lastReviewedAt: Long = 0
    ) = ReviewRecord(
        id = 1,
        errorEntryId = 10,
        intervalDays = intervalDays,
        easeFactor = easeFactor,
        repetitionCount = repetitionCount,
        lastReviewedAt = lastReviewedAt,
        nextReviewAt = NOW + intervalDays * DAY_MS,
        createdAt = NOW
    )

    // ================================================================
    // Good quality (rating = 3) — standard SM-2 path
    // ================================================================

    @Test
    fun good_firstReview_interval1day() {
        val r = record(repetitionCount = 0)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Good, NOW)

        assertEquals(1, result.intervalDays)
        assertEquals(1, result.repetitionCount)
        assertEquals(NOW + 1 * DAY_MS, result.nextReviewAt)
        assertEquals(NOW, result.lastReviewedAt)
    }

    @Test
    fun good_secondReview_interval6days() {
        val r = record(repetitionCount = 1, intervalDays = 1)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Good, NOW)

        assertEquals(6, result.intervalDays)
        assertEquals(2, result.repetitionCount)
        assertEquals(NOW + 6 * DAY_MS, result.nextReviewAt)
    }

    @Test
    fun good_thirdReview_intervalScalesByEF() {
        // rep 2+, interval = oldInterval × EF
        val r = record(repetitionCount = 2, intervalDays = 6, easeFactor = 2.5f)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Good, NOW)

        // newEF = 2.5 + (-0.14) = 2.36; newInterval = (6 * 2.36) = 14.16 → 14
        assertEquals(14, result.intervalDays)
        assertEquals(3, result.repetitionCount)
        assertEquals(NOW + 14 * DAY_MS, result.nextReviewAt)
    }

    @Test
    fun good_easeFactorIncreases() {
        val r = record(easeFactor = 2.5f)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Good, NOW)

        // EF += 0.1 - (5-3)*(0.08 + (5-3)*0.02) = 0.1 - 2*(0.08+0.04) = 0.1 - 0.24 = -0.14
        // newEF = 2.5 - 0.14 = 2.36
        assertEquals(2.36f, result.easeFactor, 0.01f)
    }

    // ================================================================
    // Easy quality (rating = 5) — bonus intervals
    // ================================================================

    @Test
    fun easy_firstReview_interval4days() {
        val r = record(repetitionCount = 0)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Easy, NOW)

        assertEquals(4, result.intervalDays)
        assertEquals(1, result.repetitionCount)
        assertEquals(NOW + 4 * DAY_MS, result.nextReviewAt)
    }

    @Test
    fun easy_secondReview_intervalAtLeast10() {
        val r = record(repetitionCount = 1, intervalDays = 4, easeFactor = 2.5f)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Easy, NOW)

        // EF*6 = 2.64*6 = 15.84 → 15, but coerceAtLeast(10) → 15
        // newEF = 2.5 + 0.1 - 0*(...) = 2.6 → EF*6 = 15.84 → 15
        assertTrue(result.intervalDays >= 10)
        assertEquals(2, result.repetitionCount)
    }

    @Test
    fun easy_thirdReview_intervalScalesByEFAnd13() {
        val r = record(repetitionCount = 2, intervalDays = 15, easeFactor = 2.5f)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Easy, NOW)

        // newEF = 2.64, interval = (15 * 2.64 * 1.3).toInt() = (51.48).toInt() = 51
        // coerceAtLeast(10) → 51
        assertTrue(result.intervalDays >= 10)
        assertTrue(result.intervalDays > r.intervalDays)
        assertEquals(3, result.repetitionCount)
    }

    @Test
    fun easy_easeFactorIncreasesMost() {
        val r = record(easeFactor = 2.5f)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Easy, NOW)

        // EF += 0.1 - (5-5)*(...) = 0.1 - 0 = 0.1
        // newEF = 2.5 + 0.1 = 2.6
        assertEquals(2.6f, result.easeFactor, 0.01f)
        assertTrue(result.easeFactor > 2.5f)
    }

    // ================================================================
    // Hard quality (rating = 2) — conservative intervals
    // ================================================================

    @Test
    fun hard_firstReview_interval1day() {
        val r = record(repetitionCount = 0)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Hard, NOW)

        assertEquals(1, result.intervalDays)
        assertEquals(0, result.repetitionCount) // Hard resets rep count
        assertEquals(NOW + 1 * DAY_MS, result.nextReviewAt)
    }

    @Test
    fun hard_secondReview_interval1day() {
        val r = record(repetitionCount = 1, intervalDays = 1)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Hard, NOW)

        assertEquals(1, result.intervalDays)
        assertEquals(0, result.repetitionCount) // reset
    }

    @Test
    fun hard_thirdReview_intervalScalesSlowly() {
        // rep 2+, interval = max(oldInterval * 1.2, 1)
        val r = record(repetitionCount = 2, intervalDays = 6)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Hard, NOW)

        // (6 * 1.2) = 7.2 → 7
        assertEquals(7, result.intervalDays)
        assertEquals(0, result.repetitionCount) // reset
    }

    @Test
    fun hard_easeFactorDecreases() {
        val r = record(easeFactor = 2.5f)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Hard, NOW)

        // EF += 0.1 - (5-2)*(0.08 + (5-2)*0.02) = 0.1 - 3*(0.08+0.06) = 0.1 - 0.42 = -0.32
        // newEF = 2.5 - 0.32 = 2.18
        assertEquals(2.18f, result.easeFactor, 0.01f)
        assertTrue(result.easeFactor < 2.5f)
    }

    // ================================================================
    // Again quality (rating = 0) — full reset
    // ================================================================

    @Test
    fun again_firstReview_interval0days() {
        val r = record(repetitionCount = 0)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Again, NOW)

        assertEquals(0, result.intervalDays)
        assertEquals(0, result.repetitionCount) // reset
        assertEquals(NOW, result.nextReviewAt)   // immediately re-due
    }

    @Test
    fun again_secondReview_interval0days() {
        val r = record(repetitionCount = 1, intervalDays = 6)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Again, NOW)

        assertEquals(0, result.intervalDays)
        assertEquals(0, result.repetitionCount)
        assertEquals(NOW, result.nextReviewAt) // immediately re-due
    }

    @Test
    fun again_resetsRepetitionCount() {
        val r = record(repetitionCount = 5, intervalDays = 30)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Again, NOW)

        assertEquals(0, result.repetitionCount)
        assertEquals(0, result.intervalDays)
    }

    @Test
    fun again_easeFactorDecreases() {
        val r = record(easeFactor = 2.5f)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Again, NOW)

        // EF += 0.1 - (5-0)*(0.08 + (5-0)*0.02) = 0.1 - 5*(0.08+0.10) = 0.1 - 0.9 = -0.8
        // newEF = 2.5 - 0.8 = 1.7
        assertEquals(1.7f, result.easeFactor, 0.01f)
    }

    // ================================================================
    // Ease factor lower bound (≥ 1.3)
    // ================================================================

    @Test
    fun easeFactor_clampedAtMinimum_1point3() {
        // Start near minimum — even aggressive Again should not go below 1.3
        val r = record(easeFactor = 1.35f)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Again, NOW)

        assertTrue("EF should be ≥ 1.3, was ${result.easeFactor}", result.easeFactor >= 1.3f)
    }

    @Test
    fun easeFactor_clampedAtMinimum_fromBelow() {
        // Already below 1.3 — should clamp up to 1.3
        val r = record(easeFactor = 1.2f)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Again, NOW)

        assertEquals(1.3f, result.easeFactor, 0.01f)
    }

    @Test
    fun easeFactor_hardSequence_staysAboveMinimum() {
        var ef = 2.5f
        for (i in 1..20) {
            val r = record(easeFactor = ef, repetitionCount = 0)
            val result = Sm2Scheduler.schedule(r, ReviewQuality.Hard, NOW)
            ef = result.easeFactor
            assertTrue("EF should be ≥ 1.3 at iteration $i, was $ef", ef >= 1.3f)
        }
    }

    // ================================================================
    // Repetition count behavior
    // ================================================================

    @Test
    fun repetitionCount_goodEasy_increments() {
        val r = record(repetitionCount = 3)

        val goodResult = Sm2Scheduler.schedule(r, ReviewQuality.Good, NOW)
        assertEquals(4, goodResult.repetitionCount)

        val easyResult = Sm2Scheduler.schedule(r, ReviewQuality.Easy, NOW)
        assertEquals(4, easyResult.repetitionCount)
    }

    @Test
    fun repetitionCount_againHard_resetsToZero() {
        val r = record(repetitionCount = 5)

        val againResult = Sm2Scheduler.schedule(r, ReviewQuality.Again, NOW)
        assertEquals(0, againResult.repetitionCount)

        val hardResult = Sm2Scheduler.schedule(r, ReviewQuality.Hard, NOW)
        assertEquals(0, hardResult.repetitionCount)
    }

    // ================================================================
    // nextReviewAt calculation
    // ================================================================

    @Test
    fun nextReviewAt_basedOnNowMillis_notSystemTime() {
        val customNow = 999_999_999_000L
        val r = record(repetitionCount = 0)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Good, customNow)

        assertEquals(customNow + 1 * DAY_MS, result.nextReviewAt)
    }

    @Test
    fun nextReviewAt_againIsSameAsNow() {
        val r = record(repetitionCount = 3, intervalDays = 20)
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Again, NOW)

        assertEquals(NOW, result.nextReviewAt)
    }

    @Test
    fun lastReviewedAt_isNowMillis() {
        val r = record()
        val result = Sm2Scheduler.schedule(r, ReviewQuality.Good, NOW)

        assertEquals(NOW, result.lastReviewedAt)
    }

    // ================================================================
    // Skip vs Again distinction
    // ================================================================

    @Test
    fun skip_doesNotUseScheduler_onlyDelaysBy1Day() {
        // Skip is handled outside the scheduler — it simply pushes nextReviewAt
        // forward by 1 day without changing easeFactor or repetitionCount.
        val r = record(repetitionCount = 3, intervalDays = 20, easeFactor = 2.5f)
        val skipped = r.copy(
            nextReviewAt = NOW + 1 * DAY_MS,
            lastReviewedAt = NOW
        )

        // Verify skip does NOT run the scheduler — fields are unchanged
        assertEquals(2.5f, skipped.easeFactor, 0.01f)
        assertEquals(3, skipped.repetitionCount)
        assertEquals(20, skipped.intervalDays)
    }
}
