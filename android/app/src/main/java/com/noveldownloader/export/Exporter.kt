package com.noveldownloader.export

import com.noveldownloader.data.model.Chapter
import com.noveldownloader.data.model.ExportFormat
import com.noveldownloader.data.model.Novel

/** 导出器接口。 */
interface Exporter {
    val format: ExportFormat
    suspend fun export(novel: Novel, chapters: List<Chapter>): ByteArray
}
