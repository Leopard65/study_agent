package com.example.mathagent.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Warning
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(val route: String, val title: String, val icon: ImageVector) {
    data object Dashboard : Screen("dashboard", "工作台", Icons.Default.Home)
    data object Errors : Screen("errors", "错题本", Icons.Default.Warning)
    data object Review : Screen("review", "今日复习", Icons.Default.Refresh)
    data object Plans : Screen("plans", "学习计划", Icons.AutoMirrored.Filled.List)
    data object Materials : Screen("materials", "资料", Icons.Default.Info)
    data object Settings : Screen("settings", "设置", Icons.Default.Settings)
    data object Search : Screen("search", "搜索", Icons.Default.Search)

    /** Error detail with argument - not in bottom nav */
    class ErrorDetail(errorId: Long) : Screen("error_detail/$errorId", "错题详情", Icons.Default.Warning) {
        companion object {
            const val ROUTE_PATTERN = "error_detail/{errorId}"
            fun route(errorId: Long) = "error_detail/$errorId"
        }
    }

    /** Material detail with optional chunk highlight - not in bottom nav */
    class MaterialDetail(materialId: Long) : Screen("material_detail/$materialId", "资料详情", Icons.Default.Info) {
        companion object {
            const val ROUTE_PATTERN = "material_detail/{materialId}?chunkIndex={chunkIndex}"
            fun route(materialId: Long, chunkIndex: Int? = null): String =
                if (chunkIndex != null) "material_detail/$materialId?chunkIndex=$chunkIndex"
                else "material_detail/$materialId"
        }
    }

    companion object {
        /** All screens including non-bottom-nav ones (Search, Settings). */
        val allScreens = listOf(
            Dashboard, Errors, Review, Plans, Materials, Settings, Search
        )

        private val topLevelRoutes = setOf(
            Dashboard.route, Errors.route, Review.route, Plans.route,
            Materials.route, Settings.route, Search.route
        )

        /** Whether the given route is a top-level (non-detail) screen. */
        fun isTopLevelRoute(route: String?): Boolean =
            route != null && route in topLevelRoutes

        /** Detail route prefixes — only match error_detail and material_detail. */
        private val detailRoutePrefixes = listOf("error_detail/", "material_detail/")

        /** Whether the given route is a detail screen. */
        fun isDetailRoute(route: String?): Boolean =
            route != null && detailRoutePrefixes.any { route.startsWith(it) }

        /** Find the Screen for a given route, falling back to Dashboard. */
        fun fromRoute(route: String?): Screen =
            allScreens.find { it.route == route } ?: Dashboard

        /** Resolve title for a route: detail screens return their own title,
         *  top-level screens look up from [allScreens]. */
        fun resolveTitle(route: String?): String {
            // Check detail patterns
            if (route != null && route.startsWith("error_detail/")) return "错题详情"
            if (route != null && route.startsWith("material_detail/")) return "资料详情"
            return fromRoute(route).title
        }
    }
}

val bottomNavItems = listOf(
    Screen.Dashboard,
    Screen.Errors,
    Screen.Review,
    Screen.Plans,
    Screen.Materials
)
