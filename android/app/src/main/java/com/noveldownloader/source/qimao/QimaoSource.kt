package com.noveldownloader.source.qimao

import com.noveldownloader.data.model.ChapterItem
import com.noveldownloader.data.model.NovelInfo
import com.noveldownloader.data.model.SearchResult
import com.noveldownloader.engine.HttpEngine
import com.noveldownloader.source.NovelSource
import com.google.gson.JsonParser
import org.jsoup.Jsoup
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class QimaoSource @Inject constructor(
    private val http: HttpEngine,
) : NovelSource {
    override val name = "qimao"
    override val showName = "七猫"
    override val hosts = listOf("www.qimao.com", "qimao.com")
    override val idPattern = Regex("""/shuku/(\d+)""")

    override suspend fun search(query: String): List<SearchResult> {
        val encoded = java.net.URLEncoder.encode(query, "UTF-8")
        val url = "https://www.qimao.com/api/def/cp/search/query?keyword=$encoded&page=1&size=20"
        val json = http.get(url)
        val root = JsonParser.parseString(json).asJsonObject
        val books = root.getAsJsonObject("data")
            ?.getAsJsonArray("books")
            ?: return emptyList()
        return books.mapNotNull { item ->
            val obj = item.asJsonObject
            val bookId = obj.get("book_id")?.asLong?.toString() ?: return@mapNotNull null
            SearchResult(
                novelId = "qimao_$bookId",
                name = obj.get("book_name")?.asString ?: "",
                author = obj.get("author")?.asString ?: "",
                coverUrl = obj.get("cover")?.asString ?: "",
                url = "https://www.qimao.com/shuku/$bookId/",
                description = obj.get("description")?.asString ?: "",
                platform = name,
                status = obj.get("status_cn")?.asString ?: "",
            )
        }
    }

    override suspend fun novelInfo(url: String): NovelInfo {
        val html = http.get(url)
        val doc = Jsoup.parse(html)
        return NovelInfo(
            novelId = extractNovelId(url) ?: "qimao_unknown",
            name = doc.selectFirst("h1")?.text() ?: "",
            author = doc.selectFirst(".author")?.text()?.replace("作者：", "") ?: "",
            coverUrl = doc.selectFirst(".cover-img img")?.attr("src") ?: "",
            description = doc.selectFirst(".intro")?.text() ?: "",
            status = doc.selectFirst(".status")?.text() ?: "",
            totalChapters = 0,
        )
    }

    override suspend fun chapterList(url: String): List<ChapterItem> {
        // 七猫章节列表主要通过 Rain API 获取，requests 模式下返回空
        return emptyList()
    }

    override suspend fun chapterContent(url: String): String {
        val html = http.get(url)
        val doc = Jsoup.parse(html)
        return doc.selectFirst(".article")?.html()
            ?.replace("<br>", "\n")
            ?.replace("<br/>", "\n")
            ?: ""
    }
}
