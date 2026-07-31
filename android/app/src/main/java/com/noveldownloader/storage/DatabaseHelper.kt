package com.noveldownloader.storage

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import com.noveldownloader.data.Chapter
import com.noveldownloader.data.Novel

class DatabaseHelper(context: Context) : SQLiteOpenHelper(context, "novels.db", null, 1) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""CREATE TABLE novels (
            novelId TEXT PRIMARY KEY, name TEXT, author TEXT, coverUrl TEXT,
            platform TEXT, url TEXT, description TEXT, totalChapters INTEGER DEFAULT 0,
            downloadedChapters INTEGER DEFAULT 0, status TEXT, createdAt INTEGER,
            updatedAt INTEGER)""")
        db.execSQL("""CREATE TABLE chapters (
            chapterId TEXT, novelId TEXT, title TEXT, url TEXT,
            orderNum INTEGER, content TEXT, isDownloaded INTEGER DEFAULT 0,
            PRIMARY KEY (novelId, chapterId))""")
    }
    override fun onUpgrade(db: SQLiteDatabase, old: Int, new: Int) {}

    fun allNovels(): List<Novel> {
        val list = mutableListOf<Novel>()
        readableDatabase.rawQuery("SELECT * FROM novels ORDER BY updatedAt DESC", null).use { c ->
            while (c.moveToNext()) list.add(Novel(
                novelId = c.getString(0), name = c.getString(1), author = c.getString(2),
                coverUrl = c.getString(3), platform = c.getString(4), url = c.getString(5),
                description = c.getString(6), totalChapters = c.getInt(7),
                downloadedChapters = c.getInt(8), status = c.getString(9),
                createdAt = c.getLong(10), updatedAt = c.getLong(11)))
        }
        return list
    }

    fun getNovel(novelId: String): Novel? {
        readableDatabase.rawQuery("SELECT * FROM novels WHERE novelId=?", arrayOf(novelId)).use { c ->
            if (c.moveToFirst()) return Novel(novelId = c.getString(0), name = c.getString(1),
                author = c.getString(2), coverUrl = c.getString(3), platform = c.getString(4),
                url = c.getString(5), description = c.getString(6), totalChapters = c.getInt(7),
                downloadedChapters = c.getInt(8), status = c.getString(9))
        }
        return null
    }

    fun upsertNovel(n: Novel) {
        val cv = ContentValues().apply {
            put("novelId", n.novelId); put("name", n.name); put("author", n.author)
            put("coverUrl", n.coverUrl); put("platform", n.platform); put("url", n.url)
            put("description", n.description); put("totalChapters", n.totalChapters)
            put("downloadedChapters", n.downloadedChapters); put("status", n.status)
            put("createdAt", n.createdAt); put("updatedAt", System.currentTimeMillis())
        }
        writableDatabase.insertWithOnConflict("novels", null, cv, SQLiteDatabase.CONFLICT_REPLACE)
    }

    fun deleteNovel(novelId: String) {
        writableDatabase.apply {
            delete("chapters", "novelId=?", arrayOf(novelId))
            delete("novels", "novelId=?", arrayOf(novelId))
        }
    }

    fun getChapters(novelId: String): List<Chapter> {
        val list = mutableListOf<Chapter>()
        readableDatabase.rawQuery("SELECT * FROM chapters WHERE novelId=? ORDER BY orderNum", arrayOf(novelId)).use { c ->
            while (c.moveToNext()) list.add(Chapter(
                chapterId = c.getString(0), novelId = c.getString(1), title = c.getString(2),
                url = c.getString(3), order = c.getInt(4), content = c.getString(5),
                isDownloaded = c.getInt(6) == 1))
        }
        return list
    }

    fun getChapter(novelId: String, chapterId: String): Chapter? {
        readableDatabase.rawQuery("SELECT * FROM chapters WHERE novelId=? AND chapterId=?", arrayOf(novelId, chapterId)).use { c ->
            if (c.moveToFirst()) return Chapter(chapterId = c.getString(0), novelId = c.getString(1),
                title = c.getString(2), url = c.getString(3), order = c.getInt(4),
                content = c.getString(5), isDownloaded = c.getInt(6) == 1)
        }
        return null
    }

    fun upsertChapters(chapters: List<Chapter>) {
        writableDatabase.use { db ->
            db.beginTransaction()
            try {
                chapters.forEach { ch ->
                    val cv = ContentValues().apply {
                        put("chapterId", ch.chapterId); put("novelId", ch.novelId)
                        put("title", ch.title); put("url", ch.url); put("orderNum", ch.order)
                        put("content", ch.content); put("isDownloaded", if (ch.isDownloaded) 1 else 0)
                    }
                    db.insertWithOnConflict("chapters", null, cv, SQLiteDatabase.CONFLICT_REPLACE)
                }
                db.setTransactionSuccessful()
            } finally { db.endTransaction() }
        }
    }

    fun updateChapterContent(novelId: String, chapterId: String, content: String) {
        val cv = ContentValues().apply { put("content", content); put("isDownloaded", 1) }
        writableDatabase.update("chapters", cv, "novelId=? AND chapterId=?", arrayOf(novelId, chapterId))
    }
}
