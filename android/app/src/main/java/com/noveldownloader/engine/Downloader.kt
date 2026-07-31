package com.noveldownloader.engine

import com.noveldownloader.data.db.ChapterDao
import com.noveldownloader.data.db.NovelDao
import com.noveldownloader.data.model.*
import com.noveldownloader.source.SourceRegistry
import com.noveldownloader.util.AppError
import com.noveldownloader.util.DownloadProgress
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import javax.inject.Inject
import javax.inject.Singleton

/** 章节下载调度器。 */
@Singleton
class Downloader @Inject constructor(
    private val registry: SourceRegistry,
    private val novelDao: NovelDao,
    private val chapterDao: ChapterDao,
    private val rateLimiter: RateLimiter,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val semaphore = Semaphore(3) // 最多 3 个并发

    /** 开始下载小说全部章节，返回进度 Flow。 */
    fun download(novelId: String): Flow<DownloadProgress> {
        val flow = MutableSharedFlow<DownloadProgress>(replay = 1)
        scope.launch {
            try {
                val novel = novelDao.getById(novelId) ?: throw AppError.NovelNotFound(novelId)
                val source = registry.getByName(novel.platform)
                    ?: throw AppError.ParseError("未知平台: ${novel.platform}")

                // 获取章节列表
                val items = source.chapterList(novel.url)
                if (items.isEmpty()) throw AppError.ParseError("章节列表为空")

                val total = items.size
                var completed = 0
                var failed = 0

                // 先批量插入章节（不含正文）
                val chapters = items.map { item ->
                    Chapter(
                        chapterId = item.chapterId,
                        novelId = novelId,
                        title = item.title,
                        url = item.url,
                        order = item.order,
                    )
                }
                chapterDao.upsertAll(chapters)

                flow.emit(DownloadProgress(novelId, total, 0, 0, "准备下载..."))

                // 并发下载每章正文
                coroutineScope {
                    items.forEach { item ->
                        launch {
                            semaphore.withPermit {
                                try {
                                    rateLimiter.wait(novel.platform)
                                    flow.emit(DownloadProgress(novelId, total, completed, failed, item.title))
                                    val content = source.chapterContent(item.url)
                                    chapterDao.updateContent(item.chapterId, content)
                                    completed++
                                } catch (_: Exception) {
                                    failed++
                                }
                            }
                        }
                    }
                }

                flow.emit(DownloadProgress(novelId, total, completed, failed, "", isFinished = true))

                // 更新小说下载进度
                novelDao.upsert(novel.copy(
                    downloadedChapters = completed,
                    totalChapters = total,
                    updatedAt = System.currentTimeMillis(),
                ))
            } catch (e: Exception) {
                flow.emit(DownloadProgress(novelId, isFinished = true))
            }
        }
        return flow
    }
}
