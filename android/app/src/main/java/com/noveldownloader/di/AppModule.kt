package com.noveldownloader.di

import android.content.Context
import androidx.room.Room
import com.noveldownloader.data.db.AppDatabase
import com.noveldownloader.data.db.ChapterDao
import com.noveldownloader.data.db.NovelDao
import com.noveldownloader.storage.StoragePaths
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {
    @Provides
    @Singleton
    fun provideAppDatabase(@ApplicationContext ctx: Context): AppDatabase {
        StoragePaths.init()
        return Room.databaseBuilder(
            ctx,
            AppDatabase::class.java,
            StoragePaths.dataDir.resolve("novels.db").absolutePath,
        ).build()
    }

    @Provides
    fun provideNovelDao(db: AppDatabase): NovelDao = db.novelDao()

    @Provides
    fun provideChapterDao(db: AppDatabase): ChapterDao = db.chapterDao()
}
