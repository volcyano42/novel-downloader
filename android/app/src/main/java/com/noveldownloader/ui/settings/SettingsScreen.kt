package com.noveldownloader.ui.settings

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
import com.noveldownloader.config.AppSettings
import com.noveldownloader.data.model.ExportFormat

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    navController: NavHostController,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val settings by viewModel.settings.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("设置") },
                navigationIcon = {
                    IconButton(onClick = { navController.popBackStack() }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("导出设置", style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ExportFormat.entries.forEach { format ->
                    FilterChip(
                        selected = settings.exportFormat == format.extension,
                        onClick = {
                            viewModel.updateSettings { it.copy(exportFormat = format.extension) }
                        },
                        label = { Text(format.label) },
                    )
                }
            }

            HorizontalDivider()

            Text("下载设置", style = MaterialTheme.typography.titleMedium)
            Text("并发数: ${settings.maxWorkers}")
            Slider(
                value = settings.maxWorkers.toFloat(),
                onValueChange = { v ->
                    viewModel.updateSettings { it.copy(maxWorkers = v.toInt()) }
                },
                valueRange = 1f..5f,
                steps = 3,
            )

            Text("请求间隔: ${settings.requestDelay}ms")
            Slider(
                value = settings.requestDelay.toFloat(),
                onValueChange = { v ->
                    viewModel.updateSettings { it.copy(requestDelay = v.toLong()) }
                },
                valueRange = 500f..5000f,
            )

            HorizontalDivider()

            Text("关于", style = MaterialTheme.typography.titleMedium)
            Text(
                "小说下载器 v1.0.0\n多平台小说搜索下载工具",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
            )
        }
    }
}
