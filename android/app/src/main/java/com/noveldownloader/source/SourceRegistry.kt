package com.noveldownloader.source

import com.noveldownloader.engine.HttpEngine

class SourceRegistry(http: HttpEngine) {
    val all: List<NovelSource> = listOf(
        FanqieSource(http), QidianSource(http), QimaoSource(http), Xs92Source(http)
    )
    private val byName = all.associateBy { it.name }

    fun resolve(url: String): NovelSource? = all.firstOrNull { it.matches(url) }
    fun getByName(name: String): NovelSource? = byName[name]
}
