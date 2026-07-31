package com.noveldownloader.export

import com.noveldownloader.data.model.Chapter
import com.noveldownloader.data.model.ExportFormat
import com.noveldownloader.data.model.Novel
import java.io.ByteArrayOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/** EPUB 3 电子书导出。 */
class EpubExporter : Exporter {
    override val format = ExportFormat.EPUB

    override suspend fun export(novel: Novel, chapters: List<Chapter>): ByteArray {
        val baos = ByteArrayOutputStream()
        val zip = ZipOutputStream(baos)

        // mimetype（必须不压缩，第一个 entry）
        val mimetype = ZipEntry("mimetype").apply {
            method = ZipEntry.STORED
            size = 20
            crc = 0x2CAB616F
        }
        zip.putNextEntry(mimetype)
        zip.write("application/epub+zip".toByteArray())
        zip.closeEntry()

        // META-INF/container.xml
        zip.putNextEntry(ZipEntry("META-INF/container.xml"))
        zip.write(
            """<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>"""
                .toByteArray()
        )
        zip.closeEntry()

        // 过滤有正文的章节
        val filledChapters = chapters.filter { it.content != null }

        // content.opf
        val manifest = StringBuilder()
        val spine = StringBuilder()
        filledChapters.forEachIndexed { i, _ ->
            val id = "chapter_$i"
            val href = "chapter_$i.xhtml"
            manifest.append("""<item id="$id" href="$href" media-type="application/xhtml+xml"/>""")
            spine.append("""<itemref idref="$id"/>""")
        }

        val opf = """<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" unique-identifier="book-id" xmlns="http://www.idpf.org/2007/opf">
  <metadata>
    <dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">${escapeXml(novel.name)}</dc:title>
    <dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">${escapeXml(novel.author)}</dc:creator>
    <dc:language xmlns:dc="http://purl.org/dc/elements/1.1/">zh-CN</dc:language>
    <dc:identifier id="book-id" xmlns:dc="http://purl.org/dc/elements/1.1/">${novel.novelId}</dc:identifier>
  </metadata>
  <manifest>
    $manifest
  </manifest>
  <spine>
    $spine
  </spine>
</package>"""
        zip.putNextEntry(ZipEntry("content.opf"))
        zip.write(opf.toByteArray(Charsets.UTF_8))
        zip.closeEntry()

        // 章节 HTML
        filledChapters.forEachIndexed { i, ch ->
            val html = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>${escapeXml(ch.title)}</title></head>
<body><h2>${escapeXml(ch.title)}</h2>
${ch.content!!.replace("\n", "<br/>\n")}
</body></html>"""
            zip.putNextEntry(ZipEntry("chapter_$i.xhtml"))
            zip.write(html.toByteArray(Charsets.UTF_8))
            zip.closeEntry()
        }

        zip.close()
        return baos.toByteArray()
    }

    private fun escapeXml(s: String): String = s
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
}
