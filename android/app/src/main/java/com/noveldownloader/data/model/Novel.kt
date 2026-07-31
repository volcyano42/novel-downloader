package com.noveldownloader.data.model

import androidx.room.Entity
import androidx.room.PrimaryKey

/** 书架上的小说。 */
@Entity(tableName = "novels")
data class Novel(
    @PrimaryKey val novelId: String,
    val name: String,
    val author: String,
    val coverUrl: String = "",
    val platform: String = "",
    val url: String = "",
    val description: String = "",
    val totalChapters: Int = 0,
    val downloadedChapters: Int = 0,
    val lastReadChapterIndex: Int = 0,
    val lastReadLine: Int = 0,
    val status: String = "",    // "completed" | "serial"
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis(),
)
