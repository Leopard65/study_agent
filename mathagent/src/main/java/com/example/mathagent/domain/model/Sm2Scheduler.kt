package com.example.mathagent.domain.model

/**
 * Stateless SM-2 spaced repetition scheduler.
 *
 * Implements a day-level variant of the SuperMemo-2 algorithm.
 * All time-dependent calls accept [nowMillis] from the caller so
 * that the logic is fully deterministic and testable.
 *
 * ## Rules
 *
 * ### Ease Factor
 * - New EF = old EF + (0.1 - (5 - rating) * (0.08 + (5 - rating) * 0.02))
 * - EF is clamped to a minimum of **1.3** (intervals never collapse).
 *
 * ### Interval (in days)
 * | Quality | Repetition 0 | Repetition 1 | Repetition 2+                 |
 * |---------|--------------|--------------|-------------------------------|
 * | Again   | 0 (same day) | 0 (same day) | 0 (same day)                  |
 * | Hard    | 1            | 1            | max(interval × 1.2, 1)        |
 * | Good    | 1            | 6            | max(interval × EF, 1)         |
 * | Easy    | 4            | max(10, EF×6)| max(interval × EF × 1.3, 10)  |
 *
 * ### Repetition count
 * - quality ≥ 3 (Good / Easy): repetitionCount += 1
 * - quality < 3 (Again / Hard): repetitionCount is **reset to 0**
 *
 * ### nextReviewAt
 * - Computed as `nowMillis + intervalDays × MILLIS_PER_DAY`.
 * - When intervalDays = 0 (Again), nextReviewAt = nowMillis
 *   so the card is immediately re-due.
 */
object Sm2Scheduler {

    private const val MILLIS_PER_DAY = 24L * 60 * 60 * 1000
    private const val MIN_EASE_FACTOR = 1.3f

    /**
     * Compute the updated review record parameters after a review.
     *
     * @param record       The current review record (before review).
     *                     Uses [ReviewRecord] from the data layer via typealias.
     * @param quality      How well the student recalled the material.
     * @param nowMillis    Current time in milliseconds (caller-provided for testability).
     * @return A pair of (newIntervalDays, newEaseFactor) plus the new repetitionCount
     *         and nextReviewAt timestamp.  Returned as a [ScheduleResult].
     */
    fun schedule(
        record: ReviewRecord,
        quality: ReviewQuality,
        nowMillis: Long
    ): ScheduleResult {
        val oldEf = record.easeFactor
        val oldInterval = record.intervalDays
        val oldRep = record.repetitionCount
        val rating = quality.rating

        // --- Ease factor (SM-2 formula) ---
        val efDelta = 0.1f - (5 - rating) * (0.08f + (5 - rating) * 0.02f)
        val newEf = (oldEf + efDelta).coerceAtLeast(MIN_EASE_FACTOR)

        // --- Interval ---
        val newInterval = when (quality) {
            ReviewQuality.Again -> 0  // re-due immediately (same day)
            ReviewQuality.Hard -> when {
                oldRep == 0 -> 1
                oldRep == 1 -> 1
                else -> (oldInterval * 1.2).toInt().coerceAtLeast(1)
            }
            ReviewQuality.Good -> when {
                oldRep == 0 -> 1
                oldRep == 1 -> 6
                else -> (oldInterval * newEf).toInt().coerceAtLeast(1)
            }
            ReviewQuality.Easy -> when {
                oldRep == 0 -> 4
                oldRep == 1 -> (newEf * 6).toInt().coerceAtLeast(10)
                else -> (oldInterval * newEf * 1.3).toInt().coerceAtLeast(10)
            }
        }

        // --- Repetition count ---
        val newRep = if (quality.rating >= 3) {
            oldRep + 1  // Good / Easy → advance
        } else {
            0           // Again / Hard → reset
        }

        // --- Timestamps ---
        val nextReviewAt = nowMillis + newInterval * MILLIS_PER_DAY

        return ScheduleResult(
            intervalDays = newInterval,
            easeFactor = newEf,
            repetitionCount = newRep,
            nextReviewAt = nextReviewAt,
            lastReviewedAt = nowMillis
        )
    }

    /**
     * The result of scheduling a review.
     */
    data class ScheduleResult(
        val intervalDays: Int,
        val easeFactor: Float,
        val repetitionCount: Int,
        val nextReviewAt: Long,
        val lastReviewedAt: Long
    )
}
