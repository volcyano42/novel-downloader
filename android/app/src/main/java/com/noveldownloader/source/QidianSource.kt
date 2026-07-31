package com.noveldownloader.source

import com.noveldownloader.engine.HttpEngine
import com.noveldownloader.data.*
import org.jsoup.Jsoup

class QidianSource(private val http: HttpEngine) : NovelSource {
    override val name = "qidian"
    override val showName = "起点"
    override val hosts = listOf("www.qidian.com", "book.qidian.com")
    override val idPattern = Regex("""(\d{10})""")

    override suspend fun search(query: String): List<SearchResult> {
        val html = http.get("https://www.qidian.com/search?kw=${java.net.URLEncoder.encode(query, "UTF-8")}")
        return Jsoup.parse(html).select("#result-list .book-mid-info").mapNotNull { el ->
            val link = el.selectFirst("h2 a") ?: return@mapNotNull null
            val href = link.attr("href")
            val bid = extractNovelId(href) ?: return@mapNotNull null
            SearchResult(novelId = "qidian_$bid", name = link.text(),
                author = el.selectFirst(".author a.name")?.text() ?: "",
                url = "https:$href", description = el.selectFirst(".intro")?.text() ?: "", platform = name)
        }
    }

    override suspend fun novelInfo(url: String): NovelInfo {
        val doc = Jsoup.parse(http.get(url))
        return NovelInfo(novelId = extractNovelId(url) ?: "qidian_unknown",
            name = doc.selectFirst(".book-info h1 em")?.text() ?: doc.selectFirst("h1")?.text() ?: "",
            author = doc.selectFirst(".book-info .writer")?.text() ?: "",
            coverUrl = doc.selectFirst(".book-img img")?.attr("src") ?: "",
            description = doc.selectFirst(".book-info .book-intro p")?.text() ?: "")
    }

    override suspend fun chapterList(url: String): List<ChapterItem> = emptyList()

    override suspend fun chapterContent(url: String): String {
        return Jsoup.parse(http.get(url)).selectFirst(".read-content")?.text()
            ?.replace("\u3000\u3000", "\n\u3000\u3000") ?: ""
    }
}
