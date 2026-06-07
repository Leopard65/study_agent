package com.example.mathagent.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.example.mathagent.LocalViewModelFactory
import com.example.mathagent.ui.screens.dashboard.DashboardScreen
import com.example.mathagent.ui.screens.errors.ErrorDetailScreen
import com.example.mathagent.ui.screens.errors.ErrorListScreen
import com.example.mathagent.ui.screens.materials.MaterialDetailScreen
import com.example.mathagent.ui.screens.materials.MaterialListScreen
import com.example.mathagent.ui.screens.plans.PlanListScreen
import com.example.mathagent.ui.screens.review.ReviewScreen
import com.example.mathagent.ui.screens.search.SearchScreen
import com.example.mathagent.ui.screens.settings.SettingsScreen
import com.example.mathagent.ui.viewmodel.DashboardViewModel
import com.example.mathagent.ui.viewmodel.ErrorDetailViewModel
import com.example.mathagent.ui.viewmodel.ErrorListViewModel
import com.example.mathagent.ui.viewmodel.MaterialDetailViewModel
import com.example.mathagent.ui.viewmodel.MaterialListViewModel
import com.example.mathagent.ui.viewmodel.PlanListViewModel
import com.example.mathagent.ui.viewmodel.ReviewViewModel
import com.example.mathagent.ui.viewmodel.SearchViewModel
import com.example.mathagent.ui.viewmodel.SettingsViewModel

@Composable
fun MathAgentNavHost(
    navController: NavHostController,
    modifier: Modifier = Modifier
) {
    NavHost(
        navController = navController,
        startDestination = Screen.Dashboard.route,
        modifier = modifier
    ) {
        composable(Screen.Dashboard.route) {
            val vm: DashboardViewModel = viewModel(factory = LocalViewModelFactory.current)
            DashboardScreen(navController = navController, viewModel = vm)
        }
        composable(Screen.Errors.route) {
            val vm: ErrorListViewModel = viewModel(factory = LocalViewModelFactory.current)
            ErrorListScreen(
                viewModel = vm,
                onErrorClick = { errorId ->
                    navController.navigate(Screen.ErrorDetail.route(errorId))
                }
            )
        }
        composable(Screen.Review.route) {
            val vm: ReviewViewModel = viewModel(factory = LocalViewModelFactory.current)
            ReviewScreen(viewModel = vm)
        }
        composable(Screen.Plans.route) {
            val vm: PlanListViewModel = viewModel(factory = LocalViewModelFactory.current)
            PlanListScreen(viewModel = vm)
        }
        composable(Screen.Materials.route) {
            val vm: MaterialListViewModel = viewModel(factory = LocalViewModelFactory.current)
            MaterialListScreen(
                viewModel = vm,
                onMaterialClick = { materialId ->
                    navController.navigate(Screen.MaterialDetail.route(materialId))
                }
            )
        }
        composable(Screen.Settings.route) {
            val vm: SettingsViewModel = viewModel(factory = LocalViewModelFactory.current)
            SettingsScreen(settingsViewModel = vm)
        }
        composable(Screen.Search.route) {
            val vm: SearchViewModel = viewModel(factory = LocalViewModelFactory.current)
            SearchScreen(navController = navController, viewModel = vm)
        }
        composable(
            route = Screen.ErrorDetail.ROUTE_PATTERN,
            arguments = listOf(navArgument("errorId") { type = NavType.LongType })
        ) { backStackEntry ->
            val errorId = backStackEntry.arguments?.getLong("errorId") ?: return@composable
            val vm: ErrorDetailViewModel = viewModel(factory = LocalViewModelFactory.current)
            ErrorDetailScreen(
                errorId = errorId,
                onBack = { navController.popBackStack() },
                viewModel = vm
            )
        }
        composable(
            route = Screen.MaterialDetail.ROUTE_PATTERN,
            arguments = listOf(
                navArgument("materialId") { type = NavType.LongType },
                navArgument("chunkIndex") {
                    type = NavType.IntType
                    defaultValue = -1
                }
            )
        ) { backStackEntry ->
            val materialId = backStackEntry.arguments?.getLong("materialId") ?: return@composable
            val chunkIndex = backStackEntry.arguments?.getInt("chunkIndex")?.takeIf { it >= 0 }
            val vm: MaterialDetailViewModel = viewModel(factory = LocalViewModelFactory.current)
            MaterialDetailScreen(
                materialId = materialId,
                onBack = { navController.popBackStack() },
                highlightChunkIndex = chunkIndex,
                viewModel = vm
            )
        }
    }
}
