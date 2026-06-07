package com.example.mathagent

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import androidx.test.ext.junit.runners.AndroidJUnit4

/**
 * Compose UI smoke test for MainActivity.
 * Uses testTags for reliable, unambiguous assertions.
 */
@RunWith(AndroidJUnit4::class)
class MainActivitySmokeTest {

    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun launch_showsDashboard() {
        composeRule.onNodeWithTag("screen-dashboard").assertIsDisplayed()
    }

    @Test
    fun launch_topbarTitle_isDashboard() {
        composeRule.onNodeWithTag("topbar-title").assertTextEquals("工作台")
    }

    @Test
    fun navigateToErrors_showsErrors() {
        composeRule.onNodeWithText("错题本").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("screen-errors").assertIsDisplayed()
    }

    @Test
    fun navigateToReview_showsReview() {
        composeRule.onNodeWithText("今日复习").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("screen-review").assertIsDisplayed()
    }

    @Test
    fun navigateToPlans_showsPlans() {
        composeRule.onNodeWithText("学习计划").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("screen-plans").assertIsDisplayed()
    }

    @Test
    fun navigateToMaterials_showsMaterials() {
        composeRule.onNodeWithText("资料").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("screen-materials").assertIsDisplayed()
    }

    @Test
    fun navigateToSettings_showsSettings() {
        composeRule.onNodeWithContentDescription("设置").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("screen-settings").assertIsDisplayed()
        composeRule.onNodeWithTag("topbar-title").assertTextEquals("设置")
    }

    @Test
    fun navigateToSettings_showsBackupSection() {
        composeRule.onNodeWithContentDescription("设置").performClick()
        composeRule.waitForIdle()
        // Settings page is scrollable; scroll to find the backup section
        composeRule.onNodeWithTag("screen-settings").performScrollToNode(
            androidx.compose.ui.test.hasTestTag("backup-section")
        )
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("backup-section").assertIsDisplayed()
        composeRule.onNodeWithTag("backup-export-button").assertIsDisplayed()
        composeRule.onNodeWithTag("backup-import-button").assertIsDisplayed()
    }

    @Test
    fun navigateToSearch_showsSearch() {
        composeRule.onNodeWithContentDescription("搜索").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("screen-search").assertIsDisplayed()
        composeRule.onNodeWithTag("topbar-title").assertTextEquals("搜索")
    }

    @Test
    fun navigateBackToDashboard_showsDashboard() {
        composeRule.onNodeWithText("错题本").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithText("工作台").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("screen-dashboard").assertIsDisplayed()
        composeRule.onNodeWithTag("topbar-title").assertTextEquals("工作台")
    }
}
