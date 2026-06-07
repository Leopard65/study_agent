package com.example.mathagent

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.ui.test.assertIsNotSelected
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
 * Smoke tests for Phase 3.3 top-level routes and settings UI.
 *
 * Detail screen chrome hiding, material item click, and import confirmation
 * tests are in DetailScreenChromeTest and BackupImportLogicTest.
 */
@RunWith(AndroidJUnit4::class)
class Phase33ComposeTest {

    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    // ---- Top-level route smoke tests ----

    @Test
    fun topLevelRoute_showsTopBar() {
        composeRule.onNodeWithTag("topbar-title").assertIsDisplayed()
        composeRule.onNodeWithTag("topbar-title").assertTextEquals("工作台")
    }

    @Test
    fun topLevelRoute_showsBottomBar() {
        composeRule.onNodeWithText("错题本").assertIsDisplayed()
        composeRule.onNodeWithText("今日复习").assertIsDisplayed()
        composeRule.onNodeWithText("学习计划").assertIsDisplayed()
        composeRule.onNodeWithText("资料").assertIsDisplayed()
    }

    @Test
    fun settingsRoute_topBarShowsTitle() {
        composeRule.onNodeWithContentDescription("设置").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("topbar-title").assertTextEquals("设置")
    }

    @Test
    fun materialsScreen_hasTopBarAndBottomBar() {
        composeRule.onNodeWithText("资料").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("topbar-title").assertTextEquals("资料")
        composeRule.onNodeWithText("工作台").assertIsDisplayed()
    }

    @Test
    fun errorsScreen_hasTopBarAndBottomBar() {
        composeRule.onNodeWithText("错题本").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("topbar-title").assertTextEquals("错题本")
        composeRule.onNodeWithText("工作台").assertIsDisplayed()
    }

    // ---- Materials screen smoke test ----

    @Test
    fun materialsScreen_showsScreenTag() {
        composeRule.onNodeWithText("资料").performClick()
        composeRule.waitForIdle()
        composeRule.onNodeWithTag("screen-materials").assertIsDisplayed()
    }

    // ---- Import mode selection smoke tests ----

    @Test
    fun settings_importModeReplace_canBeSelected() {
        composeRule.onNodeWithContentDescription("设置").performClick()
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("screen-settings").performScrollToNode(hasTestTag("import-mode-replace-row"))
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("import-mode-replace-row").performClick()
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("import-mode-replace").assertIsSelected()
        composeRule.onNodeWithTag("import-mode-merge").assertIsNotSelected()
    }

    @Test
    fun settings_importModeSelection_showsLabels() {
        composeRule.onNodeWithContentDescription("设置").performClick()
        composeRule.waitForIdle()

        composeRule.onNodeWithText("合并导入（推荐）").assertIsDisplayed()
    }

    @Test
    fun settings_backupSection_exportButtonExists() {
        composeRule.onNodeWithContentDescription("设置").performClick()
        composeRule.waitForIdle()

        composeRule.onNodeWithTag("backup-export-button").assertIsDisplayed()
        composeRule.onNodeWithText("导出备份").assertIsDisplayed()
    }
}
