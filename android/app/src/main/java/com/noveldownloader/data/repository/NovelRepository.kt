package com.noveldownloader.data.repository

import com.noveldownloader.data.db.ChapterDao
import com.noveldownloader.data.db.NovelDao
import com.noveldownloader.data.model.*
import com.noveldownloader.source.SourceRegistry
import com.noveldownloader.util.AppError
import javax.inject.Inject
import javax.inject.Singleton

/** 搜索 + 详情 + 书架管理。 */
@Singleton
class NovelRepository @Inject constructor(
    private val registry: SourceRegistry,
    private val novelDao: NovelDao,
    private val chapterDao: ChapterDao,
) {
    /** 多平台搜索，结果按平台分组。 */
    suspend fun search(query: String): Map<String, List<SearchResult>> {
        val results = mutableMapOf<String, List<SearchResult>>()
        registry.searchablePlatforms().forEach { source ->
            try {
                val items = source.search(query)
                if (items.isNotEmpty()) {
                    results[source.showName] = items
                }
            } catch (_: Exception) {
                // 单个平台失败静默跳过
            }
        }
        return results
    }

    /** 获取小说详情并返回 Novel 实体。 */
    suspend fun fetchNovelInfo(url: String): Novel {
        val source = registry.resolve(url) ?: throw AppError.NovelNotFound(url)
        val info = source.novelInfo(url)
        val novelId = source.extractNovelId(url) ?: throw AppError.ParseError("无法从 URL 提取小说 ID: $url")
        val fullNovelId = "${source.name}_$novelId"
        return Novel(
            novelId = fullNovelId,
            name = info.name,
            author = info.author,
            coverUrl = info.coverUrl,
            platform = source.name,
            url = url,
            description = info.description,
            status = info.status,
            totalChapters = info.totalChapters,
        )
    }

    /** 获取章节目录并入库（注：正文需单独下载）。 */
    suspend fun fetchChapterList(novel: Novel): List<ChapterItem> {
        val source = registry.getByName(novel.platform) ?: throw AppError.ParseError("未知平台")
        return source.chapterList(novel.url)
    }

    /** 加入书架。 */
    suspend fun addToBookshelf(novel: Novel) {
        novelDao.upsert(novel)
    }

    /** 从书架删除。 */
    suspend fun deleteFromBookshelf(novelId: String) {
        chapterDao.deleteByNovelId(novelId)
        novelDao.deleteById(novelId)
    }
}
