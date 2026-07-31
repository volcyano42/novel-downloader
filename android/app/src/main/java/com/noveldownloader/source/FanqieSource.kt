package com.noveldownloader.source

import com.noveldownloader.engine.HttpEngine
import com.noveldownloader.data.*
import com.google.gson.JsonParser

class FanqieSource(private val http: HttpEngine) : NovelSource {
    override val name = "fanqie"
    override val showName = "番茄"
    override val hosts = listOf("fanqienovel.com", "changdunovel.com")
    override val idPattern = Regex("""(\d{19})""")

    override suspend fun search(query: String): List<SearchResult> {
        val json = http.postJson(
            "https://novel.snssdk.com/api/novel/channel/homepage/search/search/v1/",
            """{"aid":1967,"q":"$query","offset":0,"query_type":0}"""
        )
        val root = JsonParser.parseString(json).asJsonObject
        val items = root.getAsJsonObject("data")?.getAsJsonArray("ret_data") ?: return emptyList()
        return items.mapNotNull { item ->
            val obj = item.asJsonObject
            val book = obj.getAsJsonObject("book_data") ?: return@mapNotNull null
            val bid = book.get("book_id").asString
            SearchResult(
                novelId = "fanqie_$bid", name = book.get("book_name")?.asString ?: "",
                author = book.get("author")?.asString ?: "",
                coverUrl = book.get("thumb_url")?.asString ?: "",
                url = "https://fanqienovel.com/page/$bid",
                description = book.get("abstract")?.asString ?: "",
                platform = name,
            )
        }
    }

    override suspend fun novelInfo(url: String): NovelInfo {
        val novelId = extractNovelId(url) ?: throw RuntimeException("Cannot extract ID from $url")
        val api = "https://api5-normal-sinfonlineb.fqnovel.com/reading/bookapi/audio/toneinfo/?book_id=$novelId&aid=1967&version_code=58932&device_platform=android"
        val json = http.get(api)
        val data = JsonParser.parseString(json).asJsonObject.getAsJsonObject("data")
            ?: throw RuntimeException("Novel not found: $url")
        return NovelInfo(
            novelId = "fanqie_$novelId", name = data.get("book_name")?.asString ?: "",
            author = data.get("author")?.asString ?: "",
            coverUrl = data.get("thumb_url")?.asString ?: "",
            description = data.get("abstract")?.asString ?: "",
        )
    }

    override suspend fun chapterList(url: String): List<ChapterItem> {
        val novelId = extractNovelId(url) ?: throw RuntimeException("Cannot extract ID from $url")
        val json = http.get("https://fanqienovel.com/api/reader/directory/detail?bookId=$novelId")
        val root = JsonParser.parseString(json).asJsonObject
        val volumes = root.getAsJsonObject("data")?.getAsJsonArray("chapterListWithVolume") ?: return emptyList()
        val result = mutableListOf<ChapterItem>()
        volumes.forEach { v ->
            v.asJsonObject.getAsJsonArray("chapterList")?.forEach { c ->
                val ch = c.asJsonObject
                val cid = ch.get("itemId")?.asString ?: return@forEach
                result.add(ChapterItem(chapterId = cid, title = ch.get("title")?.asString ?: "",
                    url = "https://fanqienovel.com/reader/$cid", order = result.size + 1))
            }
        }
        return result
    }

    override suspend fun chapterContent(url: String): String {
        val cid = url.substringAfterLast("/").substringBefore("?")
            .ifEmpty { throw RuntimeException("Cannot extract chapter ID from $url") }
        val json = http.get("https://novel.snssdk.com/api/novel/book/reader/full/v1/?item_id=$cid&aid=1967&device_platform=android")
        val content = JsonParser.parseString(json).asJsonObject
            .getAsJsonObject("data")?.get("content")?.asString ?: return ""
        return content.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
            .replace("</p><p>", "\n\n").replace("<p>", "").replace("</p>", "")
    }
}
