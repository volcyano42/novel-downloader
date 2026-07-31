package com.noveldownloader.data.model

/** 搜索结果（不入库，仅传输）。 */
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
