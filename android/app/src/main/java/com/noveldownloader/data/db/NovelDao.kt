package com.noveldownloader.data.db

import androidx.room.*
import com.noveldownloader.data.model.Novel
import kotlinx.coroutines.flow.Flow

@Dao
interface NovelDao {
    @Query("SELECT * FROM novels ORDER BY updatedAt DESC")
    fun getAll(): Flow<List<Novel>>

    @Query("SELECT * FROM novels WHERE novelId = :novelId")
    suspend fun getById(novelId: String): Novel?

    @Query("SELECT * FROM novels WHERE novelId = :novelId")
    fun getByIdFlow(novelId: String): Flow<Novel?>

    @Upsert
    suspend fun upsert(novel: Novel)

    @Query("UPDATE novels SET lastReadChapterIndex = :chapterIndex, lastReadLine = :line WHERE novelId = :novelId")
    suspend fun updateReadProgress(novelId: String, chapterIndex: Int, line: Int)

    @Query("DELETE FROM novels WHERE novelId = :novelId")
    suspend fun deleteById(novelId: String)
}
