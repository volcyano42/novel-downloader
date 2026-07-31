package com.noveldownloader.engine

import com.noveldownloader.util.AppError
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit
import javax.inject.Inject
import javax.inject.Singleton

/** HTTP 请求引擎 — OkHttp 封装。 */
@Singleton
class HttpEngine @Inject constructor() {
    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            val original = chain.request()
            val req = original.newBuilder()
                .header("User-Agent", ("Mozilla/5.0 (Linux; Android 13; OnePlus 11) " +
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"))
                .header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
                .header("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")
                .build()
            chain.proceed(req)
        }
        .build()

    /** GET 请求，返回 UTF-8 字符串。charset 非空时强制指定编码。 */
    suspend fun get(url: String, charset: String = "UTF-8"): String = withContext {
        val req = Request.Builder().url(url).get().build()
        val resp = client.newCall(req).await()
        if (!resp.isSuccessful) {
            throw AppError.NetworkError(url)
        }
        val body = resp.body?.bytes() ?: throw AppError.NetworkError(url)
        // 有 BOM 的 UTF-8 需要跳过前3字节
        val offset = if (body.size >= 3 && body[0] == 0xEF.toByte() && body[1] == 0xBB.toByte() && body[2] == 0xBF.toByte()) 3 else 0
        body.toString(charset(charset), offset, body.size - offset)
    }

    /** POST JSON，返回响应字符串。 */
    suspend fun postJson(url: String, json: String): String = withContext {
        val mediaType = "application/json; charset=utf-8".toMediaType()
        val req = Request.Builder()
            .url(url)
            .post(json.toRequestBody(mediaType))
            .build()
        val resp = client.newCall(req).await()
        if (!resp.isSuccessful) throw AppError.NetworkError(url)
        resp.body?.string() ?: throw AppError.NetworkError(url)
    }
}

/** 桥接 OkHttp 回调到协程。 */
private suspend fun <T> withContext(block: suspend () -> T): T {
    return kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) { block() }
}

private suspend fun okhttp3.Call.await(): okhttp3.Response {
    return kotlinx.coroutines.suspendCancellableCoroutine { cont ->
        enqueue(object : okhttp3.Callback {
            override fun onResponse(call: okhttp3.Call, response: okhttp3.Response) {
                cont.resume(response)
            }
            override fun onFailure(call: okhttp3.Call, e: java.io.IOException) {
                cont.resumeWithException(e)
            }
        })
        cont.invokeOnCancellation { cancel() }
    }
}
