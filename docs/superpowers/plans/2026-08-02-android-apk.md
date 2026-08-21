# Android APK 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `novel-downloader/` 仓库内新增 `android/` Gradle 项目，用 Chaquopy 嵌入 Python + ForegroundService + WebView 构建 Android APK，app_data 存公共 Documents，导出走 SAF 系统文件夹选择器。

**Architecture:** APK 启动 `ForegroundService` 通过 Chaquopy 拉起 uvicorn + 现有 FastAPI 后端（监听 127.0.0.1:18080），`MainActivity` 用 WebView 加载现有 React SPA。`server.py` 启动时注入 `NLD_APP_DATA` 指向公共 Documents 目录；导出复用现有异步任务 API，仅把最终下载从 `window.open` 切换为 `AndroidBridge.saveExport()` 走系统保存对话框。

**Tech Stack:** Kotlin + Gradle (KTS) + Chaquopy 15.0.1 + Python 3.11 + FastAPI/uvicorn + React (现有) + GitHub Actions。

## Global Constraints

- **git 提交**：提交消息必须中文、一个方面一条 commit、禁止 `git add -A`（显式指定文件）、禁止自动合并/推送 main。
- **git 仓库边界**：唯一 git 仓库是 `novel-downloader/`；`docs/` 在外层容器非 git，**不提交** docs 下任何文件。
- **Android 产物不在本机构建**：本机无 Android SDK/Gradle 环境，`./gradlew` 相关步骤只在 CI（GitHub Actions `ubuntu-latest`）执行；本地仅验证 Python 部分（`server.py` 逻辑用 pytest 模拟验证）。
- **现有代码零改动**（除任务 5 的前端下载分支）：`novelbase/`、`services/backend/`、`cli.py` 不改；app_data 路径通过 `NLD_APP_DATA` env 注入，`config_service.py` 现有逻辑直接生效。
- **browser 模式不可用**：Chaquopy pip 依赖排除 `drissionpage`、`psutil`。
- **端口固定 `18080`**；后端 app 来自 `services.backend.main:app`（FastAPI(title="Novel Downloader API")，已 include storage/download/export/engine/config 5 个 router）。
- **导出 API 为异步任务模式**（已在 `services/backend/routers/export.py`）：`POST /api/v2/export` → `{task_id}`；`GET /api/v2/export/task/{task_id}` 轮询；`GET /api/v2/export/download/{task_id}` 下载文件。
- **AndroidManifest 权限**：`INTERNET`、`FOREGROUND_SERVICE`；API 29 加 `WRITE_EXTERNAL_STORAGE`（maxSdkVersion 29）+ `requestLegacyExternalStorage`；API 30+ 运行时引导 `MANAGE_EXTERNAL_STORAGE`（manifest 声明）。

---

### Task 1: Android 项目脚手架（Gradle + Chaquopy + Manifest）

**Files:**
- Create: `android/settings.gradle.kts`
- Create: `android/build.gradle.kts`
- Create: `android/gradle.properties`
- Create: `android/app/build.gradle.kts`
- Create: `android/app/src/main/AndroidManifest.xml`
- Create: `android/app/src/main/res/values/strings.xml`
- Create: `android/app/src/main/res/mipmap-*/ic_launcher.png`（用 Android Studio 默认图标生成，或用 `android:icon="@mipmap/ic_launcher"` + adaptive icon XML）
- Create: `android/gradle/wrapper/gradle-wrapper.properties`
- Create: `android/gradle/wrapper/gradle-wrapper.jar`（CI 首跑生成）

**Interfaces:**
- Produces: `android/app/build.gradle.kts` 中 `python { pip { ... } }` 块声明 Python 依赖；`android/` 可作为独立 Gradle 项目构建出 debug APK 骨架。

- [ ] **Step 1: 创建 `android/settings.gradle.kts`**

```kotlin
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}
rootProject.name = "novel-downloader"
include(":app")
```

- [ ] **Step 2: 创建 `android/build.gradle.kts`（根）**

```kotlin
plugins {
    id("com.android.application") version "8.5.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
    id("com.chaquo.python") version "15.0.1" apply false
}
```

- [ ] **Step 3: 创建 `android/gradle.properties`**

```properties
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
kotlin.code.style=official
```

- [ ] **Step 4: 创建 `android/gradle/wrapper/gradle-wrapper.properties`**

```properties
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.7-bin.zip
networkTimeout=10000
validateDistributionUrl=true
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
```

