package com.noveldownloader.ui.bookshelf

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import com.noveldownloader.data.model.Novel
import com.noveldownloader.ui.components.EmptyState
import com.noveldownloader.ui.components.ErrorBanner
import com.noveldownloader.ui.components.NovelCard
import com.noveldownloader.ui.navigation.Screen
import com.noveldownloader.util.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BookshelfScreen(
    navController: NavHostController,
    viewModel: BookshelfViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("书架") },
                actions = {
                    IconButton(onClick = { navController.navigate(Screen.Search.route) }) {
                        Icon(Icons.Default.Search, contentDescription = "搜索")
                    }
                    IconButton(onClick = { navController.navigate(Screen.Settings.route) }) {
                        Icon(Icons.Default.Settings, contentDescription = "设置")
                    }
                },
            )
        },
    ) { padding ->
        when (val s = state) {
            is UiState.Loading -> {
                Box(Modifier.fillMaxSize().padding(padding)) {
                    CircularProgressIndicator(Modifier.padding(32.dp))
                }
            }
            is UiState.Error -> {
                ErrorBanner(
                    message = s.message,
                    modifier = Modifier.padding(padding),
                )
            }
            is UiState.Success -> {
                val novels = s.data
                if (novels.isEmpty()) {
                    EmptyState(
                        "书架空空如也\n点击搜索开始找书",
                        modifier = Modifier.padding(padding),
                    )
                } else {
                    LazyVerticalGrid(
                        columns = GridCells.Fixed(2),
                        contentPadding = PaddingValues(
                            start = 16.dp, end = 16.dp,
                            top = padding.calculateTopPadding() + 8.dp,
                            bottom = 16.dp,
                        ),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        items(novels, key = { it.novelId }) { novel ->
                            NovelCard(
                                novel = novel,
                                onClick = {
                                    navController.navigate(Screen.Detail.createRoute(novel.novelId))
                                },
                            )
                        }
                    }
                }
            }
        }
    }
}
