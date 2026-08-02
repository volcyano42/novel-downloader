package com.novel.downloader

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
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
            if (checkHealth()) {
                webView.loadUrl("$BASE/")
            } else {
                mainHandler.postDelayed(this, HEALTH_POLL_MS)
            }
        }
    }
    private var pollStart = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setupWebView()
        ServerService.start(this)
        requestStoragePermissionIfNeeded()
        pollStart = System.currentTimeMillis()
        mainHandler.post(healthPoll)
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
        } else if (Build.VERSION.SDK_INT >= 29) {
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
