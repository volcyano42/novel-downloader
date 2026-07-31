package com.noveldownloader.engine

import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlin.coroutines.suspendCoroutine

class HttpEngine {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            chain.proceed(chain.request().newBuilder()
                .header("User-Agent", "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36")
                .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
                .header("Accept-Language", "zh-CN,zh;q=0.9")
                .build())
        }
        .build()

    suspend fun get(url: String, charset: String = "UTF-8"): String {
        val req = Request.Builder().url(url).get().build()
        val resp = suspendCoroutine<Response> { cont ->
            client.newCall(req).enqueue(object : Callback {
                override fun onResponse(call: Call, response: Response) = cont.resume(response)
                override fun onFailure(call: Call, e: java.io.IOException) = cont.resumeWithException(e)
            })
        }
        resp.use { r ->
            if (!r.isSuccessful) throw RuntimeException("HTTP ${r.code}: $url")
            val body = r.body?.bytes() ?: throw RuntimeException("empty body: $url")
            val offset = if (body.size >= 3 && body[0] == 0xEF.toByte() && body[1] == 0xBB.toByte() && body[2] == 0xBF.toByte()) 3 else 0
            String(body, offset, body.size - offset, charset(charset))
        }
    }

    suspend fun postJson(url: String, json: String): String {
        val req = Request.Builder().url(url)
            .post(json.toRequestBody("application/json; charset=utf-8".toMediaType()))
            .build()
        val resp = suspendCoroutine<Response> { cont ->
            client.newCall(req).enqueue(object : Callback {
                override fun onResponse(call: Call, response: Response) = cont.resume(response)
                override fun onFailure(call: Call, e: java.io.IOException) = cont.resumeWithException(e)
            })
        }
        resp.use { r ->
            if (!r.isSuccessful) throw RuntimeException("HTTP ${r.code}: $url")
            r.body?.string() ?: throw RuntimeException("empty body: $url")
        }
    }
}
