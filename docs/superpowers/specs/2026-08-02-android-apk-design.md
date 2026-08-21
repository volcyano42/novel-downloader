# Android APK 构建设计

> 日期：2026-08-02  
> 状态：设计完成，待实现  
> 基于：brainstorming 方案 A（Chaquopy + WebView）

## 1. 目标

为 novel-downloader 构建 Android APK，用户可像普通 App 安装使用。Python 解释器动态执行（不编译），WebView 加载现有 React SPA 前端，提供核心下载 + 导出功能。

## 2. 架构

```
┌─────────────────────────────────────────┐
│              Android APK                 │
│  ┌──────────────────────────────────┐   │
│  │        MainActivity              │   │
│  │  ┌────────────────────────────┐  │   │
│  │  │        WebView             │  │   │
│  │  │  http://127.0.0.1:18080    │  │   │
│  │  │  (现有 React SPA 前端)      │  │   │
│  │  └────────────────────────────┘  │   │
│  │  ┌────────────────────────────┐  │   │
│  │  │    ForegroundService        │  │   │
│  │  │  ┌──────────────────────┐  │  │   │
│  │  │  │  Chaquopy Python     │  │  │   │
│  │  │  │  uvicorn + FastAPI   │  │  │   │
│  │  │  │  novelbase + deps    │  │  │   │
│  │  │  └──────────────────────┘  │  │   │
│  │  └────────────────────────────┘  │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

**核心流程**：
1. App 启动 → `ForegroundService` 拉起 Python 进程（uvicorn + FastAPI，监听 `127.0.0.1:18080`）
2. `MainActivity` 轮询等待后端就绪 → `WebView` 加载 `http://127.0.0.1:18080`
3. 用户操作 WebView 内的 React SPA → 请求走本地 FastAPI → 下载/导出
4. App 退到后台 → Service 保持运行（前台通知:"小说下载器运行中"）；退出 → Service 停止

## 3. 项目结构

在仓库内新增 `android/` 目录，为独立 Gradle 项目，不干扰现有 Python/React 构建：

```
novel-downloader/
├── android/                             # 新增：Android 项目
│   ├── build.gradle.kts                 # 根构建（Chaquopy 插件 15.0.1）
│   ├── settings.gradle.kts
│   ├── gradle.properties
│   ├── app/
│   │   ├── build.gradle.kts             # 模块构建（依赖、Python pip 列表）
│   │   └── src/
│   │       └── main/
│   │           ├── AndroidManifest.xml   # 权限、Service 声明
│   │           ├── java/com/novel/downloader/
│   │           │   ├── MainActivity.kt   # WebView + 启动 Service
│   │           │   └── ServerService.kt  # ForegroundService：拉起 Python
│   │           ├── python/              # Chaquopy 约定：Python 源码
│   │           │   └── server.py        # FastAPI 入口（uvicorn）
│   │           ├── res/                 # 图标、通知栏资源、strings.xml
│   │           └── assets/
│   │               └── frontend/        # 构建时从 services/frontend/dist/ 复制
│   └── scripts/
│       └── build-apk.sh                # 一键构建脚本
│
├── services/frontend/                   # 现有 React SPA（不变）
├── novelbase/                           # 现有核心库（不变）
└── .github/workflows/
    └── build-apk.yml                    # 新增：CI 构建 APK
```

### 关键设计决策

