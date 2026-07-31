package com.noveldownloader.data.model

import kotlinx.serialization.Serializable

/** 小说详情（部分字段入库到 Novel）。 */
@Serializable
data class NovelInfo(
    val novelId: String,
    val name: String,
    val author: String,
    val coverUrl: String = "",
    val description: String = "",
    val status: String = "",
    val totalChapters: Int = 0,
)
