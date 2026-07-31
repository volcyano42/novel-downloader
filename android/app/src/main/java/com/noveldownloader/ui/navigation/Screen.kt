package com.noveldownloader.ui.navigation

/** 导航路由定义。 */
sealed class Screen(val route: String) {
    data object Bookshelf : Screen("bookshelf")
    data object Search : Screen("search")
    data object Detail : Screen("detail/{novelId}") {
        fun createRoute(novelId: String) = "detail/$novelId"
    }
    data object Download : Screen("download/{novelId}") {
        fun createRoute(novelId: String) = "download/$novelId"
    }
    data object Reader : Screen("reader/{novelId}/{chapterIndex}") {
        fun createRoute(novelId: String, chapterIndex: Int) = "reader/$novelId/$chapterIndex"
    }
    data object Settings : Screen("settings")
}
