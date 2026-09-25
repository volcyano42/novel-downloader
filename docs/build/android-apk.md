# Android APK 方案（Chaquopy 嵌入 Python + WebView，2026-08-02 落地）

**架构**：APK 启动 `ForegroundService`（ServerService.kt）通过 Chaquopy `Python.start` 拉起 uvicorn + 现有 FastAPI 后端（监听 `127.0.0.1:18080`），`MainActivity` 用 WebView 加载现有 React SPA。浏览器模式不可用（构建时排除 `playwright` 依赖——Chaquopy 环境无法提供 Playwright 浏览器内核），仅 requests + api 模式。

**目录与关键文件**（`android/`，独立 Gradle 项目，Chaquopy 插件 15.0.1（wheel 仓库 `chaquo.com/pypi-13.1`）+ AGP 8.5.2 + Kotlin 1.9.24，minSdk 24 / targetSdk 34）：

| 文件 | 职责 |
|------|------|
| `app/src/main/python/server.py` | 后端入口：注入 `NLD_APP_DATA` → import `backend.main:app` → 挂载前端静态 → `_start()` 阻塞跑 uvicorn |
| `app/src/main/python/frontend/` | 前端构建产物（build-apk.sh 从 `frontend/dist/` 复制，**不是 Android assets**） |
| `java/com/novel/downloader/ServerService.kt` | 前台服务拉起 Python（START_STICKY，API 21-25 兼容） |
| `java/com/novel/downloader/MainActivity.kt` | WebView + 健康轮询（`/api/v2/health`，15s 超时）+ 权限引导 |
| `java/com/novel/downloader/AndroidBridge.kt` | SAF 导出桥（`saveExport(taskId, fileName)` JavaScriptInterface） |
| `scripts/build-apk.sh` | CI 构建脚本：npm build → 复制 `backend/` + `shared/`（+ 公开库的 `novelbase/`）+ `init_config.py` + `template/` + `frontend/` 进 `src/main/python/` → `assembleRelease` |

**关键设计点**：

- **backend/ shared/ 单一源码，构建时复制进 Android（重要）**：`backend/`、`shared/`、`init_config.py`、`template/` 只有仓库根一份源码，**不是双份维护**。`build-apk.sh` 每次构建时先 `rm -rf app/src/main/python/backend` 删旧副本，再从仓库根 `cp -r` 最新源码进 `src/main/python/`（构建产物，已被 .gitignore 忽略，不提交）。因此：
  - **改 backend/ 的 bug → 只改仓库根一处**，重跑 build-apk.sh（或 CI 构建）即自动同步进 APK，**无需改 android/ 侧**；本地验证时注意重跑构建（CI 每次全新构建无此问题）
  - **不要手动编辑 `android/app/src/main/python/backend/` 下的文件**——下次构建会被 `rm -rf` 清掉，手动改动丢失
  - **android/ 专属代码例外**：`server.py`、`MainActivity.kt`、`AndroidBridge.kt` 等 android/ 自己的文件只存在一份，改它们就是改 Android 侧本身
  - **`novelbase/` 两库不同（2026-09-19 起）**：私有仓库有 `pyproject.toml`，由 Chaquopy `pip { install("file:../..") }` 以 pip 包安装；**公开仓库没有 `pyproject.toml`**（`PUBLIC_MANIFEST.md` 规定 public 自维护版本元数据），改为与 `backend/` 同法由 `build-apk.sh` 复制 `../novelbase` 源码进 `src/main/python/`。否则 public 的 `install("file:../..")` 会直接报 `Directory '.' is not installable. Neither 'setup.py' nor 'pyproject.toml' found.`，build-apk 必然失败
