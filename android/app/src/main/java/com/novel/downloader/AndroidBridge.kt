package com.novel.downloader

import android.content.Intent
import android.net.Uri
import android.webkit.JavascriptInterface
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import java.net.HttpURLConnection
import java.net.URL

class AndroidBridge(private val activity: ComponentActivity) {

    companion object {
        const val NAME = "AndroidBridge"
        private const val BASE = "http://127.0.0.1:18080"
    }

    private var pendingTaskId: String? = null
    private var pendingFileName: String? = null

    private val saveFileLauncher =
        activity.registerForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
            uri?.let { onSaveResult(it) }
        }

    @JavascriptInterface
    fun saveExport(taskId: String, fileName: String) {
        pendingTaskId = taskId
        pendingFileName = fileName
        saveFileLauncher.launch(fileName)
    }

    private fun onSaveResult(uri: Uri) {
        val taskId = pendingTaskId ?: return
        val fileName = pendingFileName ?: return
        Thread {
            try {
                val conn = URL("$BASE/api/v2/export/download/$taskId").openConnection() as HttpURLConnection
                conn.connectTimeout = 30_000
                conn.readTimeout = 30_000
                conn.inputStream.use { input ->
                    activity.contentResolver.openOutputStream(uri)?.use { output ->
                        input.copyTo(output)
                    }
                }
                activity.runOnUiThread {
                    Toast.makeText(activity, "导出完成：$fileName", Toast.LENGTH_LONG).show()
                }
            } catch (e: Exception) {
                activity.runOnUiThread {
                    Toast.makeText(activity, "导出失败：${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }
}
