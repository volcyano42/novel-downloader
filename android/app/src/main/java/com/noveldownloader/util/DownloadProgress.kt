package com.noveldownloader.util

/** 下载进度。 */
data class DownloadProgress(
    val novelId: String,
    val total: Int = 0,
    val completed: Int = 0,
    val failed: Int = 0,
    val currentChapter: String = "",
    val isFinished: Boolean = false,
) {
    val percentage: Float
        get() = if (total > 0) completed.toFloat() / total else 0f
}