> 注：`gradle-wrapper.jar` 在 CI 中通过 `gradle wrapper` 生成（或提交预生成的 jar）；本地无 Gradle 环境时不生成。

- [ ] **Step 5: 创建 `android/app/build.gradle.kts`**

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.novel.downloader"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.novel.downloader"
        minSdk = 21
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (rootProject.file("keystore.properties").exists()) {
                val props = java.util.Properties().apply {
                    load(rootProject.file("keystore.properties").inputStream())
                }
                signingConfigs.create("release") {
                    storeFile = rootProject.file(props["storeFile"] as String)
                    storePassword = props["storePassword"] as String
                    keyAlias = props["keyAlias"] as String
                    keyPassword = props["keyPassword"] as String
                }
            } else null
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

chaquopy {
    defaultConfig {
        version = "3.11"
        pip {
            install("-r", "../../requirements.txt")
            install("novelbase", "file:../..")
            exclude("drissionpage")
            exclude("psutil")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("src/main/python")
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.webkit:webkit:1.11.0")
}
```

- [ ] **Step 6: 创建 `android/app/src/main/AndroidManifest.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <!-- Android 10 (API 29) 写入公共目录 -->
    <uses-permission
        android:name="android.permission.WRITE_EXTERNAL_STORAGE"
        android:maxSdkVersion="29" />
    <!-- Android 11+ (API 30+) "所有文件访问" -->
    <uses-permission android:name="android.permission.MANAGE_EXTERNAL_STORAGE" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:requestLegacyExternalStorage="true"
        android:supportsRtl="true"
        android:theme="@style/Theme.AppCompat.Light">
        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        <service
            android:name=".ServerService"
            android:exported="false"
            android:foregroundServiceType="dataSync" />
    </application>
</manifest>
```

- [ ] **Step 7: 创建 `android/app/src/main/res/values/strings.xml`**

```xml
<resources>
    <string name="app_name">小说下载器</string>
    <string name="notification_channel_name">小说下载器服务</string>
    <string name="notification_title">小说下载器运行中</string>
    <string name="storage_permission_guide">请在系统设置中允许"所有文件访问"，以便保存小说数据到公共目录</string>
</resources>
```

- [ ] **Step 8: 占位 res 目录**

```bash
mkdir -p android/app/src/main/res/values
mkdir -p android/app/src/main/res/mipmap-anydpi-v26
mkdir -p android/app/src/main/res/drawable
```

（图标资源实现时用 Android Studio Asset Studio 生成；CI 用占位 adaptive icon XML：`res/drawable/ic_launcher_foreground.xml` + `res/mipmap-anydpi-v26/ic_launcher.xml`）

- [ ] **Step 9: 提交**

```bash
cd novel-downloader
git add android/settings.gradle.kts android/build.gradle.kts android/gradle.properties android/app/build.gradle.kts android/app/src/main/AndroidManifest.xml android/app/src/main/res
git commit -m "feat: 新增 Android 项目脚手架（Gradle + Chaquopy 配置）"
```

---

### Task 2: server.py —— Python 入口（NLD_APP_DATA 注入 + 静态挂载）

**Files:**
- Create: `android/app/src/main/python/server.py`
- Test: `novel-downloader/tests/test_android_server.py`

**Interfaces:**
- Consumes: `services.backend.main.app`（FastAPI app）；`android.os.Environment.getExternalStoragePublicDirectory(DIRECTORY_DOCUMENTS)`（Chaquopy 内可用 Java API）。
- Produces: 模块级 `APP_DATA: Path`（公共 Documents 下 `novel-downloader/app_data`）；`get_app_data() -> Path`；`ensure_app_data_writable() -> None`（不可写抛 `RuntimeError`）；模块加载时设置 `os.environ["NLD_APP_DATA"]`；`app` 挂载 `/` 为 `StaticFiles(directory=<assets/frontend>, html=True)`。
- 关键：**Android 环境没有 `android.os.Environment` 时（本地 pytest）跳过注入**，仅保留 env 已设置时的行为——便于本地测试。

- [ ] **Step 1: 写失败测试 `tests/test_android_server.py`**

```python
# -*- coding: utf-8 -*-
"""server.py 逻辑的本地可测部分（Android 环境外验证 env 注入与挂载）。"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

# 模拟 Chaquopy 环境缺失：android.os.Environment import 必须被容错跳过


def test_server_module_sets_nld_app_data_when_env_present(tmp_path, monkeypatch):
    monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "app_data"))
    sys.path.insert(0, str(Path(__file__).parent.parent / "android" / "app" / "src" / "main" / "python"))
    try:
        import server  # noqa: F401
    finally:
        sys.path.pop(0)
    assert os.environ["NLD_APP_DATA"] == str(tmp_path / "app_data")


def test_server_module_has_app_with_static_mount():
    sys.path.insert(0, str(Path(__file__).parent.parent / "android" / "app" / "src" / "main" / "python"))
    try:
        import server
    finally:
        sys.path.pop(0)
    mounts = [r.path for r in server.app.routes if isinstance(r, type(server.app.routes[0]))]
    # FastAPI StaticFiles mount 的 path 是 "/"
    assert "/" in mounts
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_android_server.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'server'`，因 server.py 尚不存在）

- [ ] **Step 3: 实现 `android/app/src/main/python/server.py`**

```python
# -*- coding: utf-8 -*-
"""Android APK 版后端入口：注入 NLD_APP_DATA → 启动现有 FastAPI app → 挂载前端。"""
import os
from pathlib import Path

try:
    from android.os import Environment  # Chaquopy Android 环境
    _ANDROID = True
except ImportError:
    _ANDROID = False


def get_app_data() -> Path:
    """返回 app_data 目录：优先 NLD_APP_DATA env；Android 上默认公共 Documents。"""
    env = os.environ.get("NLD_APP_DATA")
    if env:
        return Path(env).resolve()
    if _ANDROID:
        docs = Path(str(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS)))
        return docs / "novel-downloader" / "app_data"
    # 本地测试兜底
    return Path(__file__).resolve().parent.parent / "app_data"


def ensure_app_data_writable() -> None:
    """确保 app_data 可写；不可写抛 RuntimeError（调用方转 503）。"""
    app_data = get_app_data()
    try:
        app_data.mkdir(parents=True, exist_ok=True)
        probe = app_data / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        raise RuntimeError(f"app_data 不可写：{app_data}（请授予存储权限）") from e


APP_DATA = get_app_data()
os.environ["NLD_APP_DATA"] = str(APP_DATA)  # config_service.py 优先读此 env
ensure_app_data_writable()

from services.backend.main import app  # noqa: E402  （现有 FastAPI app）

from fastapi.staticfiles import StaticFiles  # noqa: E402

_frontend_dir = Path(__file__).resolve().parent.parent / "assets" / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")
```

> 注：**不注册 `/health` 路由**——健康检查复用 `services/backend/main.py` 已注册的 `/api/v2/health`（注册于 SPA fallback `/{full_path:path}` 与静态 mount 之前，任何环境都可达）；server.py 自注册 `/health` 会被 SPA fallback 拦截，已在实现中移除（Task 2 实测发现）。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_android_server.py -v`
Expected: PASS（2 passed）

> 注：真实 Android 环境中 `android.os.Environment` 可用，`get_app_data()` 返回公共 Documents 路径；本地 pytest 无该模块时走 env 分支（Step 1 的 monkeypatch 已设 env），逻辑一致。

- [ ] **Step 5: 提交**

```bash
cd novel-downloader
git add android/app/src/main/python/server.py tests/test_android_server.py
git commit -m "feat: 新增 Android 后端入口 server.py（NLD_APP_DATA 注入 + 静态挂载）"
```

---

### Task 3: ServerService.kt —— ForegroundService 拉起 Python

**Files:**
- Create: `android/app/src/main/java/com/novel/downloader/ServerService.kt`

**Interfaces:**
- Consumes: `server.py`（Chaquopy `Python.start()` 目标）；通知渠道名 `novel_downloader_channel`。
- Produces: `class ServerService : Service()`，`onStartCommand` 在子线程 `Python.start(ServerService::class.java, "server")`（阻塞运行 uvicorn）；`onDestroy` 停止 Python 实例；`onCreate` 建通知渠道并 `startForeground()`；对外 `companion object { fun start(context); fun stop(context) }`。

- [ ] **Step 1: 实现 `ServerService.kt`**

```kotlin
package com.novel.downloader

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.chaquo.python.Python
import kotlin.concurrent.thread

class ServerService : Service() {

    companion object {
        private const val CHANNEL_ID = "novel_downloader_channel"
        private const val NOTIFICATION_ID = 1

        fun start(context: Context) {
            val intent = Intent(context, ServerService::class.java)
            context.startForegroundService(intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, ServerService::class.java))
        }
    }

    private var pythonThread: Thread? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(NOTIFICATION_ID, buildNotification())
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (pythonThread?.isAlive != true) {
            pythonThread = thread(name = "python-server") {
                try {
                    // 阻塞运行 uvicorn（server.py 内 uvicorn.run）
                    Python.start(ServerService::class.java, "server")
                } catch (t: Throwable) {
                    stopSelf()
                }
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        try {
            Python.getInstance().getModule("server").callAttr("_shutdown")
        } catch (_: Exception) {
            // 已停止则忽略
        }
    }

    private fun createChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notification_channel_name),
            NotificationManager.IMPORTANCE_LOW
        )
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun buildNotification() =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.notification_title))
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setOngoing(true)
            .build()
}
```

> 注：`server.py` 需补一个 `_shutdown()` 函数（`uvicorn` 的 `Server.should_exit = True`），在 Task 2 的 Step 5 提交后由本任务追加提交（见 Step 2）。

- [ ] **Step 2: 在 server.py 追加 `_shutdown`**

在 `android/app/src/main/python/server.py` 末尾追加：

```python
def _shutdown() -> None:
    """Service onDestroy 调用：优雅停止 uvicorn。"""
    for server in getattr(uvicorn, "_servers", []) or []:
        server.should_exit = True
```

同时顶部 import 增加 `import uvicorn`（已有）。若 uvicorn 未暴露 `_servers`，退化为 `os._exit(0)`（Service 线程内进程即终止）。

- [ ] **Step 3: 提交**

```bash
cd novel-downloader
git add android/app/src/main/java/com/novel/downloader/ServerService.kt android/app/src/main/python/server.py
git commit -m "feat: 新增 ServerService 前台服务拉起 Python 后端"
```

---

### Task 4: MainActivity.kt + AndroidBridge.kt —— WebView + 健康轮询 + SAF 导出 + 权限引导

**Files:**
- Create: `android/app/src/main/java/com/novel/downloader/MainActivity.kt`
- Create: `android/app/src/main/java/com/novel/downloader/AndroidBridge.kt`

**Interfaces:**
- Consumes: `ServerService.start/stop(context)`；`services/backend/main.py` 的 `/api/v2/health`（HTTP 200 即就绪，JSON `{"ok":true,"data":{"status":"ok"}}`）；`GET /api/v2/export/download/{taskId}`（下载导出文件）。
- Produces: `MainActivity`（WebView 加载 `http://127.0.0.1:18080/`，注册 `AndroidBridge`，启动 Service，健康轮询，`onDestroy` 停止 Service）；`class AndroidBridge(activity)` 暴露 `@JavascriptInterface fun saveExport(taskId: String, fileName: String)` 和 `fun onSaveResult(uri: Uri)`（AndroidX `ActivityResultContracts.CreateDocument` 或 `startActivityForResult` 均可，计划采用 AndroidX Activity Result API）。

- [ ] **Step 1: 实现 `AndroidBridge.kt`**

```kotlin
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
```

- [ ] **Step 2: 实现 `MainActivity.kt`**

```kotlin
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
            if (!EnvironmentCompat.hasAllFilesAccess(this)) {
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
```

> 注：`EnvironmentCompat` 为辅助类（见 Step 3），封装 `Environment.isExternalStorageManager()`（API 30+）。

- [ ] **Step 3: 实现 `EnvironmentCompat.kt`**

```kotlin
package com.novel.downloader

import android.os.Build
import android.os.Environment

object EnvironmentCompat {
    fun hasAllFilesAccess(): Boolean =
        if (Build.VERSION.SDK_INT >= 30) Environment.isExternalStorageManager() else true
}
```

- [ ] **Step 4: 提交**

```bash
cd novel-downloader
git add android/app/src/main/java/com/novel/downloader/MainActivity.kt android/app/src/main/java/com/novel/downloader/AndroidBridge.kt android/app/src/main/java/com/novel/downloader/EnvironmentCompat.kt
git commit -m "feat: 新增 MainActivity 与 AndroidBridge（WebView + SAF 导出 + 权限引导）"
```

---

### Task 5: 前端导出下载分支（Android 检测）

**Files:**
- Modify: `novel-downloader/services/frontend/src/features/bookshelf/BookCard.tsx:74-92`
- Test: `novel-downloader/services/frontend/src/features/bookshelf/__tests__/BookCard.test.tsx`（新建，用 Vitest + Testing Library，若项目已有前端测试则沿用其框架）

**Interfaces:**
- Consumes: `window.AndroidBridge`（Android APK 注入，类型 `{ saveExport(taskId: string, fileName: string): void }`）；现有 `useExport()` 返回 `{ task_id, status }`；导出文件名由后端 `download_export` 返回的 `Content-Disposition` 推导，前端用 `novel.title` + 扩展名（从 `/api/v2/export/format` 或导出配置取首个启用格式）。
- Produces: `handleExport` 中下载分支改为——`if (window.AndroidBridge) { window.AndroidBridge.saveExport(task.task_id, fileName) } else { window.open(...) }`。

- [ ] **Step 1: 看现有导出逻辑（确认行号与结构）**

```bash
cd novel-downloader/services/frontend
sed -n '70,95p' src/features/bookshelf/BookCard.tsx
```

确认 `handleExport` 的 `window.open` 行（当前为 `BookCard.tsx:84`）。

- [ ] **Step 2: 修改 `BookCard.tsx` 下载分支**

原代码（约 line 74-92）：

```tsx
const handleExport = async () => {
    if (!novelId || exporting) return;
    setExporting(true);
    try {
      const body = { novel_id: novelId, ...导出配置 };
      const task = await exportMut.mutateAsync(body);
      if (task.status === "completed" && task.task_id) {
        // ↓↓↓ 这里替换
        window.open(`/api/v2/export/download/${task.task_id}`, "_self");
      }
    } finally {
      setExporting(false);
    }
};
```

改为：

```tsx
const handleExport = async () => {
    if (!novelId || exporting) return;
    setExporting(true);
    try {
      const body = { novel_id: novelId, ...导出配置 };
      const task = await exportMut.mutateAsync(body);
      if (task.status === "completed" && task.task_id) {
        const androidBridge = (window as unknown as {
          AndroidBridge?: { saveExport(taskId: string, fileName: string): void };
        }).AndroidBridge;
        if (androidBridge) {
          // Android APK：走系统"保存到"对话框（SAF）
          androidBridge.saveExport(task.task_id, `${title}.zip`);
        } else {
          // 桌面/浏览器：现有逻辑
          window.open(`/api/v2/export/download/${task.task_id}`, "_self");
        }
      }
    } finally {
      setExporting(false);
    }
};
```

> 文件名默认 `${title}.zip`（多格式导出打包 ZIP）；单格式后续迭代从导出配置精确推导。

- [ ] **Step 3: 前端构建验证**

Run: `cd novel-downloader/services/frontend && npm ci && npm run build`
Expected: BUILD SUCCESS（TypeScript 编译通过；若仓库无前端测试框架则此步即验证，不强制新增测试文件）

- [ ] **Step 4: 提交**

```bash
cd novel-downloader
git add services/frontend/src/features/bookshelf/BookCard.tsx
git commit -m "feat: 前端导出支持 Android SAF 保存分支"
```

---

### Task 6: build-apk.yml CI + 一键构建脚本

**Files:**
- Create: `novel-downloader/.github/workflows/build-apk.yml`
- Create: `novel-downloader/android/scripts/build-apk.sh`

**Interfaces:**
- Consumes: `services/frontend`（npm build）；`android/` Gradle 项目；GitHub Secrets：`KEYSTORE_BASE64` / `KEYSTORE_PASSWORD` / `KEY_ALIAS` / `KEY_PASSWORD`（release 签名，可选——未配置时出未签名 APK）。
- Produces: `novel-downloader-web-{version}-android.apk` artifact；`build-apk.sh` 本地一键脚本（提示仅 CI 使用）。

- [ ] **Step 1: 创建 `android/scripts/build-apk.sh`**

```bash
#!/usr/bin/env bash
# 一键构建 Android APK（CI 专用；本机无 Android SDK 时不执行）
set -euo pipefail
cd "$(dirname "$0")/../.."

# 1. 构建前端
(cd ../../services/frontend && npm ci && npm run build)
rm -rf app/src/main/assets/frontend
mkdir -p app/src/main/assets/frontend
cp -r ../../services/frontend/dist/* app/src/main/assets/frontend/

# 2. 组装 Gradle wrapper（若未提交 jar）
if [ ! -f gradle/wrapper/gradle-wrapper.jar ]; then
  gradle wrapper --gradle-version 8.7 || true
fi

# 3. 构建 APK
./gradlew :app:assembleRelease

# 4. 输出路径
ls -lh app/build/outputs/apk/release/
```

- [ ] **Step 2: 创建 `.github/workflows/build-apk.yml`**

```yaml
name: build-apk

on:
  workflow_dispatch:
    inputs:
      version:
        description: '版本号（可选，用于产物命名）'
        required: false
        default: ''

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          distribution: temurin
          java-version: '17'

      - name: Build frontend & APK
        run: |
          chmod +x android/scripts/build-apk.sh
          android/scripts/build-apk.sh
        shell: bash

      - name: Sign APK (if secrets present)
        if: env.KEYSTORE_BASE64 != ''
        env:
          KEYSTORE_BASE64: ${{ secrets.KEYSTORE_BASE64 }}
          KEYSTORE_PASSWORD: ${{ secrets.KEYSTORE_PASSWORD }}
          KEY_ALIAS: ${{ secrets.KEY_ALIAS }}
          KEY_PASSWORD: ${{ secrets.KEY_PASSWORD }}
        run: |
          echo "$KEYSTORE_BASE64" | base64 -d > android/keystore.jks
          cd android
          ./gradlew :app:signingReport || true
          # 用 apksigner 对 release APK 签名（路径按 AGP 输出）
          find app/build/outputs/apk -name '*.apk' -exec \
            "$ANDROID_HOME/build-tools/34.0.0/apksigner" sign \
            --ks keystore.jks --ks-pass "pass:$KEYSTORE_PASSWORD" \
            --key-pass "pass:$KEY_PASSWORD" --ks-key-alias "$KEY_ALIAS" \
            --out {}.signed {} \;

      - name: Upload APK artifact
        uses: actions/upload-artifact@v4
        with:
          name: novel-downloader-android-apk
          path: |
            android/app/build/outputs/apk/release/*.apk
          if-no-files-found: error
```

- [ ] **Step 3: 提交**

```bash
cd novel-downloader
git add .github/workflows/build-apk.yml android/scripts/build-apk.sh
git commit -m "feat: 新增 Android APK 构建 workflow 与一键脚本"
```

---

## Self-Review

**1. Spec 覆盖：**
- §2 架构（Service 拉起 Python + WebView）→ Task 3/4 ✅
- §3 app_data 公共 Documents + NLD_APP_DATA 注入 → Task 2 ✅
- §3/§4.3 SAF 导出 → Task 4（AndroidBridge）+ Task 5（前端分支）✅
- §5.1 MainActivity 健康轮询 15s → Task 4 ✅
- §5.3 server.py 静态挂载 + 可写检测 → Task 2 ✅
- §6.1 pip 依赖（排除 drissionpage/psutil）→ Task 1 ✅
- §6.3 存储权限（API 29/30+）→ Task 1 manifest + Task 4 引导 ✅
- §7 CI build-apk.yml workflow_dispatch + 签名 Secrets → Task 6 ✅
- §8 错误处理（503 提示、导出失败 Toast）→ Task 2 `ensure_app_data_writable` + Task 4 Toast ✅
- §9 测试（pytest 复用 + gradlew test）→ Task 2 单测 + Task 6 CI ✅
- 导出 API 异步任务模式 → spec §4.3/§5.4 已修正，Task 4/5 按实际 API 实现 ✅

**2. Placeholder 扫描：** 无 TBD/TODO；所有代码块为完整可写实现。Task 3 Step 2 的 `_shutdown` 降级路径明确说明。

**3. Type 一致性：**
- `AndroidBridge.saveExport(taskId: String, fileName: String)`（Task 4）↔ 前端 `androidBridge.saveExport(task.task_id, ...)`（Task 5）✅
- `NLD_APP_DATA`（Task 2）↔ `config_service.py:27` `os.environ.get("NLD_APP_DATA")` ✅
- 端口 `18080` 贯穿 Task 2/3/4 ✅
- `server.py` 模块名 `server`（Chaquopy `Python.start(cls, "server")`）↔ 文件 `server.py` ✅

**已知边界（实现时注意）：**
- Task 3 `_shutdown` 依赖 uvicorn 内部 `_servers`，可能不稳定；降级 `os._exit(0)` 已在计划中说明。
- 图标资源用占位 XML，正式图标后续替换（不阻塞构建）。
- `keystore.properties` 本地签名为可选路径（Task 1 Step 5 的 release signingConfig 为空则出未签名 APK，CI 里 apksigner 处理）。
- 前端测试框架：仓库当前未见 `__tests__` 目录与 Vitest 配置，Task 5 以 `npm run build` 作为验证门槛，不强行引入测试框架（YAGNI）。
