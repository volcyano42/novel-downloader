package com.noveldownloader.data.repository

import com.noveldownloader.engine.Downloader
import com.noveldownloader.util.DownloadProgress
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

/** 下载调度 + 进度管理。 */
@Singleton
class DownloadRepository @Inject constructor(
    private val downloader: Downloader,
) {
    private val downloadJobs = java.util.concurrent.ConcurrentHashMap<String, Job>()

    /** 开始下载，返回进度流。 */
    fun startDownload(novelId: String, scope: CoroutineScope): Flow<DownloadProgress> {
        val flow = downloader.download(novelId)
        scope.launch {
            flow.collect { progress ->
                if (progress.isFinished) {
                    downloadJobs.remove(novelId)
                }
            }
        }
        return flow
    }

    /** 暂停下载。 */
    fun pauseDownload(novelId: String) {
        downloadJobs[novelId]?.cancel()
        downloadJobs.remove(novelId)
    }
}
