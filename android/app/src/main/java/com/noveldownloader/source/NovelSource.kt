package com.noveldownloader.source

import com.noveldownloader.data.*

interface NovelSource {
    val name: String
    val showName: String
    val hosts: List<String>
    val idPattern: Regex

    suspend fun search(query: String): List<SearchResult>
    suspend fun novelInfo(url: String): NovelInfo
    suspend fun chapterList(url: String): List<ChapterItem>
    suspend fun chapterContent(url: String): String

    fun extractNovelId(url: String): String? =
        idPattern.find(url)?.groupValues?.getOrNull(1)

    fun matches(url: String): Boolean =
        hosts.any { url.contains(it) }
}
