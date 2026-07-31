package com.noveldownloader.source.qidian

import com.noveldownloader.data.model.ChapterItem
import com.noveldownloader.data.model.NovelInfo
import com.noveldownloader.data.model.SearchResult
import com.noveldownloader.engine.HttpEngine
import com.noveldownloader.source.NovelSource
import org.jsoup.Jsoup
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class QidianSource @Inject constructor(
    private val http: HttpEngine,
) : NovelSource {
    override val name = "qidian"
    override val showName = "起点"
    override val hosts = listOf("www.qidian.com", "book.qidian.com")
    override val idPattern = Regex("""(\d{10})""")

    override suspend fun search(query: String): List<SearchResult> {
        val encoded = java.net.URLEncoder.encode(query, "UTF-8")
        val html = http.get("https://www.qidian.com/search?kw=$encoded")
        val doc = Jsoup.parse(html)
        return doc.select("#result-list .book-mid-info").map { el ->
            val link = el.selectFirst("h2 a") ?: return@map null
            val href = link.attr("href")
            val bookId = extractNovelId(href) ?: return@map null
            SearchResult(
                novelId = "qidian_$bookId",
                name = link.text(),
                author = el.selectFirst(".author a.name")?.text() ?: "",
                coverUrl = "https:$href",  // placeholder
                url = "https:$href",
                description = el.selectFirst(".intro")?.text() ?: "",
                platform = name,
                status = "",
            )
        }.filterNotNull()
    }

    override suspend fun novelInfo(url: String): NovelInfo {
        val html = http.get(url)
        val doc = Jsoup.parse(html)
        return NovelInfo(
            novelId = extractNovelId(url) ?: "qidian_unknown",
            name = doc.selectFirst(".book-info h1 em")?.text()
                ?: doc.selectFirst("h1")?.text() ?: "",
            author = doc.selectFirst(".book-info .writer")?.text() ?: "",
            coverUrl = doc.selectFirst(".book-img img")?.attr("src") ?: "",
            description = doc.selectFirst(".book-info .book-intro p")?.text() ?: "",
            status = "",
            totalChapters = 0,
        )
    }

    override suspend fun chapterList(url: String): List<ChapterItem> {
        // 起点章节列表由 JS 动态加载，requests 模式下无法直接获取
        // 返回空列表，浏览器模式下可通过 Playwright 获取
        return emptyList()
    }

    override suspend fun chapterContent(url: String): String {
        val html = http.get(url)
        val doc = Jsoup.parse(html)
        return doc.selectFirst(".read-content")?.text()
            ?.replace("\u3000\u3000", "\n\u3000\u3000")
            ?: ""
    }
}
