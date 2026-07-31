package com.noveldownloader.source

import com.noveldownloader.engine.HttpEngine
import com.noveldownloader.data.*
import com.google.gson.JsonParser
import org.jsoup.Jsoup

class QimaoSource(private val http: HttpEngine) : NovelSource {
    override val name = "qimao"
    override val showName = "七猫"
    override val hosts = listOf("www.qimao.com", "qimao.com")
    override val idPattern = Regex("""/shuku/(\d+)""")

    override suspend fun search(query: String): List<SearchResult> {
        val json = http.get("https://www.qimao.com/api/def/cp/search/query?keyword=${java.net.URLEncoder.encode(query, "UTF-8")}&page=1&size=20")
        val books = JsonParser.parseString(json).asJsonObject.getAsJsonObject("data")?.getAsJsonArray("books") ?: return emptyList()
        return books.mapNotNull { item ->
            val obj = item.asJsonObject
            val bid = obj.get("book_id")?.asLong?.toString() ?: return@mapNotNull null
            SearchResult(novelId = "qimao_$bid", name = obj.get("book_name")?.asString ?: "",
                author = obj.get("author")?.asString ?: "", coverUrl = obj.get("cover")?.asString ?: "",
                url = "https://www.qimao.com/shuku/$bid/",
                description = obj.get("description")?.asString ?: "", platform = name)
        }
    }

    override suspend fun novelInfo(url: String): NovelInfo {
        val doc = Jsoup.parse(http.get(url))
        return NovelInfo(novelId = extractNovelId(url) ?: "qimao_unknown",
            name = doc.selectFirst("h1")?.text() ?: "",
            author = doc.selectFirst(".author")?.text()?.replace("作者：", "") ?: "",
            coverUrl = doc.selectFirst(".cover-img img")?.attr("src") ?: "",
            description = doc.selectFirst(".intro")?.text() ?: "")
    }

    override suspend fun chapterList(url: String): List<ChapterItem> = emptyList()

    override suspend fun chapterContent(url: String): String {
        return Jsoup.parse(http.get(url)).selectFirst(".article")?.html()
            ?.replace("<br>", "\n")?.replace("<br/>", "\n") ?: ""
    }
}
