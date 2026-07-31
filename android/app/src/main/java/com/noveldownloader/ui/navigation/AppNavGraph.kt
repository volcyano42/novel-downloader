package com.noveldownloader.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.noveldownloader.ui.bookshelf.BookshelfScreen
import com.noveldownloader.ui.detail.DetailScreen
import com.noveldownloader.ui.download.DownloadScreen
import com.noveldownloader.ui.reader.ReaderScreen
import com.noveldownloader.ui.search.SearchScreen
import com.noveldownloader.ui.settings.SettingsScreen

@Composable
fun AppNavGraph(
    navController: NavHostController = rememberNavController(),
) {
    NavHost(navController = navController, startDestination = Screen.Bookshelf.route) {
        composable(Screen.Bookshelf.route) {
            BookshelfScreen(navController = navController)
        }
        composable(Screen.Search.route) {
            SearchScreen(navController = navController)
        }
        composable(
            route = Screen.Detail.route,
            arguments = listOf(navArgument("novelId") { type = NavType.StringType })
        ) { backStackEntry ->
            val novelId = backStackEntry.arguments?.getString("novelId") ?: return@composable
            DetailScreen(novelId = novelId, navController = navController)
        }
        composable(
            route = Screen.Download.route,
            arguments = listOf(navArgument("novelId") { type = NavType.StringType })
        ) { backStackEntry ->
            val novelId = backStackEntry.arguments?.getString("novelId") ?: return@composable
            DownloadScreen(novelId = novelId, navController = navController)
        }
        composable(
            route = Screen.Reader.route,
            arguments = listOf(
                navArgument("novelId") { type = NavType.StringType },
                navArgument("chapterIndex") { type = NavType.IntType },
            )
        ) { backStackEntry ->
            val novelId = backStackEntry.arguments?.getString("novelId") ?: return@composable
            val chapterIndex = backStackEntry.arguments?.getInt("chapterIndex") ?: 0
            ReaderScreen(novelId = novelId, chapterIndex = chapterIndex, navController = navController)
        }
        composable(Screen.Settings.route) {
            SettingsScreen(navController = navController)
        }
    }
}
