package com.noveldownloader.data.model

/** 支持导出的格式。 */
enum class ExportFormat(val extension: String, val label: String) {
    TXT("txt", "TXT 纯文本"),
    EPUB("epub", "EPUB 电子书"),
}
