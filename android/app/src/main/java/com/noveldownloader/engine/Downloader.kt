package com.noveldownloader.engine

import com.noveldownloader.data.*
import com.noveldownloader.source.SourceRegistry
import com.noveldownloader.storage.DatabaseHelper
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit

class Downloader(
    private val registry: SourceRegistry,
    private val db: DatabaseHelper,
    private val rateLimiter: RateLimiter,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val semaphore = Semaphore(3)

    data class Progress(
        var total: Int = 0, var completed: Int = 0, var failed: Int = 0,
        var currentChapter: String = "", var finished: Boolean = false,
    )

    fun download(novelId: String, onProgress: (Progress) -> Unit) {
        scope.launch {
            val novel = db.getNovel(novelId) ?: return@launch
            val source = registry.getByName(novel.platform) ?: return@launch
            val items = source.chapterList(novel.url)
            if (items.isEmpty()) return@launch

            val progress = Progress(total = items.size)
            val chapters = items.map { Chapter(it.chapterId, novelId, it.title, it.url, it.order) }
            db.upsertChapters(chapters)
            onProgress(progress)

            coroutineScope {
                items.forEach { item ->
                    launch {
                        semaphore.withPermit {
                            try {
                                rateLimiter.wait(novel.platform)
                                progress.currentChapter = item.title
                                onProgress(progress)
                                val content = source.chapterContent(item.url)
                                db.updateChapterContent(novelId, item.chapterId, content)
                                progress.completed++
                            } catch (e: Exception) { progress.failed++ }
                        }
                    }
                }
            }
            progress.finished = true
            db.upsertNovel(novel.copy(downloadedChapters = progress.completed, totalChapters = progress.total))
            onProgress(progress)
        }
    }
}
