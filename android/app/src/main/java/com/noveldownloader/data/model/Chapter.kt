package com.noveldownloader.data.model

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

/** 章节 + 正文。 */
@Entity(
    tableName = "chapters",
    foreignKeys = [
        ForeignKey(
            entity = Novel::class,
            parentColumns = ["novelId"],
            childColumns = ["novelId"],
            onDelete = ForeignKey.CASCADE
        )
    ],
    indices = [Index("novelId"), Index("novelId", "order")]
)
data class Chapter(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val chapterId: String,
    val novelId: String,
    val title: String,
    val url: String = "",
    val order: Int = 0,
    val content: String? = null,
    val isDownloaded: Boolean = false,
)
