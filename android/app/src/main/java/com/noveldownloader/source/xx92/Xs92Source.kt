package com.noveldownloader.source.xx92

import com.noveldownloader.data.model.ChapterItem
import com.noveldownloader.data.model.NovelInfo
import com.noveldownloader.data.model.SearchResult
import com.noveldownloader.engine.HttpEngine
import com.noveldownloader.source.NovelSource
import org.jsoup.Jsoup
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class Xs92Source @Inject constructor(
    private val http: HttpEngine,
) : NovelSource {
    override val name = "92xs"
    override val showName = "就爱文学"
    override val hosts = listOf("www.92xs.org", "92xs.org")
    override val idPattern = Regex("""/book/(\d+)\.html""")

    override suspend fun search(query: String): List<SearchResult> {
        val encoded = java.net.URLEncoder.encode(query, "GBK")
        val html = http.get("https://www.92xs.org/modules/article/search.php?searchkey=$encoded", charset = "GBK")
        val doc = Jsoup.parse(html)
        return doc.select(".grid tr").drop(1).mapNotNull { row ->
            val cells = row.select("td")
            if (cells.size < 3) return@mapNotNull null
            val link = cells[0].selectFirst("a") ?: return@mapNotNull null
            val href = link.attr("href")
            val bookId = extractNovelId(href) ?: return@mapNotNull null
            SearchResult(
                novelId = "92xs_$bookId",
                name = link.text(),
                author = cells[2].text(),
                coverUrl = "",
                url = href,
                description = "",
                platform = name,
                status = "",
            )
        }
    }

    override suspend fun novelInfo(url: String): NovelInfo {
        val html = http.get(url, charset = "GBK")
        val doc = Jsoup.parse(html)
        return NovelInfo(
            novelId = extractNovelId(url) ?: "92xs_unknown",
            name = doc.selectFirst("#info h1")?.text() ?: "",
            author = doc.selectFirst("#info p")?.text()?.replace("作者：", "") ?: "",
            coverUrl = doc.selectFirst("#fmimg img")?.attr("src") ?: "",
            description = doc.selectFirst("#intro")?.text() ?: "",
            status = "",
            totalChapters = 0,
        )
    }

    override suspend fun chapterList(url: String): List<ChapterItem> {
        val html = http.get(url, charset = "GBK")
        val doc = Jsoup.parse(html)
        return doc.select("#list dd a").mapIndexed { index, link ->
            ChapterItem(
                chapterId = "${index + 1}",
                title = link.text(),
                url = link.attr("href"),
                order = index + 1,
            )
        }
    }

    override suspend fun chapterContent(url: String): String {
        val html = http.get(url, charset = "GBK")
        val doc = Jsoup.parse(html)
        return doc.selectFirst("#content")?.html()
            ?.replace("&nbsp;", " ")
            ?.replace("<br>", "\n")
            ?.replace("<br/>", "\n")
            ?: ""
    }
}
