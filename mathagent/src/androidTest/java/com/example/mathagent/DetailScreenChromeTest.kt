package com.example.mathagent

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotDisplayed
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mathagent.data.local.MathAgentDatabase
import com.example.mathagent.data.local.entity.ErrorEntry
import com.example.mathagent.data.local.entity.Material
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import androidx.test.ext.junit.runners.AndroidJUnit4

/**
 * Tests for detail screen chrome hiding:
 * - From error list, click error -> detail page hides bottom nav and top bar
 * - From materials list, click material -> detail page hides bottom nav and top bar
 * - Back button returns to source page
 * - Material items have stable test tags
 *
 * Uses the real MainActivity database (math_agent.db) via MathAgentDatabase.getInstance().
 * Test data is inserted before each test and cleaned up after.
 */
@RunWith(AndroidJUnit4::class)
class DetailScreenChromeTest {

    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    private lateinit var db: MathAgentDatabase
    private lateinit var testErrorQuestion: String
    private lateinit var testMaterialTitle: String
    private var testMaterialId: Long = 0

    @Before
    fun setup() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        db = MathAgentDatabase.getInstance(context)

        // Create unique test data
        testErrorQuestion = "测试题目_1plus1_${System.nanoTime()}"
        testMaterialTitle = "测试资料_线代_${System.nanoTime()}"

        // Clean and insert test data
        runBlocking {
            db.errorEntryDao().deleteAllSync()
            db.materialDao().deleteAllSync()

            db.errorEntryDao().insert(
                ErrorEntry(
                    question = testErrorQuestion,
                    subject = "数学",
                    wrongAnswer = "3",
                    correctAnswer = "2"
                )
            )
            testMaterialId = db.materialDao().insert(
                Material(
                    title = testMaterialTitle,
                    subject = "数学",
                    description = "测试用的资料"
                )
            )
        }
        composeRule.waitForIdle()
    }

    @After
    fun teardown() {
        runBlocking {
            db.errorEntryDao().deleteAllSync()
            db.materialDao().deleteAllSync()
        }
    }

    @Test
    fun errorDetail_hidesGlobalChrome() {
        // Navigate to errors list
        composeRule.onNodeWithText("错题本").performClick()
        composeRule.waitForIdle()

        // Verify we're on errors screen with chrome
        composeRule.onNodeWithTag("screen-errors").assertIsDisplayed()
        composeRule.onNodeWithTag("topbar-title").assertIsDisplayed()

        // Click the error item using hasText matcher (partial match)
        composeRule.onNode(hasText(testErrorQuestion)).performClick()
        composeRule.waitForIdle()

        // Verify we're on error detail screen
        composeRule.onNodeWithTag("screen-error-detail").assertIsDisplayed()

        // Verify global chrome is hidden
        composeRule.onNodeWithTag("topbar-title").assertIsNotDisplayed()
        composeRule.onNodeWithText("工作台").assertIsNotDisplayed()
        composeRule.onNodeWithText("错题本").assertIsNotDisplayed()
        composeRule.onNodeWithText("今日复习").assertIsNotDisplayed()
        composeRule.onNodeWithText("学习计划").assertIsNotDisplayed()
        composeRule.onNodeWithText("资料").assertIsNotDisplayed()
    }

    @Test
    fun errorDetail_backButton_returnsToList() {
        // Navigate to errors list
        composeRule.onNodeWithText("错题本").performClick()
        composeRule.waitForIdle()

        // Click the error item
        composeRule.onNode(hasText(testErrorQuestion)).performClick()
        composeRule.waitForIdle()

        // Verify detail screen
        composeRule.onNodeWithTag("screen-error-detail").assertIsDisplayed()

        // Click back button
        composeRule.onNodeWithContentDescription("返回").performClick()
        composeRule.waitForIdle()

        // Verify we're back on errors list
        composeRule.onNodeWithTag("screen-errors").assertIsDisplayed()
        composeRule.onNodeWithTag("topbar-title").assertTextEquals("错题本")
    }

    @Test
    fun materialDetail_hidesGlobalChrome() {
        // Navigate to materials list
        composeRule.onNodeWithText("资料").performClick()
        composeRule.waitForIdle()

        // Verify we're on materials screen with chrome
        composeRule.onNodeWithTag("screen-materials").assertIsDisplayed()
        composeRule.onNodeWithTag("topbar-title").assertIsDisplayed()

        // Click the material item using hasText matcher
        composeRule.onNode(hasText(testMaterialTitle)).performClick()
        composeRule.waitForIdle()

        // Verify we're on material detail screen
        composeRule.onNodeWithTag("screen-material-detail").assertIsDisplayed()

        // Verify global chrome is hidden
        composeRule.onNodeWithTag("topbar-title").assertIsNotDisplayed()
        composeRule.onNodeWithText("工作台").assertIsNotDisplayed()
        composeRule.onNodeWithText("错题本").assertIsNotDisplayed()
        composeRule.onNodeWithText("今日复习").assertIsNotDisplayed()
        composeRule.onNodeWithText("学习计划").assertIsNotDisplayed()
        composeRule.onNodeWithText("资料").assertIsNotDisplayed()
    }

    @Test
    fun materialDetail_backButton_returnsToList() {
        // Navigate to materials list
        composeRule.onNodeWithText("资料").performClick()
        composeRule.waitForIdle()

        // Click the material item
        composeRule.onNode(hasText(testMaterialTitle)).performClick()
        composeRule.waitForIdle()

        // Verify detail screen
        composeRule.onNodeWithTag("screen-material-detail").assertIsDisplayed()

        // Click back button
        composeRule.onNodeWithContentDescription("返回").performClick()
        composeRule.waitForIdle()

        // Verify we're back on materials list
        composeRule.onNodeWithTag("screen-materials").assertIsDisplayed()
        composeRule.onNodeWithTag("topbar-title").assertTextEquals("资料")
    }

    @Test
    fun materialItem_hasStableTestTag() {
        // Navigate to materials list
        composeRule.onNodeWithText("资料").performClick()
        composeRule.waitForIdle()

        // Verify material item has stable test tag with the actual inserted id
        composeRule.onNodeWithTag("material-item-$testMaterialId").assertIsDisplayed()
    }
}
