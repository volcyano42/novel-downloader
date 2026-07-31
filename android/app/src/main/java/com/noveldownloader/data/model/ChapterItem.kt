package com.noveldownloader.data.model

/** 章节列表项（传输用，不入库）。 */
data class ChapterItem(
    val chapterId: String,
    val title: String,
    val url: String = "",
    val order: Int = 0,
)
