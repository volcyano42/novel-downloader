package com.noveldownloader.source

import com.noveldownloader.source.fanqie.FanqieSource
import com.noveldownloader.source.qidian.QidianSource
import com.noveldownloader.source.qimao.QimaoSource
import com.noveldownloader.source.xx92.Xs92Source
import javax.inject.Inject
import javax.inject.Singleton

/** 编译期注册所有书源，按 URL 匹配分发。 */
@Singleton
class SourceRegistry @Inject constructor(
    fanqieSource: FanqieSource,
    qidianSource: QidianSource,
    qimaoSource: QimaoSource,
    xs92Source: Xs92Source,
) {
    val all: List<NovelSource> = listOf(fanqieSource, qidianSource, qimaoSource, xs92Source)

    private val byName: Map<String, NovelSource> = all.associateBy { it.name }

    /** 根据 URL 返回匹配的书源，无匹配返回 null */
    fun resolve(url: String): NovelSource? = all.firstOrNull { it.matches(url) }

    /** 根据平台名返回书源 */
    fun getByName(name: String): NovelSource? = byName[name]

    /** 获取所有支持搜索的平台 */
    fun searchablePlatforms(): List<NovelSource> = all
}
