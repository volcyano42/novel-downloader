package com.noveldownloader.data

data class Novel(
    val novelId: String,
    val name: String,
    val author: String,
    val coverUrl: String = "",
    val platform: String = "",
    val url: String = "",
    val description: String = "",
    val totalChapters: Int = 0,
    val downloadedChapters: Int = 0,
    val status: String = "",
    val createdAt: Long = System.currentTimeMillis(),
)

data class Chapter(
    val chapterId: String,
    val novelId: String,
    val title: String,
    val url: String = "",
    val order: Int = 0,
    val content: String? = null,
    val isDownloaded: Boolean = false,
)

data class SearchResult(
    val novelId: String,
    val name: String,
    val author: String,
    val coverUrl: String = "",
    val url: String = "",
    val description: String = "",
    val platform: String = "",
    val status: String = "",
)

data class NovelInfo(
    val novelId: String,
    val name: String,
    val author: String,
    val coverUrl: String = "",
    val description: String = "",
)

data class ChapterItem(
    val chapterId: String,
    val title: String,
    val url: String = "",
    val order: Int = 0,
)
