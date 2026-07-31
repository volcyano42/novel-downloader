package com.noveldownloader.engine

import kotlinx.coroutines.delay
import java.util.concurrent.ConcurrentHashMap

class RateLimiter {
    private val lastRequest = ConcurrentHashMap<String, Long>()

    suspend fun wait(key: String, minIntervalMs: Long = 1500) {
        val now = System.currentTimeMillis()
        val last = lastRequest[key] ?: 0L
        val elapsed = now - last
        if (elapsed < minIntervalMs) delay(minIntervalMs - elapsed)
        lastRequest[key] = System.currentTimeMillis()
    }
}
