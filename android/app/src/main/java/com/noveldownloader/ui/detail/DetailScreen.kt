package com.noveldownloader.ui.detail

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import com.noveldownloader.ui.components.ChapterItemRow
import com.noveldownloader.ui.components.EmptyState
import com.noveldownloader.ui.components.ErrorBanner
import com.noveldownloader.ui.navigation.Screen
import com.noveldownloader.util.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DetailScreen(
    novelId: String,
    navController: NavHostController,
    viewModel: DetailViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text((state as? UiState.Success)?.data?.novel?.name ?: "详情") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
        bottomBar = {
            val s = state as? UiState.Success ?: return@Scaffold
            if (!s.data.isInBookshelf && s.data.novel != null) {
                Surface(Modifier.fillMaxWidth()) {
                    Button(
                        onClick = { viewModel.addToBookshelfAndFetchChapters() },
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                    ) {
                        Text("加入书架并下载")
                    }
                }
            } else if (s.data.isInBookshelf) {
                Surface(Modifier.fillMaxWidth()) {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(16.dp),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        OutlinedButton(
                            onClick = {
                                navController.navigate(Screen.Download.createRoute(novelId))
                            },
                            modifier = Modifier.weight(1f),
                        ) { Text("下载全部") }
                        Button(
                            onClick = {
                                navController.navigate(Screen.Reader.createRoute(novelId, 0))
                            },
                            modifier = Modifier.weight(1f),
                        ) { Text("开始阅读") }
                    }
                }
            }
        },
    ) { padding ->
        when (val s = state) {
            is UiState.Loading -> {
                Box(Modifier.fillMaxSize().padding(padding)) {
                    CircularProgressIndicator(Modifier.padding(32.dp))
                }
            }
            is UiState.Error -> {
                ErrorBanner(s.message, modifier = Modifier.padding(padding))
            }
            is UiState.Success -> {
                val detail = s.data
                LazyColumn(contentPadding = padding) {
                    // 小说信息
                    item {
                        Column(Modifier.padding(16.dp)) {
                            Text(detail.novel?.name ?: "", style = MaterialTheme.typography.headlineMedium)
                            Spacer(Modifier.height(4.dp))
                            Text(
                                "作者: ${detail.novel?.author ?: ""}",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                            )
                            if (!detail.novel?.description.isNullOrEmpty()) {
                                Spacer(Modifier.height(8.dp))
                                Text(
                                    detail.novel!!.description,
                                    style = MaterialTheme.typography.bodyMedium,
                                    maxLines = 5,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                        }
                        HorizontalDivider()
                    }

                    // 章节列表
                    if (detail.chapters.isEmpty()) {
                        item {
                            EmptyState(
                                "暂无章节\n请先加入书架获取章节列表",
                                modifier = Modifier.height(200.dp),
                            )
                        }
                    } else {
                        items(detail.chapters.take(200), key = { it.chapterId }) { item ->
                            ChapterItemRow(
                                chapter = com.noveldownloader.data.model.Chapter(
                                    chapterId = item.chapterId,
                                    novelId = novelId,
                                    title = item.title,
                                    url = item.url,
                                    order = item.order,
                                ),
                                onClick = {
                                    navController.navigate(
                                        Screen.Reader.createRoute(novelId, item.order - 1)
                                    )
                                },
                            )
                            HorizontalDivider()
                        }
                    }
                }
            }
        }
    }
}
