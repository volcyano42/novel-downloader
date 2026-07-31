package com.noveldownloader.ui.reader

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.FormatSize
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavHostController
import com.noveldownloader.ui.components.EmptyState
import com.noveldownloader.ui.components.ErrorBanner
import com.noveldownloader.util.UiState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReaderScreen(
    novelId: String,
    chapterIndex: Int,
    navController: NavHostController,
    viewModel: ReaderViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    var showControls by remember { mutableStateOf(true) }
    var showFontSlider by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            AnimatedVisibility(visible = showControls) {
                TopAppBar(
                    title = {
                        Text(
                            (state as? UiState.Success)?.data?.currentChapter?.title ?: "阅读",
                            maxLines = 1,
                        )
                    },
                    navigationIcon = {
                        IconButton(onClick = { navController.popBackStack() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回")
                        }
                    },
                    actions = {
                        IconButton(onClick = { showFontSlider = !showFontSlider }) {
                            Icon(Icons.Default.FormatSize, contentDescription = "字号")
                        }
                        IconButton(onClick = { viewModel.toggleBackground() }) {
                            Icon(Icons.AutoMirrored.Filled.ArrowForward, contentDescription = "切换背景")
                        }
                    },
                )
            }
        },
        bottomBar = {
            AnimatedVisibility(visible = showControls) {
                val s = (state as? UiState.Success)?.data ?: return@AnimatedVisibility
                Surface {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(8.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        TextButton(
                            onClick = { viewModel.prevChapter() },
                            enabled = s.currentIndex > 0,
                        ) { Text("上一章") }
                        Text(
                            "${s.currentIndex + 1} / ${s.chapters.size}",
                            modifier = Modifier.align(Alignment.CenterVertically),
                            style = MaterialTheme.typography.bodySmall,
                        )
                        TextButton(
                            onClick = { viewModel.nextChapter() },
                            enabled = s.currentIndex < s.chapters.lastIndex,
                        ) { Text("下一章") }
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
                val reader = s.data
                val bgColor = if (reader.isDarkBg) Color(0xFF1A1A2E) else Color(0xFFFFF8E7)
                val textColor = if (reader.isDarkBg) Color(0xFFCCCCCC) else Color(0xFF333333)

                Column(modifier = Modifier.fillMaxSize()) {
                    // 字号 slider
                    AnimatedVisibility(visible = showFontSlider) {
                        Slider(
                            value = reader.fontSize,
                            onValueChange = viewModel::setFontSize,
                            valueRange = 14f..28f,
                            modifier = Modifier.padding(horizontal = 32.dp),
                        )
                    }

                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .background(bgColor)
                            .clickable(
                                indication = null,
                                interactionSource = remember { MutableInteractionSource() },
                            ) { showControls = !showControls }
                            .padding(padding),
                    ) {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize().padding(24.dp),
                        ) {
                            item {
                                Text(
                                    text = reader.currentChapter?.content
                                        ?.replace("\n\n", "\n")
                                        ?.replace("\n", "\n\n")
                                        ?: "（暂无内容）",
                                    style = MaterialTheme.typography.bodyLarge.copy(
                                        fontSize = reader.fontSize.sp,
                                        color = textColor,
                                        textAlign = TextAlign.Start,
                                    ),
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}
