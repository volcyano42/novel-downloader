package com.noveldownloader.source

import com.noveldownloader.data.model.ChapterItem
import com.noveldownloader.data.model.NovelInfo
import com.noveldownloader.data.model.SearchResult

/** 书源核心接口。每个平台实现一个。 */
interface NovelSource {
    /** 平台标识，如 "fanqie" */
    val name: String

    /** 中文显示名，如 "番茄" */
    val showName: String

    /** 支持的域名列表，用于 URL 匹配 */
    val hosts: List<String>

    /** 小说 ID 正则（从 URL 提取 novelId） */
    val idPattern: Regex

    /** 搜索小说 */
    suspend fun search(query: String): List<SearchResult>

    /** 获取小说详情 */
    suspend fun novelInfo(url: String): NovelInfo

    /** 获取章节目录 */
    suspend fun chapterList(url: String): List<ChapterItem>

    /** 获取章节正文 */
    suspend fun chapterContent(url: String): String

    /** 根据 URL 提取 novelId，失败返回 null */
    fun extractNovelId(url: String): String? {
        return idPattern.find(url)?.groupValues?.getOrNull(1)
    }

    /** 判断 URL 是否属于此书源 */
    fun matches(url: String): Boolean {
        val host = try {
            java.net.URI(url).host ?: return false
        } catch (_: Exception) {
            return false
        }
        return hosts.any { host == it || host.endsWith(".$it") }
    }
}