| 设计点 | 决策 | 理由 |
|--------|------|------|
| Python 代码位置 | `app/src/main/python/server.py` | Chaquopy 约定，自动识别为 Python 源码 |
| 前端进入 APK | CI 先 `npm run build`，产物复制到 `assets/frontend/` | FastAPI 用 `StaticFiles` 挂载，WebView 加载 localhost |
| novelbase 依赖 | `pip install` 仓库根目录（`-e ../..`） | 不复制源码，保持单一来源 |
| 后端端口 | 固定 `18080` | 与 desktop 版一致 |
| browser 模式 | 不可用，仅暴露 requests + api | DrissionPage 依赖 Chromium，Android 无法运行 |
| **app_data 存储** | **公共存储** `/storage/emulated/0/Documents/novel-downloader/app_data` | **重装后数据保留、直接复用**；需存储权限（见 §6.3 / §8） |
| **下载目录** | **`{app_data}/storage/`** | 与现有 `get_database_url()`（`APP_DATA/storage/novels.db`）一致，零改动，重装复用 |
| **导出目录** | **系统文件夹选择器（SAF）** | 每次导出由用户选择保存位置，Android 11+ 免存储权限 |
| 通知栏 | 前台 Service 显示"小说下载器运行中" | Android 8.0+ 前台 Service 必须显示通知 |

## 4. 数据流

### 4.1 启动流程

```
用户点击图标
  → MainActivity.onCreate()
    → startForegroundService(ServerService)
      → ServerService.onStartCommand()
        → Python.start("server.py")   // Chaquopy API
          → server.py: uvicorn.run(app, host="127.0.0.1", port=18080)
        → 显示通知 "小说下载器运行中"
    → MainActivity 轮询 http://127.0.0.1:18080/health
      → HTTP 200 → WebView.loadUrl("http://127.0.0.1:18080")
```

### 4.2 下载流程

```
用户点下载
  → WebView JS fetch POST /api/v2/download/start
    → FastAPI 创建下载任务
      → novelbase.source.engine.fetch(...)  // requests 模式
      → SSE 推送进度 → WebView EventSource 接收
    → SQLite 写入 {app_data}/storage/novels.db（现有 get_database_url() 逻辑）
```

### 4.3 导出流程（SAF 系统文件夹选择器）

```
用户点导出（现有 ExportDialog + useExport() 流程）
  → WebView JS POST /api/v2/export（body 含 novel_id/格式配置）→ {task_id}
  → 轮询 GET /api/v2/export/task/{task_id} 直到 status=completed
  → 检测环境：window.AndroidBridge 存在？
      ├─ 否（桌面/浏览器）→ window.open(`/api/v2/export/download/${task_id}`, "_self")  // 现有逻辑
      └─ 是（Android）→ AndroidBridge.saveExport(task_id, 文件名)
          → MainActivity 启动 ACTION_CREATE_DOCUMENT（系统"保存到"对话框）
            → 用户选择位置 + 确认文件名（默认 {book_name}.{format}）
            → Kotlin 拿 content:// URI → DocumentFile.openOutputStream
              → HTTP GET http://127.0.0.1:18080/api/v2/export/download/{task_id}
                → 流式写入 OutputStream（大文件不占内存）
            → 完成 → Toast "导出完成：{位置}"
```

- 复用现有异步导出任务 API（`triggerExport` / `exportTaskStatus` / `download_export`），后端零改动
- Android 上仅把"下载"这一步从 `window.open` 换成 SAF 保存，其余逻辑不变
- 每次导出都弹系统选择器，用户自主决定位置（零权限，符合 Android 11+ 存储规范）

### 4.4 关闭流程

```
用户退出 App（返回键 / 划掉）
  → MainActivity.onDestroy()
    → stopService(ServerService)
      → ServerService.onDestroy()
        → Python 进程终止
```

## 5. 组件详情

### 5.1 MainActivity.kt

- 继承 `AppCompatActivity`
- 持有 `WebView`，配置：JavaScript 启用、DOM storage 启用、缩放禁用
- `onCreate`：启动 `ServerService`，轮询 `http://127.0.0.1:18080/health`（间隔 500ms，最多 30 次）
- `onDestroy`：停止 `ServerService`
- 处理 WebView 内链接跳转（`shouldOverrideUrlLoading` 返回 false，全在 WebView 内）

### 5.2 ServerService.kt

