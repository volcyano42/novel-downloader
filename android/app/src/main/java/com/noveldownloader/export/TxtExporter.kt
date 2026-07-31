package com.noveldownloader.export

import com.noveldownloader.data.model.Chapter
import com.noveldownloader.data.model.ExportFormat
import com.noveldownloader.data.model.Novel

/** TXT 纯文本导出。 */
class TxtExporter : Exporter {
    override val format = ExportFormat.TXT

    override suspend fun export(novel: Novel, chapters: List<Chapter>): ByteArray {
        val sb = StringBuilder()
        sb.appendLine(novel.name)
        sb.appendLine("作者: ${novel.author}")
        sb.appendLine("=".repeat(50))
        sb.appendLine()

        chapters.filter { it.content != null }.forEach { chapter ->
            sb.appendLine(chapter.title)
            sb.appendLine("-".repeat(30))
            sb.appendLine(chapter.content)
            sb.appendLine()
            sb.appendLine()
        }
        return sb.toString().toByteArray(Charsets.UTF_8)
    }
}
