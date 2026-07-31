package com.noveldownloader.source

import com.noveldownloader.engine.HttpEngine
import com.noveldownloader.data.*
import org.jsoup.Jsoup

class Xs92Source(private val http: HttpEngine) : NovelSource {
    override val name = "92xs"
    override val showName = "就爱文学"
    override val hosts = listOf("www.92xs.org", "92xs.org")
    override val idPattern = Regex("""/book/(\d+)\.html""")

    override suspend fun search(query: String): List<SearchResult> {
        val html = http.get("https://www.92xs.org/modules/article/search.php?searchkey=${java.net.URLEncoder.encode(query, "GBK")}", "GBK")
        return Jsoup.parse(html).select(".grid tr").drop(1).mapNotNull { row ->
            val cells = row.select("td")
            if (cells.size < 3) return@mapNotNull null
            val link = cells[0].selectFirst("a") ?: return@mapNotNull null
            val href = link.attr("href")
            val bid = extractNovelId(href) ?: return@mapNotNull null
            SearchResult(novelId = "92xs_$bid", name = link.text(), author = cells[2].text(),
                url = href, platform = name)
        }
    }

    override suspend fun novelInfo(url: String): NovelInfo {
        val doc = Jsoup.parse(http.get(url, "GBK"))
        return NovelInfo(novelId = extractNovelId(url) ?: "92xs_unknown",
            name = doc.selectFirst("#info h1")?.text() ?: "",
            author = doc.selectFirst("#info p")?.text()?.replace("作者：", "") ?: "",
            coverUrl = doc.selectFirst("#fmimg img")?.attr("src") ?: "",
            description = doc.selectFirst("#intro")?.text() ?: "")
    }

    override suspend fun chapterList(url: String): List<ChapterItem> {
        val doc = Jsoup.parse(http.get(url, "GBK"))
        return doc.select("#list dd a").mapIndexed { i, link ->
            ChapterItem(chapterId = "${i + 1}", title = link.text(), url = link.attr("href"), order = i + 1)
        }
    }

    override suspend fun chapterContent(url: String): String {
        return Jsoup.parse(http.get(url, "GBK")).selectFirst("#content")?.html()
            ?.replace("&nbsp;", " ")?.replace("<br>", "\n")?.replace("<br/>", "\n") ?: ""
    }
}
