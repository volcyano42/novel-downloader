package com.novel.downloader

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.provider.Settings
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : AppCompatActivity() {

    companion object {
        private const val BASE = "http://127.0.0.1:18080"
        private const val HEALTH_TIMEOUT_MS = 15_000L
        private const val HEALTH_POLL_MS = 500L
        private const val REQ_MANAGE_STORAGE = 2001
        private const val REQ_WRITE_STORAGE = 2002
    }

    private lateinit var webView: WebView
    private val mainHandler = Handler(Looper.getMainLooper())
    private val healthPoll = object : Runnable {
        override fun run() {
            // 同步 HTTP 健康检查放后台线程，避免阻塞主线程（最坏 2s）
            Thread {
                val healthy = checkHealth()
                mainHandler.post {
                    if (isDestroyed || isFinishing) return@post
                    if (healthy) {
                        webView.loadUrl("$BASE/")
                    } else if (SystemClock.elapsedRealtime() - pollStart > HEALTH_TIMEOUT_MS) {
                        Toast.makeText(this@MainActivity, R.string.backend_not_ready, Toast.LENGTH_LONG).show()
                    } else {
                        mainHandler.postDelayed(healthPoll, HEALTH_POLL_MS)
                    }
                }
            }.start()
        }
    }
    private var pollStart = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setupWebView()
        ServerService.start(this)
        requestStoragePermissionIfNeeded()
        pollStart = SystemClock.elapsedRealtime()
        scheduleHealthPoll()
    }

    /** 重启健康轮询：先取消排队的回调再 post，避免重复调度导致并行轮询。 */
    private fun scheduleHealthPoll() {
        mainHandler.removeCallbacks(healthPoll)
        mainHandler.post(healthPoll)
    }

    override fun onResume() {
        super.onResume()
        // 从 MANAGE_EXTERNAL_STORAGE 设置页返回后复查授权，已授权则重启后端服务与轮询
        if (Build.VERSION.SDK_INT >= 30 && EnvironmentCompat.hasAllFilesAccess()) {
            ServerService.start(this)
            pollStart = SystemClock.elapsedRealtime()
            scheduleHealthPoll()
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQ_WRITE_STORAGE && grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            ServerService.start(this)
            pollStart = SystemClock.elapsedRealtime()
            scheduleHealthPoll()
        }
    }

    private fun setupWebView() {
        webView = WebView(this)
        setContentView(webView)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            setSupportZoom(false)
        }
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView?, url: String?): Boolean {
                // 全部留在 WebView 内（本地 localhost）
                return false
            }
        }
        webView.addJavascriptInterface(AndroidBridge(this), AndroidBridge.NAME)
    }

    private fun checkHealth(): Boolean = try {
        val conn = URL("$BASE/api/v2/health").openConnection() as HttpURLConnection
        conn.connectTimeout = 1_000
        conn.readTimeout = 1_000
        conn.responseCode == 200
    } catch (_: Exception) {
        false
    }

    private fun requestStoragePermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= 30) {
            if (!EnvironmentCompat.hasAllFilesAccess()) {
                AlertDialog.Builder(this)
                    .setMessage(R.string.storage_permission_guide)
                    .setPositiveButton("去授权") { _, _ ->
                        startActivityForResult(
                            Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                                Uri.parse("package:$packageName")),
                            REQ_MANAGE_STORAGE
                        )
                    }
                    .setNegativeButton("稍后", null)
                    .show()
            }
        } else if (Build.VERSION.SDK_INT >= 23) {
            // API 23-28 请求 WRITE；API 21-22 自动授予存储权限，无需请求
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE)
                != PackageManager.PERMISSION_GRANTED
            ) {
                ActivityCompat.requestPermissions(
                    this,
                    arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE),
                    REQ_WRITE_STORAGE
                )
            }
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        mainHandler.removeCallbacks(healthPoll)
        ServerService.stop(this)
        webView.destroy()
    }
}
