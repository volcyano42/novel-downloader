package com.noveldownloader

import android.app.Activity
import android.os.Build
import android.os.Bundle
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient

class MainActivity : Activity() {
    private lateinit var server: WebServer

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Start HTTP server on port 8080
        server = WebServer(8080, applicationContext)
        try { server.start() } catch (_: Exception) {}

        // Fullscreen WebView
        val wv = WebView(this).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = true
            settings.setSupportZoom(false)
            // 不跟随系统暗色：关闭 WebView 算法暗色渲染（API 33+），前端默认亮色
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                settings.setForceDark(WebSettings.FORCE_DARK_OFF)
                settings.setAlgorithmicDarkeningAllowed(false)
            }
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String) {
                    // Hide any loading overlay
                }
            }
        }
        setContentView(wv)
        wv.loadUrl("http://localhost:8080/")
    }

    override fun onDestroy() {
        server.stop()
        super.onDestroy()
    }
}
