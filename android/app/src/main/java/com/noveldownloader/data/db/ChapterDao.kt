package com.noveldownloader.data.db

import androidx.room.*
import com.noveldownloader.data.model.Chapter
import kotlinx.coroutines.flow.Flow

@Dao
interface ChapterDao {
    @Query("SELECT * FROM chapters WHERE novelId = :novelId ORDER BY `order` ASC")
    fun getByNovelId(novelId: String): Flow<List<Chapter>>

    @Query("SELECT * FROM chapters WHERE novelId = :novelId ORDER BY `order` ASC")
    suspend fun getByNovelIdSync(novelId: String): List<Chapter>

    @Query("SELECT * FROM chapters WHERE novelId = :novelId AND `order` = :order LIMIT 1")
    suspend fun getByNovelAndOrder(novelId: String, order: Int): Chapter?

    @Upsert
    suspend fun upsertAll(chapters: List<Chapter>)

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(chapter: Chapter)

    @Query("UPDATE chapters SET content = :content, isDownloaded = 1 WHERE chapterId = :chapterId")
    suspend fun updateContent(chapterId: String, content: String)

    @Query("SELECT COUNT(*) FROM chapters WHERE novelId = :novelId AND isDownloaded = 1")
    suspend fun downloadedCount(novelId: String): Int

    @Query("DELETE FROM chapters WHERE novelId = :novelId")
    suspend fun deleteByNovelId(novelId: String)

    @Query("SELECT COUNT(*) FROM chapters WHERE novelId = :novelId")
    suspend fun countByNovelId(novelId: String): Int
}
