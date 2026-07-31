package com.noveldownloader.util

/** 统一错误类型。 */
sealed class AppError(message: String, cause: Throwable? = null) : Exception(message, cause) {
    class NetworkError(val url: String, cause: Throwable? = null)
        : AppError("网络请求失败: $url", cause)

    class ParseError(val detail: String)
        : AppError("解析失败: $detail")

    class NovelNotFound(val url: String)
        : AppError("未找到小说: $url")

    class AntiCrawlError(val url: String, val retryAfter: Int = 60)
        : AppError("触发反爬，请等待 ${retryAfter}s")

    class StorageError(val path: String, cause: Throwable? = null)
        : AppError("存储错误: $path", cause)

    fun toUserMessage(): String = when (this) {
        is NetworkError -> "网络连接失败，请检查网络后重试"
        is ParseError -> "数据解析失败"
        is NovelNotFound -> "未找到该小说"
        is AntiCrawlError -> "请求过于频繁，${retryAfter}秒后自动重试"
        is StorageError -> "存储空间不足或文件写入失败"
    }
}
