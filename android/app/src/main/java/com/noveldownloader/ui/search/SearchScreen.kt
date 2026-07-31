package com.noveldownloader.ui.search

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
import com.noveldownloader.data.model.SearchResult
import com.noveldownloader.ui.components.EmptyState
import com.noveldownloader.ui.components.ErrorBanner
import com.noveldownloader.ui.navigation.Screen
import com.noveldownloader.util.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SearchScreen(
    navController: NavHostController,
    viewModel: SearchViewModel = hiltViewModel(),
) {
    val query by viewModel.query.collectAsStateWithLifecycle()
    val state by viewModel.state.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    OutlinedTextField(
                        value = query,
                        onValueChange = viewModel::onQueryChanged,
                        placeholder = { Text("搜索书名或作者...") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
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
                ErrorBanner(s.message, modifier = Modifier.padding(padding))
            }
            is UiState.Success -> {
                val results = s.data
                if (results.isEmpty()) {
                    EmptyState(
                        if (query.length < 2) "输入至少 2 个字符开始搜索" else "未找到结果",
                        modifier = Modifier.padding(padding),
                    )
                } else {
                    LazyColumn(contentPadding = PaddingValues(padding)) {
                        results.forEach { (platform, items) ->
                            item {
                                Text(
                                    text = platform,
                                    style = MaterialTheme.typography.titleMedium,
                                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
                                    color = MaterialTheme.colorScheme.primary,
                                )
                            }
                            items(items, key = { it.novelId }) { novel ->
                                SearchResultRow(
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
}

@Composable
private fun SearchResultRow(
    novel: SearchResult,
    onClick: () -> Unit,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
    ) {
        Text(
            text = novel.name,
            style = MaterialTheme.typography.bodyLarge,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(modifier = Modifier.height(2.dp))
        Text(
            text = "${novel.author} · ${novel.platform}",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f),
        )
        if (novel.description.isNotEmpty()) {
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                text = novel.description,
                style = MaterialTheme.typography.bodySmall,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            )
        }
    }
}
