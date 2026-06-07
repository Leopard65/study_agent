package com.example.mathagent.domain.model

/**
 * Review quality levels for the SM-2 spaced repetition algorithm.
 *
 * Each quality maps to a student-facing action and a numeric rating
 * used by [Sm2Scheduler] to compute the next review interval.
 *
 * | Quality | Rating | Meaning                        |
 * |---------|--------|--------------------------------|
 * | Again   | 0      | Completely forgotten           |
 * | Hard    | 2      | Recalled with difficulty       |
 * | Good    | 3      | Recalled correctly             |
 * | Easy    | 5      | Recalled effortlessly          |
 */
enum class ReviewQuality(val rating: Int) {
    Again(0),
    Hard(2),
    Good(3),
    Easy(5)
}
