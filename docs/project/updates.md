# 更新记录 — v4.2.3（9a51b561）之后

> 基准：tag v4.2.3 = commit `9a51b561`（main 分支）。以下为 dev 分支在 9a51b561 之后的全部非合并提交（21 个），日期均为 2026-08-02。

## 提交时间线（倒序）

| 短哈希 | 提交消息 |
|--------|----------|
| [`6023f3a`](#6023f3a) | fix: 存储权限授权后自动重启后端服务并消除轮询竞态 |
| [`9b6ac8a`](#9b6ac8a) | fix: Android 构建产物清理与输入校验加固 |
| [`668b485`](#668b485) | fix: Android 打包补全 Python 运行时模块并修复配置初始化与权限流程 |
| [`1ec612e`](#1ec612e) | fix: APK 产物按版本号命名并动态解析 build-tools 路径 |
| [`3e5219b`](#3e5219b) | chore: 删除 Nuitka 构建脚本 build-web.ps1（portable 为主方案） |
| [`e4b463f`](#e4b463f) | chore: 彻底移除 Nuitka 构建路径（删 build-web.ps1，更新全部引用与注释） |
| [`45b270a`](#45b270a) | feat: 新增 Android APK 构建 workflow 与一键脚本 |
| [`6cbe243`](#6cbe243) | fix: 构建脚本防 init_config 漏包加固 |
| [`b60d94e`](#b60d94e) | feat: 前端导出支持 Android SAF 保存分支 |
| [`0c98d93`](#0c98d93) | fix: 健康轮询加 15s 超时并放行 localhost 明文 HTTP |
| [`a66e3dc`](#a66e3dc) | fix: 启动.bat 就绪等待改用系统 timeout.exe |
| [`09631d3`](#09631d3) | feat: 新增 MainActivity 与 AndroidBridge（WebView + SAF 导出 + 权限引导） |
| [`e4f6122`](#e4f6122) | fix: ServerService 兼容 API 21-25 并加固 uvicorn 启动幂等 |
| [`11ce3de`](#11ce3de) | feat: 新增 ServerService 前台服务拉起 Python 后端 |
| [`7198123`](#7198123) | fix: 修复 env 兜底测试的无条件目录删除隐患 |
| [`beb5201`](#beb5201) | fix: 修复 health 测试的无条件目录删除隐患 |
| [`1bf512b`](#1bf512b) | fix: 健康检查改用 /api/v2/health（/health 会被 SPA fallback 拦截） |
| [`38c0f93`](#38c0f93) | feat: 新增 Android 后端入口 server.py |
| [`008e201`](#008e201) | fix: Windows portable 打包补复制 init_config.py（uvicorn 启动失败根因） |
| [`a4ab581`](#a4ab581) | fix: 修正 Chaquopy pip 本地 novelbase 安装语法 |
| [`2061de7`](#2061de7) | feat: 新增 Android 项目脚手架（Gradle + Chaquopy 配置） |

---

## 按主题归纳

### 🆕 Android 平台支持（13 个提交）

项目新增完整的 Android APK 构建能力，基于 Gradle + Chaquopy（Python 嵌入）+ WebView 前端方案。

| 提交 | 说明 |
|------|------|
| `2061de7` | 脚手架：`android/` 目录、Gradle 项目结构、Chaquopy 插件配置 |
| `38c0f93` | 后端入口 `server.py`：NLD_APP_DATA 环境变量注入 + SPA 静态文件挂载 |
| `11ce3de` | `ServerService.kt`：Android 前台通知服务拉起 uvicorn Python 后端 |
| `e4f6122` | ServerService 兼容 API 21-25，加固 uvicorn 启动幂等性 |
| `09631d3` | `MainActivity.kt` + `AndroidBridge.kt`：WebView 加载前端、SAF 导出、权限引导 |
| `b60d94e` | 前端 `BookCard.tsx` 适配 Android SAF 导出分支 |
| `45b270a` | `.github/workflows/build-apk.yml` + `android/scripts/build-apk.sh` 一键构建 |
| `1ec612e` | APK 产物按版本号命名，build-tools 路径动态解析 |
| `a4ab581` | 修正 Chaquopy pip 安装本地 `novelbase` 的语法错误 |
| `668b485` | Android 打包补全 Python 运行时模块（asyncio、concurrent 等），修复配置初始化与权限流程 |
| `9b6ac8a` | Android 构建产物清理与 `init_config` 输入校验加固 |
| `6023f3a` | 存储权限授权后自动重启后端，消除健康轮询与 ServerService 的竞态条件 |
| `0c98d93` | 健康轮询加 15s 超时，放行 localhost 明文 HTTP（`network_security_config.xml`） |

### 🧹 Nuitka 构建路径彻底移除（2 个提交）

| 提交 | 说明 |
|------|------|
| `3e5219b` | 删除 `build-web.ps1`（76 行 Nuitka Windows 构建脚本） |
| `e4b463f` | 清理全部 Nuitka 引用：`build-portable.ps1/.sh`、`build-pypi.ps1/.sh`、`CONTRIBUTING.md` |

> Portable 成为唯一 Windows 构建方案。

### 🔧 构建与启动修复（3 个提交）

| 提交 | 说明 |
|------|------|
| `008e201` | Windows portable 打包补复制 `init_config.py`（缺失导致 uvicorn 启动失败——v4.2.3 已知问题） |
| `6cbe243` | `build-web.ps1` 补打包 `init_config`、`portable.sh` 去掉静默容错（改显式报错） |
| `a66e3dc` | `启动.bat` 就绪等待改用系统 `timeout.exe`（Git Bash 的 GNU `timeout` 抢占致 `sleep` 失效） |

### 🩺 健康检查修复（2 个提交）

| 提交 | 说明 |
|------|------|
| `1bf512b` | 健康检查端点从 `/health` 迁移到 `/api/v2/health`（原 `/health` 被 SPA fallback 拦截返回 index.html） |
| `0c98d93` | 同上（与 Android 网络安全配置打包提交，属同一波修复） |

### 🧪 测试安全加固（2 个提交）

| 提交 | 说明 |
|------|------|
| `beb5201` | 修复 health 测试的无条件 `rmtree` 隐患（对齐 `test2` 守卫模式） |
| `7198123` | 修复 env 兜底测试的无条件目录删除隐患（对齐守卫模式） |

---

## 文件变更统计

```
32 files changed, 827 insertions(+), 92 deletions(-)
```

| 文件 | 状态 | 说明 |
|------|------|------|
| `android/` (8 文件) | **新增** | Android 项目（Gradle + Kotlin + Python） |
| `.github/workflows/build-apk.yml` | **新增** | APK CI |
| `tests/test_android_server.py` | **新增** | Android 服务端测试（4 个用例） |
| `build-web.ps1` | **删除** | Nuitka 构建（已废弃） |
| `init_config.py` | 修改 | NLD_APP_DATA env 优先 |
| `services/backend/main.py` | 修改 | 健康检查路由 |
| `services/frontend/src/.../BookCard.tsx` | 修改 | SAF 导出分支 |
| `build-portable.ps1/.sh` | 修改 | Nuitka 清理 |
| `build-pypi.ps1/.sh` | 修改 | Nuitka 清理 |
| `.gitignore` | 修改 | Android 构建产物 |
| `CONTRIBUTING.md` | 修改 | 构建文档更新 |

---

---

## 2026-08-03 变更（5 个提交）

| 短哈希 | 提交消息 |
|--------|----------|
| `5d695d8` | refactor: 公共 API 重构 — 统一 capabilities 返回结构、拆分 source 子命名空间、移除 split_into_groups |
| `1f1c177` | fix: 手机端底部导航栏右下角恢复为「设置」并清理未使用的 User 导入 |
| `cb48d17` | feat: source 能力契约与运行时签名校验（Protocol + CAPABILITY_META + inspect） |
| `26fd789` | feat: source 能力契约与运行时签名校验（Protocol + CAPABILITY_META 单一数据源） |
| `fb8dd54` | refactor: 移除 registry 的 exe 硬编码兜底（打包编译方案已放弃） |

### 🧹 Registry 清理（1 个提交）

| 提交 | 说明 |
|------|------|
| `fb8dd54` | 删除 `_hardcoded_sources()`/`_hardcoded_exporters()`/`_hardcoded_export_options()`/`_probe_capabilities()` 四个函数及相关 `import re`，Nuitka 打包方案已放弃 |

### 📐 Source 能力契约（3 个提交）

| 提交 | 说明 |
|------|------|
| `26fd789` | 新建 `novelbase/sources/contracts.py`：4 个 `typing.Protocol` 类 + `CAPABILITY_META` 单一数据源 |
| `cb48d17` | registry.py 删 `FUNC_FILE_MAP`，`capabilities()`/`resolve()` 改读 `CAPABILITY_META`；`resolve()` 加 `inspect.signature` 运行时签名校验；source 扫描简化为"目录+`__init__.py`" |
| `5d695d8` | 公共 API 重构：`capabilities()` 统一返回 `dict[str, dict[str, list[str]]]`（单 provider mode 用 `""` key）；`resolve`/`capabilities` 迁入 `novelbase.source` 子命名空间；`split_into_groups` 从 `__all__` 移除；前端 + backend + 测试全部同步更新 |

### 🔧 前端修复（1 个提交）

| 提交 | 说明 |
|------|------|
| `1f1c177` | 手机端底部导航栏右下角「我的」→「设置」，统一复用 `DESKTOP_ITEMS`；清理未使用的 `User` 图标导入 |

## 里程碑

- **v4.2.3**（`9a51b561`，main）：已发布 tag。已知 Windows portable 缺 `init_config.py`（`008e201` 已修复）。
- **dev**（`6023f3a`）：Android 平台完整可用，APK CI 就绪，Nuitka 已移除，测试 125 全绿。
- **dev**（`5d695d8`，2026-08-03）：registry exe 硬编码兜底删除、source 能力契约重构（Protocol + CAPABILITY_META + inspect 签名校验）、手机端导航修复。测试 133 全绿。
- **dev**（`37ad467`，2026-08-05 当前 HEAD）：variant 重命名（provider→variant + default 占位）、NLD_PRIVATE_SOURCES 私有源隔离、BrowserOptions extra_args、版本号 4.2.3→4.3.0、CI 修复。

---
---

## 2026-08-05 变更（6 个提交）

| 短哈希 | 提交消息 |
|--------|----------|
| `9aee58b` | refactor: 将 Linux Chromium 默认参数从核心库移至服务层 |
| `cf37537` | fix: 修复 CI 挂起——skip test_health_route_reachable_via_test_client |
| `a52d00b` | chore: 版本号 4.2.3 → 4.3.0 并更新 CHANGELOG |
| `b48fecf` | feat: 新增 BrowserOptions extra_args 属性并适配 Linux Chromium sandbox 自动参数 |
| `72bfea2` | refactor: provider 重命名为 variant，单实现模式占位改用 default |
| `37ad467` | feat: 敏感代码隔离——NLD_PRIVATE_SOURCES 外部私有源目录 |

### 🏷️ 版本号跃进

| 提交 | 说明 |
|------|------|
| `a52d00b` | `pyproject.toml` + `novelbase/__init__.py` 版本号从 4.2.3 → 4.3.0；CHANGELOG 新增 v4.3.0 段落 |

### 🖥️ BrowserOptions extra_args

| 提交 | 说明 |
|------|------|
| `b48fecf` | `BrowserOptions` 新增 `extra_args: list[str] \| None`，`engine.py` 遍历传入 `ChromiumOptions.set_argument()` |
| `9aee58b` | Linux 默认 sandbox 参数（`--no-sandbox` 等）从 `engine.py` 核心库移到 `services/backend/services/engine_manager.py` |

### 🔄 variant 重命名（跨前后端 + 测试）

| 提交 | 说明 |
|------|------|
| `72bfea2` | 16 文件：`capabilities()` 第二层 key 从 `provider` 改为 `variant`，单实现占位 `""` → `"default"`，`resolve()` 签名 `variant=None`；backend 路由参数 + task_manager；前端 6 页面 + hooks + sessionCache |

### 🔒 敏感代码隔离

| 提交 | 说明 |
|------|------|
| `37ad467` | `source.py` 新增 `_scan_source_dirs()`/`_scan_capabilities()`，`capabilities()` 合并双路径，`resolve()` 用 `importlib.util.spec_from_file_location` 加载私有源；环境变量 `NLD_PRIVATE_SOURCES`；tests 新增 `TestPrivateSources`（4 passed / 1 skipped） |

### 🔧 CI 修复

| 提交 | 说明 |
|------|------|
| `cf37537` | 跳过 `test_health_route_reachable_via_test_client`（CI 环境 `127.0.0.1` 不可达导致挂起）

---

## 2026-08-06 变更（4 个提交）— 阅读页交互调整 + 配置简化

| 短哈希 | 提交消息 |
|--------|----------|
| `01659f3` | refactor: 移除 API variant 的 enabled 字段，简化配置逻辑 |
| `6c32b6c` | chore: app_data/ 脱离 git 跟踪，磁盘保留 |
| `07c9d8f` | refactor: 移除阅读页左右滑动手势跳转章节 |
| `5c6fb1a` | feat: 阅读页目录自动滚动到当前章节 |

---

## 2026-08-11 变更（10 个提交）— 收藏功能 + 下载管理改造 + Nuitka manifest 方案

| 短哈希 | 提交消息 |
|--------|----------|
| `400c62e` | fix: 修复前端 TypeScript 语法错误（variant 缺符号、TooltipVariant 不存在、DownloadDialog 参数重名） |
| `707fb05` | feat: 恢复 Nuitka 打包方案（4.1.3 锁版本，与 portable 共存） |
| `15c929b` | CI: 构建产物 artifact 添加 retention-days:3 防止配额溢出，gitignore 添加会话归档目录 |
| `67de187` | 重构: groups 从 YAML 迁移到 SQLite，新增收藏功能 |
| `39100c8` | 重构: 下载管理面板改为折叠章节队列，取消下载真正生效 |
| `5a18ec8` | fix: 修复便携版 Ctrl+C 退出体验（Windows 去 pause、Linux/Termux 加 trap 清理） |
| `fea52db` | 重构: 书源注册发现机制去硬编码，Nuitka 模式从 manifest 读取 |
| `bb3111f` | 重构: build_manifest 移动到 utils/ |
| `114431e` | 文档: 书源注册重构同步 + Phase 2 插件设计 |

### 按主题归纳

| 提交 | 说明 |
|------|------|
| `67de187` | **收藏与分组**：groups 从 YAML 迁移到 SQLite（user_data.db），新增收藏功能（源自"搜索历史/书籍收藏"设计讨论） |
| `39100c8` | **下载管理**：面板改为折叠章节队列，取消下载真正生效 |
| `fea52db`/`bb3111f`/`114431e` | **Nuitka manifest 方案**：书源注册发现机制去硬编码，Nuitka 模式从 manifest 读取；`build_manifest.py` 归入 `utils/`；书源注册重构同步 + Phase 2 插件设计 |
| `707fb05` | **恢复 Nuitka 打包**（4.1.3 锁版本，与 portable 共存） |
| `400c62e` | 前端 TS 语法错误修复（variant 缺符号、TooltipVariant 不存在、DownloadDialog 参数重名） |
| `15c929b` | CI artifact 加 retention-days:3 防配额溢出；gitignore 添加会话归档目录 |

---

## 2026-08-12 变更（1 个提交）

| 短哈希 | 提交消息 |
|--------|----------|
| `0c8abad` | feat: 直接访问 8000 端口始终可用（前端未构建时显示构建提示页） |

---

## 2026-08-13 变更（21 个提交）— Engine httpx 迁移 + 异步化 + 目录重构

| 短哈希 | 提交消息 |
|--------|----------|
| `ca1734b` | 文档: 目录结构重构设计（shared共享层 + storage分层 + 默认值单一数据源） |
| `52e1ef3` | fix: docs/ 重新纳入 .gitignore，恢复不提交文档的约定 |
| `1cdafa3` | 依赖: httpx 提升为主依赖，移除 requests/urllib3 |
| `5260c17` | feat: 新增编码探测工具 detect_encoding（chardet，替代 apparent_encoding） |
| `293625f` | 重构: RequestsEngine 换 httpx.Client，新增 async_fetch_text/json |
| `f8de64e` | 重构: APIEngine 换 httpx.Client，新增 async_fetch_text/json |
| `76c8382` | feat: BrowserEngine 新增 async_fetch_text/json（asyncio.to_thread 包装） |
| `90e15a6` | feat: Engine 基类新增 async_fetch_text/json 抽象方法 |
| `206bbd8` | 重构: 书源文件 requests 全量替换为 httpx |
| `55186ba` | feat: 新增 shared 共享层（config 单一数据源 + user_data 归位） |
| `216dfd1` | fix: .gitignore 排除 __init__.py（_*.py 规则误伤） |
| `0ec51fe` | 重构: services/backend 上提为 backend/，跨层调用改走 shared |
| `72a0c5f` | 清理: 删除空的 services/__init__.py 残留 |
| `5bc0248` | 重构: services/frontend 上提为 frontend/ |
| `b2405fc` | 重构: cli.py + cli_lib 合并为 cli/ 包，分组功能改走 shared |
| `c57fc37` | 重构: 构建脚本收纳进 scripts/，新增 storage 迁移脚本 |
| `e699380` | 文档: 更新 AGENTS.md 启动命令以匹配新目录结构 |
| `14d1994` | fix: app.py 启动器改用 backend.main:app，清理残留旧路径 |
| `0acd312` | fix: Android 构建脚本适配新目录结构，requirements 同步 httpx/chardet |
| `17b6c44` | 清理: 更新残留注释中的旧路径引用 |
| `9a07463` | test: 补 close 清理 AsyncClient 测试 |

### ⚡ Engine HTTP 层迁移到 httpx（5 个提交）

novelbase 的三种引擎（Requests/API/Browser）从 requests 全量迁移到 httpx：同步 `fetch_text`/`fetch_json` 用 `httpx.Client`，新增异步 `async_fetch_text`/`async_fetch_json` 用 `httpx.AsyncClient`（BrowserEngine 因 DrissionPage 同步库，用 `asyncio.to_thread` 包装）。

| 提交 | 说明 |
|------|------|
| `1cdafa3` | httpx 提升为主依赖，删除 requests/urllib3（pyproject.toml） |
| `5260c17` | 新增 `detect_encoding`（chardet），替代 requests 的 apparent_encoding（httpx 无此属性） |
| `293625f` | RequestsEngine 换 httpx.Client + 新增 async 方法 |
| `f8de64e` | APIEngine 换 httpx + async 方法，保留 params 合并与 post_data 分支 |
| `76c8382` | BrowserEngine 新增 async 方法（asyncio.to_thread 包装同步方法） |
| `90e15a6` | Engine 基类新增 async_fetch_text/json 抽象方法 |
| `206bbd8` | 9 个书源文件 requests → httpx（纯机械替换，签名不变） |

### 📁 目录结构重构（8 个提交）

参考 golang-standards/project-layout 与 DeepSeek-Reasonix 的多客户端架构：`novelbase`（纯核心）→ `shared`（共享应用层）→ `backend`/`cli`/`frontend`（三个薄前端）。

| 提交 | 说明 |
|------|------|
| `55186ba` | 新增 `shared/`：config.py（默认值单一数据源，从 novelbase options 派生）+ user_data.py（groups/favorites/search_history/bookmarks 归位） |
| `0ec51fe` | `services/backend` → `backend/`，跨层调用（cli_lib.user_db）改走 shared |
| `5bc0248` | `services/frontend` → `frontend/` |
| `b2405fc` | `cli.py` + `cli_lib` → `cli/` 包，user_db 归 shared |
| `c57fc37` | 构建脚本收纳进 `scripts/`，新增 `migrate_storage.py`（storage 分层迁移） |
| `e699380` | AGENTS.md 启动命令同步新目录 |
| `14d1994`/`0acd312`/`17b6c44` | 清理 app.py、Android 构建脚本、requirements.txt、注释中的旧路径/旧依赖残留 |

### 🗄️ storage 分层（运行时迁移）

`app_data/storage/` 分层为 `novels/`（31 本小说库）+ `users/default/`（用户数据 user_data.db），为未来多用户隔离预留结构。迁移脚本 `scripts/migrate_storage.py` 已执行，32 个 db 文件迁入新路径，端到端读取验证通过。

### 🧪 测试补充

| 提交 | 说明 |
|------|------|
| `9a07463` | 补 close 清理 AsyncClient 测试（懒加载后关闭 + 未加载时 close 不报错） |

> 本批变更后测试 154 passed, 2 skipped。

---

## 2026-08-13~17 变更（53 个提交）— 导出器契约 + 全链路异步化收尾 + BrowserEngine 换 Playwright + 前端 UI 修复

> 基准：2026-08-13（`9a07463`）之后 dev 分支全部提交，日期 2026-08-13 ~ 08-17。版本号已至 **v4.4.0**。

## 提交时间线（倒序）

| 短哈希 | 提交消息 |
|--------|----------|
| `f601f3b` | 回退: 移除网页顶部全屏按钮（移动端 header + 桌面侧栏） |
| `8744f6f` | 修复: 保存按钮手机端 offset 加大到 bottom-20，避免被底部导航栏遮挡 |
| `61a8c02` | 修复: 下载任务所有状态均可展开查看章节（含已完成/失败） |
| `fce80d4` | 修复: 下载对话框 API 模式默认选中首个 variant，避免未选导致下载不启动 |
| `61d8854` | 修复: 保存按钮移动端不被 bottom nav 遮挡 + 保存时清理 notify 默认值字段 |
| `af35753` | 性能: 书架列表封面返回缩略图（Illustration.thumbnail 等比缩小转 JPEG） |
| `4b385d5` | 修复: 书籍卡片喜欢按钮移左上角 + 下载完成提示音（Web Audio bell） |
| `b298c56` | 新增: 网页顶部全屏按钮（Fullscreen API，移动端 header + 桌面侧栏） |
| `f78fbee` | 修复: 设置页 Range 点击区域加大、API variant 空值 fallback、删导出格式启用按钮 |
| `6968916` | 修复: 章节对比模式标题加 min-w-0 截断 + 封面放大全黑背景锁滚动 |
| `6b3eb0f` | 版本号 4.3.0 → 4.4.0 并更新 CHANGELOG |
| `2aeacdc` | 重构: page 池去掉 max_pages 信号量，改纯懒加载复用 |
| `e736ff5` | 重构: BrowserEngine 加 page 池复用，避免每次抓取新开 tab |
| `7553e29` | 修复: DetailPage 章节状态 Tooltip 缺 TooltipProvider 包裹 |
| `e67c054` | 构建: Windows portable 删 ChromeSetup.exe，统一 playwright install chromium |
| `c51ca23` | 修复: Engine 加 aclose() 异步关闭，shutdown 时 await 释放浏览器进程 |
| `d69b188` | 修复: BrowserEngine final review 问题（懒创建锁、同步 fetch_text 补 retry/backoff） |
| `9341c07` | 构建: 排除项 drissionpage 换 playwright + Chrome 说明改 playwright install chromium |
| `aa73e7f` | 重构: qidian/qimao browser 书源交互改 Playwright（去 to_thread） |
| `6ff78c0` | 修复: BrowserEngine 换 Playwright 的 review 问题（persistent context、懒启动锁、browser_type 选择） |
| `f7fbedf` | 重构: BrowserEngine 从 DrissionPage 换 Playwright（懒启动 + 真异步） |
| `9a2ee9d` | refactor: build-nuitka.sh 删掉 Termux 分支，只保留 Linux x64/arm64 |
| `a574289` | fix: build-nuitka.sh Termux 产物生成 start.sh（onefile 动态 libpython 需 LD_LIBRARY_PATH） |
| `94fce10` | fix: 构建脚本补打包 shared 共享层（backend 依赖 shared.config/user_data） |
| `ffc88cf` | fix: build-nuitka.sh 补依赖安装 + portable 裸包自举 |
| `bce6a95` | fix: build-nuitka.sh 合并历史 build-web/build-termux 的 Termux 特殊处理 |
| `96369dc` | feat: 新增 build-nuitka.sh（Linux/termux 版 Nuitka 单文件构建） |
| `8d3bcd6` | fix: 构建脚本复制 template 而非 app_data（防敏感字段泄露）+ 修 services 旧路径 |
| `e016189` | fix: 修复 termux 构建脚本路径（目录重构遗留）+ 新增本地预装脚本 |
| `4c4dec3` | fix: engine_manager 缓存加锁，消除并发双创建引擎竞态 |
| `524d863` | fix: 修 engine close() 泄漏 + async_fetch_json 补 NetworkError 包装 |
| `6c912d9` | refactor: RequestsEngine 支持 post_data，92xs search 消除私有方法依赖 |
| `72f7c1d` | fix: 恢复 resolve_changdunovel 并改 async（changdunovel 域名支持工具，非死代码） |
| `119328c` | refactor: 去掉 search 无用的 page 参数 + 删除 resolve_changdunovel 死代码 |
| `79ccd42` | fix: 修复暂停功能失效（wait() 反用 + 排队/收尾检查点） |
| `a6751a1` | 修复: 下载进度条逐章实时推进 + engine 同步创建移出事件循环 |
| `9498303` | fix(cli): cmd_search 对 async search 用 asyncio.run 包装，避免返回未消费 coroutine |
| `16b80b7` | refactor: CLI 下载改 asyncio（asyncio.run + asyncio.gather） |
| `e345637` | refactor: task_manager 改 asyncio 原生（asyncio.create_task + asyncio.Event） |
| `7f59c90` | refactor: backend 路由直接 await async 函数，删除死 executor |
| `58f1de5` | refactor: qidian/qimao/92xs 书源 async 化 + 封面下载归 engine |
| `27c01bb` | refactor: fanqie 书源 async 化 + 图片下载归 engine.async_fetch_images |
| `d889877` | refactor: downloader 四函数改 async def（search/resolve_meta/resolve_chapter_list/resolve_chapter） |
| `f3aaebd` | feat: BrowserEngine 实现 async_fetch_images（httpx，不开标签页） |
| `551c008` | test: 为 APIEngine 补 async_fetch_images 批量下载独立测试 |
| `ab25230` | feat: Requests/API 引擎实现 async_fetch_images 批量图片下载 |
| `39a7df5` | feat: Engine 基类新增 async_fetch_images 抽象方法 |
| `87574bf` | refactor: 移除 list_exporter_options（register_export_options 已覆盖其用途） |
| `4c15137` | feat: 导出器新增 list_exporter_formats / list_exporter_options 列表函数 |
| `65a1c8b` | feat: 导出器新增契约（Protocol + 运行时签名校验） |
| `6abe404` | feat: 导出器改为动态发现，支持 NLD_PRIVATE_EXPORTERS 外部自定义格式 |
| `c13e3bb` | 重构: registry.py 改名 exporter.py 并上提到 novelbase 根目录 |
| `a546464` | 重构: source 注册/发现函数从 registry 归一到 novelbase.source |

## 按主题归纳

### 📦 导出器契约与动态发现（6 个提交，08-13）

| 提交 | 说明 |
|------|------|
| `a546464` | source 注册/发现函数从 registry 归一到 `novelbase.source` 命名空间 |
| `c13e3bb` | `registry.py` 改名 `exporter.py` 并上提到 novelbase 根目录 |
| `6abe404` | 导出器改为动态发现，支持 `NLD_PRIVATE_EXPORTERS` 外部自定义格式 |
| `65a1c8b` | 导出器新增契约（Protocol + 运行时签名校验） |
| `4c15137` | 新增 `list_exporter_formats` / `list_exporter_options` 列表函数 |
| `87574bf` | 移除 `list_exporter_options`（`register_export_options` 已覆盖其用途） |

### ⚡ async_fetch_images 图片批量下载（6 个提交，08-14）

| 提交 | 说明 |
|------|------|
| `39a7df5` | Engine 基类新增 `async_fetch_images` 抽象方法 |
| `ab25230` | Requests/API 引擎实现 `async_fetch_images` 批量图片下载 |
| `551c008` | APIEngine 批量下载独立测试 |
| `f3aaebd` | BrowserEngine 实现（httpx，不开标签页） |
| `d889877` | downloader 四函数改 `async def`（search/resolve_meta/resolve_chapter_list/resolve_chapter） |
| `27c01bb` | fanqie 书源 async 化 + 图片下载归 `engine.async_fetch_images` |

### 🔄 全链路异步化收尾 + 引擎修复（12 个提交，08-15）

| 提交 | 说明 |
|------|------|
| `58f1de5` | qidian/qimao/92xs 书源 async 化 + 封面下载归 engine |
| `7f59c90` | backend 路由直接 `await` async 函数，删除死 executor |
| `e345637` | task_manager 改 asyncio 原生（`asyncio.create_task` + `asyncio.Event`） |
| `16b80b7` | CLI 下载改 asyncio（`asyncio.run` + `asyncio.gather`） |
| `9498303` | `cmd_search` 对 async search 用 `asyncio.run` 包装，避免未消费 coroutine |
| `a6751a1` | 下载进度条逐章实时推进 + engine 同步创建移出事件循环 |
| `79ccd42` | 修复暂停功能失效（`wait()` 反用 + 排队/收尾检查点） |
| `119328c` | 去掉 search 无用的 page 参数 + 删除 resolve_changdunovel 死代码 |
| `72f7c1d` | 恢复 `resolve_changdunovel` 并改 async（changdunovel 域名支持工具，非死代码） |
| `6c912d9` | RequestsEngine 支持 `post_data`，92xs search 消除私有方法依赖 |
| `524d863` | 修 engine `close()` 泄漏 + `async_fetch_json` 补 NetworkError 包装 |
| `4c4dec3` | engine_manager 缓存加锁，消除并发双创建引擎竞态 |

### 🌐 BrowserEngine 从 DrissionPage 换 Playwright（8 个提交，08-16）

> **重大变更**：browser 模式底层从 DrissionPage 迁移到 Playwright（懒启动 + 真异步），依赖、文档、书源交互全部同步。

| 提交 | 说明 |
|------|------|
| `f7fbedf` | 核心重构：BrowserEngine 换 Playwright（懒启动 + 真异步） |
| `6ff78c0` | review 问题：persistent context、懒启动锁、`browser_type` 选择 |
| `aa73e7f` | qidian/qimao browser 书源交互改 Playwright（去 to_thread） |
| `9341c07` | 构建排除项 drissionpage 换 playwright，Chrome 说明改 `playwright install chromium` |
| `d69b188` | final review：懒创建锁、同步 `fetch_text` 补 retry/backoff |
| `c51ca23` | Engine 加 `aclose()` 异步关闭，shutdown 时 await 释放浏览器进程 |
| `e67c054` | Windows portable 删 ChromeSetup.exe，统一 `playwright install chromium` |
| `e736ff5`/`2aeacdc` | BrowserEngine 加 page 池复用（懒加载，去掉 max_pages 信号量） |

### 🛠️ Nuitka/Termux 构建脚本（8 个提交，08-16）

| 提交 | 说明 |
|------|------|
| `e016189` | 修复 termux 构建脚本路径（目录重构遗留）+ 新增本地预装脚本 |
| `8d3bcd6` | 构建脚本复制 template 而非 app_data（防敏感字段泄露）+ 修 services 旧路径 |
| `96369dc` | 新增 `build-nuitka.sh`（Linux/termux 版 Nuitka 单文件构建） |
| `bce6a95` | 合并历史 build-web/build-termux 的 Termux 特殊处理 |
| `ffc88cf` | 补依赖安装 + portable 裸包自举 |
| `94fce10` | 补打包 shared 共享层（backend 依赖 shared.config/user_data） |
| `a574289` | Termux 产物生成 start.sh（onefile 动态 libpython 需 LD_LIBRARY_PATH） |
| `9a2ee9d` | 删掉 Termux 分支，只保留 Linux x64/arm64 |

### 🏷️ 版本号

| 提交 | 说明 |
|------|------|
| `6b3eb0f` | 版本号 4.3.0 → **4.4.0** 并更新 CHANGELOG |

### 🖥️ 前端 UI 修复（13 个提交，08-17）

| 提交 | 说明 |
|------|------|
| `7553e29` | DetailPage 章节状态 Tooltip 缺 TooltipProvider 包裹 |
| `6968916` | 章节对比模式标题加 min-w-0 截断 + 封面放大全黑背景锁滚动 |
| `f78fbee` | 设置页 Range 点击区域加大、API variant 空值 fallback、删导出格式启用按钮 |
| `b298c56` | 新增网页顶部全屏按钮（Fullscreen API，移动端 header + 桌面侧栏） |
| `f601f3b` | **回退**：移除全屏按钮（b298c56 撤回） |
| `4b385d5` | 书籍卡片喜欢按钮移左上角 + 下载完成提示音（Web Audio bell） |
| `af35753` | 书架列表封面返回缩略图（`Illustration.thumbnail` 等比缩小转 JPEG） |
| `61d8854`/`8744f6f` | 保存按钮移动端不被 bottom nav 遮挡（offset 加大到 bottom-20）+ 清理 notify 默认值字段 |
| `fce80d4` | 下载对话框 API 模式默认选中首个 variant，避免未选导致下载不启动 |
| `61a8c02` | 下载任务所有状态均可展开查看章节（含已完成/失败） |

## 里程碑

- **dev**（`f601f3b`，2026-08-17）：BrowserEngine 换 Playwright、全链路 async（downloader/task_manager/CLI/backend/书源）、`async_fetch_images` 图片批量下载、导出器契约重构、Nuitka 构建脚本、版本 **4.4.0**、前端移动端 UI 修复。
- **main**（`6b3eb0f`，2026-08-17）：dev 已合并至 **v4.4.0**（合并点 = 版本号提交 `6b3eb0f`，含 8-06/8-11/8-12/8-13 全部变更）；**dev 领先 main 10 个提交**（8-17 前端 UI 修复，`f601f3b` 等，尚未合并 main）。
- 本批变更后测试 **203 passed, 2 skipped**（新增 test_source_async / test_task_manager_async / test_exporter / test_engine_manager 等大量异步测试）。

## 文件变更统计

```
84 files changed, 2723 insertions(+), 736 deletions(-)
```

---

## 2026-08-20 变更（4 个提交）— 16 项体验清单落地

> 基准：`f601f3b`（2026-08-17）之后 dev 分支全部提交，4 条均于 2026-08-20，已推送 origin/dev。来源：用户 16 项待办清单（brainstorming 流程分 D/B/C/A/E 五组实施）。

### 提交时间线（倒序）

| 短哈希 | 提交消息 |
|--------|----------|
| `ad82893` | fix: 前端交互体验优化（书架/下载/详情/阅读/设置） |
| `198dd2c` | feat: 前端搜索体系升级（搜索历史/封面图/variant 校验） |
| `d36a975` | feat: 后端搜索历史 API 与搜索封面透传 |
| `3976668` | feat: Novel.serial 为 0 时自动跟随本地章节数（92xs 等无总数书源） |

### 按主题归纳

#### 🧩 Novel.serial 兜底（`3976668`）

| 提交 | 说明 |
|------|------|
| `3976668` | `Novel` 新增 `_serial_auto` 标记：serial=0（如 92xs）且带章节时进入自动模式，`update_chapter` 持续同步 `serial=len(chapters)`；显式非零 serial 不被覆盖。补 5 个用例 + 暂停测试时序修复（speed=0.05） |

#### 📚 搜索历史 API（`d36a975`）

| 提交 | 说明 |
|------|------|
| `d36a975` | 新增 `backend/routers/history.py`：`/api/v2/history/search` GET（按天分组：今天/昨天/M月D日/跨年加年份）POST（添加）DELETE（单条）；`shared/user_data.py` 新增 `delete_search_history`；`SearchResultData` 加 `cover_url` 并透传书源返回值；补 search_history 增查删测试 |

#### 🔍 前端搜索体系（`198dd2c`）

| 提交 | 说明 |
|------|------|
| `198dd2c` | 搜索历史面板（按天分组、垃圾桶删除模式、点击回填不自动搜、替代原 tips）；搜索结果封面缩略图（无封面降级放大镜）、评分移至作者行；API 模式未选 variant 抖动拦截（取消兜底）、variant 区独立成行修手机端错位；endpoints/hooks 新增 history 三件套 |

#### 🖥️ 前端交互体验（`ad82893`）

| 提交 | 说明 |
|------|------|
| `ad82893` | 书架：收藏空态保留切换按钮（可返回）、收藏入口移入三点菜单；下载管理：任务逆序、加载骨架、下载开始改 toast 不跳转、完成态可展开全部章节；详情：本地模式骨架统一、封面弹窗恢复半透明去缩放；阅读页回顶强化；设置：取消保存按钮改自动保存+toast、apikey 输入框样式；导航改 Link 保持 SPA 历史 |

### 里程碑

- **dev**（`ad82893`，2026-08-20）：16 项体验清单全部落地（D 组 #7 / B 组 #1/#2/#8/#13 / C 组 #1/#3/#5/#6 / A 组 #11/#14/#15 / E 组 #4/#10/#12）；#9 分组折叠按用户要求保持原状、#16 全屏按钮无残留。已推送 origin/dev。
- **main**：仍停在 `6b3eb0f`（v4.4.0），**dev 领先 main 14 个提交**（8-17 的 10 个 + 本批 4 个）。
- 本批变更后测试 **209 passed, 2 skipped**（新增 search_history 测试）。

## 文件变更统计

```
21 files changed, 482 insertions(+), 176 deletions(-)
```
