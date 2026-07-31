package com.noveldownloader.storage

import android.os.Environment
import java.io.File

/** 存储路径管理 — 文档目录下，卸载不丢。 */
object StoragePaths {
    val root: File by lazy {
        File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS), "novel-downloader")
    }

    val dataDir: File by lazy { File(root, "data").also { it.mkdirs() } }
    val cacheDir: File by lazy { File(root, "cache").also { it.mkdirs() } }
    val exportDir: File by lazy { File(root, "exports").also { it.mkdirs() } }

    fun init() {
        root.mkdirs()
        dataDir.mkdirs()
        cacheDir.mkdirs()
        exportDir.mkdirs()
    }
}