- **健康检查**：复用 `backend/main.py` 的 `/api/v2/health`（注册于 SPA fallback 与静态 mount 之前，任何环境可达）；**不要**在 server.py 自注册 `/health`（会被 SPA fallback 拦截，已踩坑）
- **app_data 存公共 Documents**：`server.py` 用 `android.os.Environment.getExternalStoragePublicDirectory(DIRECTORY_DOCUMENTS)` 计算，写入 `NLD_APP_DATA` env；`init_config.py` 的 `_target_dir()` 已支持 `NLD_APP_DATA` 优先（2026-08-02 增强，桌面版无 env 行为不变）→ 重装可复用
- **导出走 SAF**：前端 `BookCard.tsx` 检测 `window.AndroidBridge` 存在 → `saveExport(task_id, 文件名)` → 系统"保存到"对话框 → 流式写入；否则 `window.open`（桌面逻辑）
- **明文 HTTP**：`res/xml/network_security_config.xml` 只放行 `127.0.0.1`/`localhost`（Android 9+ 默认禁明文，已配置）
- **权限**：API 30+ 引导 `MANAGE_EXTERNAL_STORAGE`（设置页），API 23-29 运行时 `WRITE_EXTERNAL_STORAGE`；授权返回后自动 `ServerService.start` 重启后端（stopSelf 后 START_STICKY 无效，必须显式重启）
- **签名**：CI 用 GitHub Secrets（`KEYSTORE_BASE64`/`KEYSTORE_PASSWORD`/`KEY_ALIAS`/`KEY_PASSWORD`）经 apksigner 签名；未配置时出未签名 APK；产物按 `inputs.version` 命名
- **测试**：`tests/test_android_server.py` 4 个（env 注入、静态挂载、/api/v2/health 可达、env 兜底）；本地 pytest 无法验证 Chaquopy 打包（无 Android SDK）
- **minSdk 24（2026-09-19，原 21）**：Chaquopy 只接受 tag ≤ app minSdk 的 wheel（维护者原话 "pip will accept wheels whose tags are less than or equal to your app's minimum API level"），而 `lxml`/`PyYAML` 在仓库 `chaquo.com/pypi-13.1` 里**只有 `android_24` 的 cp311 wheel**；`yarl`/`multidict`/`numpy`/`frozenlist` 的 `android_21` wheel 仍可安装（21 ≤ 24）。Chaquopy 17.0 也把 24 定为官方最低要求 → 代价是放弃 Android 5.0/6.0（7.0+ 覆盖率约 97-98%）
- **Android 依赖清单（2026-09-19）**：Chaquopy 的 `pip` 块**只有 `install`/`options`，没有 `exclude`**（写了会 KTS 编译失败：`Unresolved reference`）。依赖排除改由 `build-apk.sh` 第 1b 步生成 `android/.req-android.txt`（`grep -v -E "^(playwright|psutil|pillow-heif)"`），`build.gradle.kts` 安装该清单；要排除其它包就改这条 grep
- **Chaquopy 启动 API 与 Kotlin 编译修正（2026-09-24）**：`ServerService` 原写 `Python.start(ServerService::class.java, "server")`，在 Chaquopy 15.0.1 下编译不过（`Python.start` 只接受 `Python.Platform`，且模块不会以 `__main__` 方式执行）→ 改为 `Python.start(AndroidPlatform(this@ServerService))`（带 `Python.isStarted()` 守卫）+ `getModule("server").callAttr("_start")`；`MainActivity` 里不存在的标签 `this@healthPoll` 改为直接引用 `healthPoll` 字段。依赖清单同时 pin `fastapi==0.120.0`（0.121+ 起要求 `pydantic>=2.9`，与 `pydantic<2` 冲突）
- **构建状态（2026-09-24）**：公开库 `build-apk.yml` **已构建成功**（run `35975357459`，artifact `novel-crawler-apk-dev` ≈28.6 MB，**未签名**）；2026-09-19~24 逐层修掉 8 处阻塞：KTS `#` 注释、`pip { exclude }`（该 API 不存在）、`java.util.Properties()`、lxml/PyYAML 的 ABI tag（→ minSdk 24）、fastapi/pydantic 版本冲突、`Python.start` 参数、`this@healthPoll`、`healthPoll` 初始化自引用
- **遗留（需真机/后续确认）**：APK 未签名（未配置 `KEYSTORE_*` secrets，仅可侧载测试）；产物名跟随 `inputs.version`（不传则为 `-dev`）；APK 内 `versionName` 为 gradle 硬编码（public `1.0.1` / private `1.0.0`）；`buildPython 3.12.3` 与 app Python 3.11 不匹配 → `.pyc` 预编译被跳过（仅警告，运行时可解释执行）；真机启动（Chaquopy 首次解压 + uvicorn + WebView）仍未验证；私有库未触发构建验证
