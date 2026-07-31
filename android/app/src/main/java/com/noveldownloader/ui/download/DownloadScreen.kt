package com.noveldownloader.ui.download

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import com.noveldownloader.ui.components.ErrorBanner
import com.noveldownloader.ui.components.ProgressBar
import com.noveldownloader.util.DownloadProgress
import com.noveldownloader.util.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DownloadScreen(
    novelId: String,
    navController: NavHostController,
    viewModel: DownloadViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("下载") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
                actions = {
                    val progress = (state as? UiState.Success)?.data
                    if (progress != null && !progress.isFinished) {
                        TextButton(onClick = { viewModel.pauseDownload() }) {
                            Text("暂停")
                        }
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
                val progress = s.data
                Column(modifier = Modifier.padding(padding)) {
                    ProgressBar(progress)
                    if (progress.isFinished) {
                        Spacer(Modifier.height(16.dp))
                        Text(
                            text = if (progress.failed > 0)
                                "下载完成！${progress.completed} 章成功，${progress.failed} 章失败"
                            else "全部下载完成！共 ${progress.completed} 章",
                            style = MaterialTheme.typography.bodyLarge,
                            color = MaterialTheme.colorScheme.primary,
                            modifier = Modifier.padding(horizontal = 16.dp),
                        )
                    }
                }
            }
        }
    }
}
