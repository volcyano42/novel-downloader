package com.noveldownloader.source.fanqie

import com.noveldownloader.data.model.ChapterItem
import com.noveldownloader.data.model.NovelInfo
import com.noveldownloader.data.model.SearchResult
import com.noveldownloader.engine.HttpEngine
import com.noveldownloader.source.NovelSource
import com.google.gson.JsonParser
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class FanqieSource @Inject constructor(
    private val http: HttpEngine,
) : NovelSource {
    override val name = "fanqie"
    override val showName = "番茄"
    override val hosts = listOf("fanqienovel.com", "changdunovel.com")
    override val idPattern = Regex("""(\d{19})""")

    override suspend fun search(query: String): List<SearchResult> {
        val url = "https://novel.snssdk.com/api/novel/channel/homepage/search/search/v1/"
        val body = """
            {"aid":1967,"q":"$query","offset":0,"query_type":0}
        """.trimIndent()
        val json = http.postJson(url, body)
        val root = JsonParser.parseString(json).asJsonObject
        val items = root.getAsJsonObject("data")
            ?.getAsJsonArray("ret_data")
            ?: return emptyList()
        return items.mapNotNull { item ->
            val obj = item.asJsonObject
            val book = obj.getAsJsonObject("book_data") ?: return@mapNotNull null
            SearchResult(
                novelId = "fanqie_${book.get("book_id").asString}",
                name = book.get("book_name")?.asString ?: "",
                author = book.get("author")?.asString ?: "",
                coverUrl = book.get("thumb_url")?.asString ?: "",
                url = "https://fanqienovel.com/page/${book.get("book_id").asString}",
                description = book.get("abstract")?.asString ?: "",
                platform = name,
                status = book.get("creation_status")?.asString ?: "",
            )
        }
    }

    override suspend fun novelInfo(url: String): NovelInfo {
        val novelId = extractNovelId(url) ?: throw com.noveldownloader.util.AppError.NovelNotFound(url)
        val apiUrl = ("https://api5-normal-sinfonlineb.fqnovel.com/reading/bookapi/audio/toneinfo/" +
            "?is_exempt=false&book_id=$novelId&iid=3314387856142496&device_id=3314387856138400" +
            "&ac=wifi&channel=43536151a&aid=1967&app_name=novelapp&version_code=58932" +
            "&version_name=5.8.9.32&device_platform=android&os=android&ssmix=a" +
            "&device_type=HD1900&device_brand=OnePlus&language=zh&os_api=28&os_version=9" +
            "&manifest_version_code=58932&resolution=1080*1920&dpi=480" +
            "&update_version_code=58932&_rticket=${System.currentTimeMillis()}")
        val json = http.get(apiUrl)
        val root = JsonParser.parseString(json).asJsonObject
        val data = root.getAsJsonObject("data") ?: throw com.noveldownloader.util.AppError.NovelNotFound(url)
        return NovelInfo(
            novelId = "fanqie_$novelId",
            name = data.get("book_name")?.asString ?: "",
            author = data.get("author")?.asString ?: "",
            coverUrl = data.get("thumb_url")?.asString ?: "",
            description = data.get("abstract")?.asString ?: "",
            status = data.get("creation_status")?.asString ?: "",
            totalChapters = 0,
        )
    }

    override suspend fun chapterList(url: String): List<ChapterItem> {
        val novelId = extractNovelId(url) ?: throw com.noveldownloader.util.AppError.NovelNotFound(url)
        val apiUrl = "https://fanqienovel.com/api/reader/directory/detail?bookId=$novelId"
        val json = http.get(apiUrl)
        val root = JsonParser.parseString(json).asJsonObject
        val chapters = root.getAsJsonObject("data")
            ?.getAsJsonArray("chapterListWithVolume")
            ?: return emptyList()
        val result = mutableListOf<ChapterItem>()
        chapters.forEach { volume ->
            val vol = volume.asJsonObject
            vol.getAsJsonArray("chapterList")?.forEach { ch ->
                val obj = ch.asJsonObject
                result.add(ChapterItem(
                    chapterId = obj.get("itemId")?.asString ?: "",
                    title = obj.get("title")?.asString ?: "",
                    url = "https://fanqienovel.com/reader/${obj.get("itemId")?.asString}",
                    order = result.size + 1,
                ))
            }
        }
        return result
    }

    override suspend fun chapterContent(url: String): String {
        val chapterId = idPattern.find(url)?.groupValues?.getOrNull(1)
            ?: java.net.URI(url).path.split("/").lastOrNull()
            ?: throw com.noveldownloader.util.AppError.ParseError("无法提取章节 ID: $url")
        val novelId = chapterId // 番茄的 chapter itemId 即 chapter id
        val apiUrl = ("https://novel.snssdk.com/api/novel/book/reader/full/v1/" +
            "?item_id=$novelId&aid=1967&channel=43536151a&device_platform=android")
        val json = http.get(apiUrl)
        val root = JsonParser.parseString(json).asJsonObject
        val content = root.getAsJsonObject("data")
            ?.get("content")?.asString
            ?: return ""
        // 替换换行标签
        return content.replace("<br>", "\n")
            .replace("<br/>", "\n")
            .replace("<br />", "\n")
            .replace("</p><p>", "\n\n")
            .replace("<p>", "").replace("</p>", "")
    }
}