- 继承 `Service`，`ForegroundServiceStartNotAllowedException` 兼容处理
- 创建通知渠道 `novel_downloader_channel`
- `onStartCommand`：创建 Python 实例，`python.start("server.py")`（Chaquopy 6.3.0+ API）
- `onDestroy`：停止 Python，取消通知
- 注：Chaquopy 的 `Python.start()` 在当前线程阻塞运行 uvicorn，`onStartCommand` 需在子线程调用

### 5.3 server.py

```python
import os
from pathlib import Path
import uvicorn
from android.os import Environment
from services.backend.main import app  # 现有 FastAPI app

# ── app_data 指向公共 Documents（重装可复用）──
doc_dir = Path(str(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS)))
app_data = doc_dir / "novel-downloader" / "app_data"
app_data.mkdir(parents=True, exist_ok=True)
os.environ["NLD_APP_DATA"] = str(app_data)  # config_service.py 优先读此 env

# 挂载前端静态文件
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="assets/frontend", html=True), name="frontend")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18080, log_level="info")
```

> 注：写入公共目录需要存储权限，授予流程见 §6.3；`NLD_APP_DATA` env 在 uvicorn 启动前设置，`config_service.py` 现有逻辑（env 优先）零改动生效。

### 5.4 AndroidBridge.kt（导出保存桥接）

```kotlin
class AndroidBridge(private val activity: MainActivity) {
    companion object { const val REQUEST_SAVE = 1001 }

    private var pendingTaskId: String? = null
    private var pendingFileName: String? = null

    @JavascriptInterface
    fun saveExport(taskId: String, fileName: String) {
        // 1. 暂存导出参数
        pendingTaskId = taskId
        pendingFileName = fileName
        // 2. 启动系统"保存到"对话框
        val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
            addCategory(Intent.CATEGORY_OPENABLE)
            type = "application/octet-stream"   // 按扩展名映射 MIME
            putExtra(Intent.EXTRA_TITLE, fileName)
        }
        activity.startActivityForResult(intent, REQUEST_SAVE)
    }

    fun onSaveResult(uri: Uri) {
        // 3. 用户确认位置后，流式拉取后端导出文件写入 URI
        val taskId = pendingTaskId ?: return
        val fileName = pendingFileName ?: return
        Thread {
            try {
                val url = "http://127.0.0.1:18080/api/v2/export/download/$taskId"
                activity.contentResolver.openOutputStream(uri)?.use { out ->
                    URL(url).openStream().use { it.copyTo(out) }
                }
                activity.runOnUiThread { Toast.makeText(activity, "导出完成", Toast.LENGTH_LONG).show() }
            } catch (e: Exception) {
                activity.runOnUiThread { Toast.makeText(activity, "导出失败：${e.message}", Toast.LENGTH_LONG).show() }
            }
        }.start()
    }
}
```

- `MainActivity` 注册 `webView.addJavascriptInterface(AndroidBridge(this), "AndroidBridge")`
- 前端调用：`window.AndroidBridge.saveExport(taskId, fileName)`（`BookCard.tsx` 的下载分支按 `window.AndroidBridge` 是否存在切换）

## 6. 依赖管理

### Python 依赖（build.gradle.kts 声明）

```
python {
    pip {
        install "-r ../../requirements.txt"
        install "-e ../.."             // novelbase 库
        // 排除 Android 不可用包
        exclude "drissionpage"
        exclude "psutil"
    }
}
```

### Android 依赖

- `androidx.webkit:webkit` — WebView 增强
- `com.chaquo.python:gradle:15.0.1` — Chaquopy 插件
- `androidx.core:core-ktx` — 前台 Service 兼容

### 前端构建（CI 脚本）

```bash
cd services/frontend
npm ci
npm run build
cp -r dist/* ../../android/app/src/main/assets/frontend/
```

### 存储权限（app_data 写入公共目录）

| Android 版本 | 权限方案 |
|--------------|----------|
| Android 10 (API 29) | `WRITE_EXTERNAL_STORAGE` 运行时权限 + `requestLegacyExternalStorage=true`（AndroidManifest） |
| Android 11+ (API 30+) | `MANAGE_EXTERNAL_STORAGE`（"所有文件访问"），首次启动弹引导页跳系统设置开启；App 不发布 Google Play（见 §10），该权限可用 |

