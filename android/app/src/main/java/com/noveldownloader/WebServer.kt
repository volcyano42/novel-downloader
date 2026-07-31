package com.noveldownloader

import android.content.Context
import com.google.gson.Gson
import com.google.gson.JsonParser
import com.noveldownloader.config.ConfigManager
import com.noveldownloader.data.*
import com.noveldownloader.engine.Downloader
import com.noveldownloader.engine.HttpEngine
import com.noveldownloader.engine.RateLimiter
import com.noveldownloader.export.EpubExporter
import com.noveldownloader.export.TxtExporter
import com.noveldownloader.source.SourceRegistry
import com.noveldownloader.storage.DatabaseHelper
import fi.iki.elonen.NanoHTTPD
import kotlinx.coroutines.runBlocking
import java.io.ByteArrayInputStream
import java.io.InputStream
import java.util.UUID

class WebServer(
    port: Int,
    private val ctx: Context,
) : NanoHTTPD(port) {
    private val gson = Gson()
    private val http = HttpEngine()
    private val registry = SourceRegistry(http)
    private val db = DatabaseHelper(ctx)
    private val config = ConfigManager(ctx)
    private val limiter = RateLimiter()
    private val downloader = Downloader(registry, db, limiter)
    private val downloadTasks = mutableMapOf<String, Downloader.Progress>()

    override fun serve(session: IHTTPSession): Response {
        val uri = session.uri
        return try {
            when {
                uri.startsWith("/api/v2/") -> handleApi(session, uri.removePrefix("/api/v2/"))
                else -> serveStatic(uri)
            }
        } catch (e: Exception) {
            json(500, mapOf("ok" to false, "message" to (e.message ?: "error")))
        }
    }

    private fun serveStatic(uri: String): Response {
        val path = if (uri == "/" || uri.isEmpty()) "/index.html" else uri
        val assetPath = "frontend${path}"
        return try {
            val input = ctx.assets.open(assetPath)
            val mime = when { path.endsWith(".html") -> "text/html"
                path.endsWith(".js") -> "application/javascript"
                path.endsWith(".css") -> "text/css"
                path.endsWith(".svg") -> "image/svg+xml"
                path.endsWith(".png") -> "image/png"
                else -> "application/octet-stream" }
            newFixedLengthResponse(Response.Status.OK, mime, input, input.available().toLong())
        } catch (e: Exception) {
            // SPA fallback: serve index.html for non-asset routes
            try {
                val input = ctx.assets.open("frontend/index.html")
                newFixedLengthResponse(Response.Status.OK, "text/html", input, input.available().toLong())
            } catch (_: Exception) {
                newFixedLengthResponse(Response.Status.NOT_FOUND, "text/plain", "Not Found")
            }
        }
    }

    @Suppress("UNCHECKED_CAST")
    private fun handleApi(session: IHTTPSession, path: String): Response {
        val params = session.parms ?: emptyMap()
        val bodyStr = readBody(session)
        val method = session.method

        return when {
            // Search
            method == Method.GET && path == "download/search" -> {
                val platform = params["platform"] ?: "fanqie"
                val query = params["query"] ?: return json(400, mapOf("ok" to false, "message" to "query required"))
                val source = registry.getByName(platform) ?: registry.all.first()
                val results = runBlocking { source.search(query) }
                json(200, okData(results.map { r -> mapOf("title" to r.name, "author" to r.author,
                    "url" to r.url, "description" to r.description, "platform" to r.platform, "extra" to emptyMap<String,Any>()) }))
            }

            // Novel info
            method == Method.POST && path == "download/novel" -> {
                val body = JsonParser.parseString(bodyStr).asJsonObject
                val url = body.get("url")?.asString ?: return json(400, mapOf("ok" to false))
                val info = runBlocking {
                    val s = registry.resolve(url) ?: throw RuntimeException("Unknown platform")
                    s.novelInfo(url)
                }
                json(200, okData(mapOf("title" to info.name, "url" to url, "id" to info.novelId,
                    "author" to info.author, "description" to info.description, "cover" to info.coverUrl,
                    "serial" to 1, "tags" to emptyList<String>(), "count" to 0, "extra" to emptyMap<String,Any>())))
            }

            // Chapter list
            method == Method.GET && path.matches(Regex("download/novel/[^/]+/chapters")) -> {
                val url = params["url"] ?: return json(400, mapOf("ok" to false))
                val items = runBlocking {
                    val s = registry.resolve(url) ?: throw RuntimeException("Unknown platform")
                    s.chapterList(url)
                }
                json(200, okData(items.map { mapOf("id" to it.chapterId, "url" to it.url,
                    "novel_id" to "", "title" to it.title, "order" to it.order, "volume" to 0, "count" to 0) }))
            }

            // Download chapters
            method == Method.POST && path.matches(Regex("download/novel/[^/]+/chapter")) -> {
                val title = params["title"] ?: ""
                val novelUrl = params["novel_url"] ?: ""
                val platform = params["platform"] ?: ""
                val body = JsonParser.parseString(bodyStr).asJsonArray
                if (body.size() == 0) return json(400, mapOf("ok" to false, "message" to "empty"))
                val novelId = runBlocking {
                    val s = registry.resolve(novelUrl) ?: registry.getByName(platform) ?: registry.all.first()
                    val info = s.novelInfo(novelUrl)
                    val nid = "${s.name}_${s.extractNovelId(novelUrl)}"
                    db.upsertNovel(Novel(novelId = nid, name = title, author = info.author,
                        coverUrl = info.coverUrl, platform = s.name, url = novelUrl, description = info.description))
                    nid
                }
                val taskId = UUID.randomUUID().toString()
                val progress = Downloader.Progress()
                downloadTasks[taskId] = progress
                Thread {
                    downloader.download(novelId) { p -> progress.total = p.total; progress.completed = p.completed
                        progress.failed = p.failed; progress.currentChapter = p.currentChapter; progress.finished = p.finished }
                }.start()
                json(200, okData(mapOf("task_id" to taskId)))
            }

            // Tasks
            method == Method.GET && path == "download/tasks" -> {
                json(200, okData(downloadTasks.map { (id, p) -> mapOf("task_id" to id,
                    "status" to if (p.finished) "completed" else "downloading", "progress" to p.completed, "total" to p.total) }))
            }

            // Delete task
            method == Method.DELETE && path.startsWith("download/task/") -> {
                val taskId = path.removePrefix("download/task/").substringBefore("/")
                downloadTasks.remove(taskId)
                json(200, mapOf("ok" to true, "message" to "ok"))
            }

            // Storage - list novels
            method == Method.GET && path == "storage/novel" -> {
                val novels = db.allNovels().map { n -> mapOf("title" to n.name, "url" to n.url,
                    "id" to n.novelId, "author" to n.author, "description" to n.description,
                    "count" to n.totalChapters, "cover" to n.coverUrl, "serial" to 1,
                    "tags" to emptyList<String>(), "extra" to emptyMap<String,Any>()) }
                json(200, okData(novels))
            }

            // Storage - novel meta
            method == Method.GET && path.matches(Regex("storage/novel/[^/]+/meta")) -> {
                val id = path.split("/")[2]
                val n = db.getNovel(id) ?: return json(404, mapOf("ok" to false))
                json(200, okData(mapOf("title" to n.name, "url" to n.url, "id" to n.novelId,
                    "author" to n.author, "description" to n.description, "count" to n.totalChapters,
                    "cover" to n.coverUrl, "serial" to 1, "tags" to emptyList<String>(), "extra" to emptyMap<String,Any>())))
            }

            // Storage - delete novel
            method == Method.DELETE && path.matches(Regex("storage/novel/[^/]+$")) -> {
                val id = path.split("/").last()
                db.deleteNovel(id)
                json(200, mapOf("ok" to true, "message" to "deleted"))
            }

            // Storage - chapters
            method == Method.GET && path.matches(Regex("storage/novel/[^/]+/chapters$")) -> {
                val id = path.split("/")[2]
                val chs = db.getChapters(id).map { mapOf("id" to it.chapterId, "url" to it.url,
                    "novel_id" to it.novelId, "title" to it.title, "order" to it.order,
                    "volume" to 0, "count" to 0, "downloaded" to it.isDownloaded) }
                json(200, okData(chs))
            }

            // Storage - chapter content
            method == Method.GET && path.matches(Regex("storage/novel/[^/]+/chapter/[^/]+$")) -> {
                val parts = path.split("/")
                val ch = db.getChapter(parts[2], parts[4])
                    ?: return json(404, mapOf("ok" to false))
                json(200, okData(mapOf("id" to ch.chapterId, "novel_id" to ch.novelId,
                    "title" to ch.title, "content" to (ch.content ?: ""), "order" to ch.order)))
            }

            // Export
            method == Method.POST && path == "export" -> {
                val body = JsonParser.parseString(bodyStr).asJsonObject
                val novelId = body.get("novel_id")?.asString ?: return json(400, mapOf("ok" to false))
                val novel = db.getNovel(novelId) ?: return json(404, mapOf("ok" to false))
                val chapters = db.getChapters(novelId).filter { it.isDownloaded && it.content != null }
                val taskId = UUID.randomUUID().toString()
                val data = when {
                    body.has("txt") -> TxtExporter.export(novel, chapters)
                    body.has("epub") -> EpubExporter.export(novel, chapters)
                    else -> TxtExporter.export(novel, chapters)
                }
                val file = java.io.File(ctx.cacheDir, "${taskId}.txt")
                file.writeBytes(data)
                json(200, okData(mapOf("task_id" to taskId, "path" to file.absolutePath)))
            }

            // Export download
            method == Method.GET && path.startsWith("export/download/") -> {
                val taskId = path.removePrefix("export/download/")
                val file = java.io.File(ctx.cacheDir, "${taskId}.txt")
                if (!file.exists()) return json(404, mapOf("ok" to false))
                newFixedLengthResponse(Response.Status.OK, "application/octet-stream",
                    file.inputStream(), file.length())
            }

            // Config
            method == Method.GET && path == "config" -> {
                val c = config.load()
                json(200, okData(mapOf("mode" to c.mode, "max_workers" to c.maxWorkers,
                    "notify" to mapOf("on_complete" to c.notify.onComplete))))
            }

            method == Method.PUT && path == "config" -> {
                val body = JsonParser.parseString(bodyStr).asJsonObject
                val c = config.load()
                val updated = c.copy(mode = body.get("mode")?.asString ?: c.mode,
                    maxWorkers = body.get("max_workers")?.asInt ?: c.maxWorkers)
                config.save(updated)
                json(200, mapOf("ok" to true, "message" to "ok"))
            }

            // Groups
            method == Method.GET && path == "config/groups" ->
                json(200, okData(config.loadGroups()))
            method == Method.PUT && path == "config/groups" -> {
                val groups: Map<String, Any> = gson.fromJson(bodyStr, Map::class.java) as Map<String, Any>
                config.saveGroups(groups)
                json(200, mapOf("ok" to true, "message" to "ok"))
            }

            // Sources
            method == Method.GET && path == "download/sources" -> {
                val sources = registry.all.associate { s -> s.name to mapOf(
                    "hosts" to s.hosts, "show_name" to s.showName,
                    "id_pattern" to s.idPattern.pattern,
                    "capabilities" to mapOf("requests" to listOf("search", "novel_info", "chapter_list", "chapter_content"))) }
                json(200, okData(sources))
            }

            // Platform list
            method == Method.GET && path == "download/platform" -> {
                json(200, okData(registry.all.map { mapOf("id" to it.name, "label" to it.showName) }))
            }

            // 404
            else -> json(404, mapOf("ok" to false, "message" to "not found: $path"))
        }
    }

    private fun readBody(session: IHTTPSession): String {
        val map = HashMap<String, String>()
        session.parseBody(map)
        // POST → map["postData"]（原始 body）；PUT → map["content"]（NanoHTTPD 存入临时文件路径）
        map["postData"]?.let { return it }
        map["content"]?.let { path ->
            return runCatching { java.io.File(path).readText() }.getOrDefault("")
        }
        return ""
    }

    private fun json(status: Int, data: Any): Response {
        val text = gson.toJson(data)
        return newFixedLengthResponse(Response.Status.lookup(status), "application/json; charset=utf-8", text)
    }

    private fun okData(data: Any) = mapOf("ok" to true, "message" to "", "data" to data)
}
