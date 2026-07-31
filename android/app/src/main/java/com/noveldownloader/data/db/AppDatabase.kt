package com.noveldownloader.data.db

import androidx.room.Database
import androidx.room.RoomDatabase
import com.noveldownloader.data.model.Chapter
import com.noveldownloader.data.model.Novel

@Database(
    entities = [Novel::class, Chapter::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun novelDao(): NovelDao
    abstract fun chapterDao(): ChapterDao
}
