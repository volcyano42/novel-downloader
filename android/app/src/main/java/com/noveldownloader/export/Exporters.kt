package com.noveldownloader.export

import com.noveldownloader.data.Chapter
import com.noveldownloader.data.Novel

object TxtExporter {
    fun export(novel: Novel, chapters: List<Chapter>): ByteArray {
        val sb = StringBuilder()
        sb.appendLine(novel.name).appendLine("作者: ${novel.author}").appendLine("=".repeat(50)).appendLine()
        chapters.filter { it.content != null }.forEach { ch ->
            sb.appendLine(ch.title).appendLine("-".repeat(30)).appendLine(ch.content).appendLine().appendLine()
        }
        return sb.toString().toByteArray(Charsets.UTF_8)
    }
}

object EpubExporter {
    fun export(novel: Novel, chapters: List<Chapter>): ByteArray {
        val baos = java.io.ByteArrayOutputStream()
        val zip = java.util.zip.ZipOutputStream(baos)
        val filled = chapters.filter { it.content != null }

        val mimetype = java.util.zip.ZipEntry("mimetype")
        mimetype.method = java.util.zip.ZipEntry.STORED; mimetype.size = 20; mimetype.crc = 0x2CAB616F
        zip.putNextEntry(mimetype); zip.write("application/epub+zip".toByteArray()); zip.closeEntry()

        zip.putNextEntry(java.util.zip.ZipEntry("META-INF/container.xml"))
        zip.write("""<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>""".toByteArray())
        zip.closeEntry()

        val manifest = StringBuilder(); val spine = StringBuilder()
        filled.forEachIndexed { i, _ ->
            manifest.append("""<item id="chapter_$i" href="chapter_$i.xhtml" media-type="application/xhtml+xml"/>""")
            spine.append("""<itemref idref="chapter_$i"/>""")
        }
        val opf = """<?xml version="1.0"?><package version="3.0" unique-identifier="book-id" xmlns="http://www.idpf.org/2007/opf"><metadata><dc:title xmlns:dc="http://purl.org/dc/elements/1.1/">${esc(novel.name)}</dc:title><dc:creator xmlns:dc="http://purl.org/dc/elements/1.1/">${esc(novel.author)}</dc:creator><dc:language xmlns:dc="http://purl.org/dc/elements/1.1/">zh-CN</dc:language></metadata><manifest>$manifest</manifest><spine>$spine</spine></package>"""
        zip.putNextEntry(java.util.zip.ZipEntry("content.opf"))
        zip.write(opf.toByteArray(Charsets.UTF_8)); zip.closeEntry()

        filled.forEachIndexed { i, ch ->
            val html = """<?xml version="1.0"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml"><head><title>${esc(ch.title)}</title></head><body><h2>${esc(ch.title)}</h2>${ch.content!!.replace("\n", "<br/>\n")}</body></html>"""
            zip.putNextEntry(java.util.zip.ZipEntry("chapter_$i.xhtml"))
            zip.write(html.toByteArray(Charsets.UTF_8)); zip.closeEntry()
        }
        zip.close()
        return baos.toByteArray()
    }

    private fun esc(s: String) = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")
}
