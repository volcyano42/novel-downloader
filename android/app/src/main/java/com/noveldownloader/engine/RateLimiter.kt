package com.noveldownloader.engine

import kotlinx.coroutines.delay
import javax.inject.Inject
import javax.inject.Singleton

/** 请求间隔控制，防止触发反爬。 */
@Singleton
class RateLimiter @Inject constructor() {
    private val lastRequest = java.util.concurrent.ConcurrentHashMap<String, Long>()

    /** 等待指定毫秒数（距上次请求），默认 1500ms */
    suspend fun wait(key: String, minIntervalMs: Long = 1500) {
        val now = System.currentTimeMillis()
        val last = lastRequest[key] ?: 0L
        val elapsed = now - last
        if (elapsed < minIntervalMs) {
            delay(minIntervalMs - elapsed)
        }
        lastRequest[key] = System.currentTimeMillis()
    }
}