- 权限缺失时后端仍可读（`getExternalStoragePublicDirectory` 可读），仅写入受限；`server.py` 启动时检测 `app_data` 可写性，失败则返回 503 并在前端提示"请授予存储权限"
- 导出走 SAF（§4.3），**不受存储权限影响**——Android 11+ 上即使未授予"所有文件访问"也能导出

## 7. CI 构建

### build-apk.yml（GitHub Actions）

- **触发**：`workflow_dispatch`（手动触发）
- **运行环境**：`ubuntu-latest`
- **步骤**：
  1. Checkout 代码
  2. 设置 JDK 17
  3. 构建前端（`npm ci && npm run build`，复制到 assets/frontend/）
  4. `./gradlew assembleRelease`（Android 命令行构建）
  5. 签名 APK（keystore 走 GitHub Secrets）
  6. 上传 APK 为 workflow artifact

### 签名

- Debug 构建：Chaquopy 默认 debug keystore
- Release 签名：`KEYSTORE_BASE64` + `KEYSTORE_PASSWORD` + `KEY_ALIAS` + `KEY_PASSWORD` 走 GitHub Secrets

## 8. 错误处理

| 场景 | 处理方式 |
|------|----------|
| Python 启动失败 | Service 停止，MainActivity 显示 Toast "启动失败，请重试" |
| 后端健康检查超时（15s） | WebView 显示本地 error.html："服务未就绪，请重启 App" |
| 后端运行时崩溃 | Chaquopy 抛出 `PyException`，Service 捕获后重启 Python（最多 1 次） |
| WebView 加载失败 | 显示 Android 原生错误界面，提供刷新按钮 |
| 网络请求失败（source 不可用） | FastAPI 返回标准错误，前端已有错误处理 UI |
| **app_data 不可写（权限未授予）** | server.py 启动检测，返回 503，前端提示"请授予存储权限"并跳引导 |
| **导出取消 / URI 写入失败** | AndroidBridge 捕获 IOException，Toast "导出失败：{原因}" |
| 存储空间不足 | FastAPI 检测剩余空间 < 100MB 时返回 507，前端提示 |

## 9. 测试策略

| 层级 | 内容 | 工具 |
|------|------|------|
| Python 后端 | 复用现有 `tests/`（121 passed），Android 环境下跑同一套 | pytest（Chaquopy 支持 `python -m pytest`） |
| Android 单元测试 | `ServerService` 启动/停止逻辑 | JUnit + Robolectric |
| Android 集成测试 | Service + WebView 端到端启动 | Espresso / UI Automator |
| CI 验证 | `./gradlew test` + APK 构建成功 | GitHub Actions |

## 10. 已知限制

- **browser 模式不可用**：DrissionPage 依赖 Chromium，Android 无法运行；前端 source 选择器需过滤 browser 模式（通过 capabilities API 已自动处理）
- **APK 体积较大**：Python + 依赖约 50-80MB，加上前端约 90-120MB
- **启动耗时**：首次启动需解压 Python 环境（Chaquopy 首次运行解压），约 3-5 秒
- **不支持 Android 5.x 以下**：Chaquopy 最低支持 API 21（Android 5.0）
- **Android 11+ 需"所有文件访问"权限**：首次启动引导用户在系统设置开启（不发布 Google Play，该权限可用）；Android 10 走 WRITE_EXTERNAL_STORAGE 运行时权限
- **重装复用**：app_data 在公共 Documents，卸载重装后数据保留，重新授权存储权限即可继续使用
- **不发布 Google Play**：自签名 APK + GitHub Release 分发（与现有 portable 模式一致）

## 11. 不包含的内容

- ❌ 原生 Android UI（使用 WebView 套现有前端）
- ❌ browser 模式支持
- ❌ 后台定时下载 / 通知推送
- ❌ Google Play 上架
- ❌ iOS 支持
