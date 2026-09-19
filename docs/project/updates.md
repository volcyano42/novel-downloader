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
---

## 2026-08-22 变更（15 个提交）

| 短哈希 | 提交消息 |
|--------|----------|
| `bf864af` | fix: 92xs 章节 id 从完整 URL 改为末尾数字段（修复前端路由/文件名兼容） |
| `7fb30a4` | fix: 章节 SSE 异常终止不再显示不完整章节数（区分 [DONE] 与错误，留空白） |
| `1e641b3` | fix: 详情页章节数省略号判断改用 loading\|\|streaming（本地书流式加载也会显示 ...） |
| `54d9768` | feat: 详情页章节数加载中显示省略号占位（.../N 章） |
| `b898cba` | feat: 详情页章节数在加载中显示省略号，完成后显示当前章节数 |
| `2a9fb00` | fix: test_source_contracts 断言兼容本地新增 appapi variant（子集断言，CI 无此目录亦通过） |
| `9e3e45b` | feat: user_data.db 空表模板加入 template/ 并接入 init_config 初始化 |
| `ef2b983` | fix: 迁移脚本补 groups/bookmarks 表更新并新增 hash 输入测试 |
| `5042e31` | refactor: 搜索框移除纯数字 id 平台猜测（hash id 非数字） |
| `35811a8` | refactor: 退役 ID_PATTERN/ORIGIN_ID_PATTERN/BOOK_URL_TEMPLATE（hash id 不可反查） |
| `2240f74` | refactor: 移除 get_source_for_id（resolve_chapter 走 url 回退） |
| `9d0dbf2` | refactor: 删除 4 个 source 手动拼 id（id 改由 resolve_meta 中心生成） |
| `5642bfe` | feat: resolve_meta 中心化生成 hash id 并冗余写入 extra.platform |
| `1de5ff3` | refactor: Novel.id 加默认值并移除 origin_id 属性（hash id 无前缀可去） |
| `a4b4a7d` | feat: 新增 canonical_book_url 与 make_novel_id（Novel.id hash 化工具） |

### 🆔 Novel.id hash 化（核心重构，8 个提交）

`Novel.id` 从「各 source 拼接平台前缀 + 源站 ID」改为「`sha256(canonical_book_url(novel.url, platform))[:32]`」中心化生成，彻底去掉前缀。

| 提交 | 说明 |
|------|------|
| `a4b4a7d` | 新增 `novelbase/utils/urls.py`：`canonical_book_url`（通用规范化 + 92xs/qidian 平台别名）+ `make_novel_id`（sha256[:32]），9 测试 |
| `1de5ff3` | `Novel.id` 加默认值 `""` 并删除 `origin_id` 属性（hash 无前缀可去） |
| `5642bfe` | `resolve_meta()` 中心化赋值 id + 冗余写入 `novel.extra["platform"]` |
| `9d0dbf2` | 4 个 source 删除手动拼 id（含连锁测试修复 test_source_async.py） |
| `2240f74` | `get_source_for_id` 退役，`resolve_chapter` 平台识别走 `get_source(chapter.url)` 回退 |
| `35811a8` | `ID_PATTERN`/`ORIGIN_ID_PATTERN`/`BOOK_URL_TEMPLATE` 三件套退役；`resolve_book_url` 仅接受 http(s)；backend `/sources`、cli、前端类型同步 |
| `5042e31` | 前端 SearchBar 移除纯数字 id 按位数猜平台 |
| `ef2b983` | 迁移脚本补 groups/bookmarks 表 + 新增 hash 输入测试（最终审查 2 Important 修复） |

**存量迁移**（2026-08-23 执行）：34 本 `.db` 重命名为 hash id，库内 `meta.id`/`illustrations.owner_id` 同步，`favorites`/`groups`/`bookmarks` 三表更新；5 个未下载书的幽灵条目经用户确认删除。迁移脚本 `novel-downloader-tools/scripts/migrate_novel_id.py`（含 rename 重试 + 先 rename 后 UPDATE + 显式 commit）。

### 🗄️ user_data.db 空表模板（1 个提交）

| 提交 | 说明 |
|------|------|
| `9e3e45b` | `template/storage/users/default/user_data.db` 空表模板（`shared/user_data.py` 提取 `_SCHEMA_SQL` 单一数据源）；`init_config.init_user_db()` 首次运行复制；测试 4 用例 |

### 🖥️ 前端章节数显示（4 个提交，方案收敛为 SSE 异常留空白）

| 提交 | 说明 |
|------|------|
| `b898cba`/`54d9768`/`1e641b3` | 省略号占位方案的三次迭代（加载中显示 .../N 章），最终废弃 |
| `7fb30a4` | 最终方案：`streamChapters` 区分正常完成（`data: [DONE]`）与异常终止（非 200/流中断/网络错走 `onError`）；`DetailPage` SSE 异常时章节数留空白，不显示不完整章节数 |

### 📄 92xs 章节 id（1 个提交）

| 提交 | 说明 |
|------|------|
| `bf864af` | 92xs 章节 id 从完整 URL（`http://www.92xs.info/html/96850/35632400.html`）改为末尾数字段（`35632400`），修复前端路由 `/novel/{id}/{chapterId}` 被 `/` 截断；存量 1698 个章节 id 已迁移 |

### 🧪 测试

| 提交 | 说明 |
|------|------|
| `2a9fb00` | `test_source_contracts` 断言改为子集（兼容本地新增 appapi variant，CI 无此目录亦通过） |

设计文档：`docs/superpowers/specs/2026-08-22-novel-id-hash-design.md`；实施计划：`docs/superpowers/plans/2026-08-22-novel-id-hash.md`。

---
---

## 2026-08-25 变更（BrowserOptions.auto_reconnect，4 个提交）

| 短哈希 | 提交消息 |
|--------|----------|
| `c30066c` | fix: 修复并发重建竞态与同步路径退化（锁内重建 + _fetch_with_page 区分路径） |
| `aab9b8a` | feat: auto_reconnect 配置透传（sites yaml + 显式引擎 API + CLI） |
| `527c800` | feat: BrowserEngine 支持浏览器失效自动重建（auto_reconnect） |
| `f5a4057` | feat: BrowserOptions 新增 auto_reconnect 字段（默认 False） |

### 🔄 浏览器自动重建（BrowserOptions.auto_reconnect）

browser 模式持久 Playwright 浏览器意外关闭（手关/崩溃/杀进程）时自动重建并重试当前抓取，避免直接 `NetworkError`。

| 提交 | 说明 |
|------|------|
| `f5a4057` | `BrowserOptions.auto_reconnect: bool = False`（默认关零退化）+ `set_browser_options` 透传 |
| `527c800` | `_is_reconnectable_error`（类名白名单 + 消息特征）/ `_reset_browser`（playwright.stop + close + 清 page 池）/ `_reconnect_browser`；`_fetch_with_page` 遇失效异常 raise；`async_fetch_text` 重建级重试（retry_times，耗尽 NetworkError） |
| `aab9b8a` | 配置透传：`BrowserOptionsData` + `engine_manager` 两处（sites yaml `auto_reconnect` / 显式引擎 `_build_options`）+ `cli/config.py` |
| `c30066c` | 最终审查 2 Important 修复：`_ensure_browser_locked` 拆分（`_reconnect_browser` 在 `_launch_lock` 内 reset+ensure，消除并发重建竞态）；`_fetch_with_page` 加 `abort_on_browser_close` 参数区分持久/isolated 路径（同步路径不退化） |

设计文档：`docs/superpowers/specs/2026-08-22-browser-auto-reconnect-design.md`；实施计划：`docs/superpowers/plans/2026-08-22-browser-auto-reconnect.md`。

---
---

## 2026-08-25 变更（交互式 CLI 还原 + 搜索历史 mode/variant，13 个提交）

### 🖥️ 交互式 CLI 还原（6 个提交）

| 短哈希 | 提交消息 |
|--------|----------|
| `034c633` | feat: 还原交互式 CLI 辅助层 cli/ui.py（去 box-drawing、无 ID 反查） |
| `23e8b5c` | feat: 还原交互式 CLI 通知模块 cli/notify.py |
| `bd14fbf` | feat: 还原交互式 CLI 设置/导出/删除菜单 cli/menus.py |
| `90a2aba` | feat: 还原交互式 CLI 主循环 cli/interactive.py（适配 async/新 API） |
| `0911044` | feat: 还原交互式 CLI 入口 main.py |
| `1e15cb4` | fix: 交互式搜索关键词路径捕获 search 异常 |

还原 2026-08-02 删除的交互式 CLI（`2c717f7`）：

- **入口**：根目录 `main.py`（5 行）委托 `cli.interactive.main()`
- **文件布局**：交互层并入 `cli/` 包（`interactive.py` 主循环 + `menus.py` 子菜单 + `ui.py` 辅助 + `notify.py` 通知），**不重建** `app/` 包；`cli/main.py`（非交互 argparse）、`cli/core.py`、`cli/config.py` 零改动，两入口并存
- **novelbase 适配**：`resolve_meta`/`resolve_chapter_list`/`resolve_chapter`/`search` 均 async，同步主循环经 `asyncio.run()` 包装；`_platform_from_url` 改数据驱动（`novelbase.source.platform_from_url`）；`register_source`/`register_export_options` 新导入路径；删除 `_build_url_from_id`（id_pattern 已退役，hash id 不可反查）
- **去方框**：主菜单 `┌─┐│├┤└┘` 方框、`───` 标题线、注释分隔符全部 box-drawing 装饰去除，改纯文字样式（rich 进度条保留）
- 更新支持单选/全部：单选走 `interactive._update_one_async`，全部复用 `cli.core.do_update`
- 测试：`tests/test_interactive_cli.py`（TestUi 21 / TestNotify 6 / TestMenus 4 / TestInteractive 6，共 36 用例）

设计文档：`docs/superpowers/specs/2026-08-25-restore-interactive-cli-design.md`；实施计划：`docs/superpowers/plans/2026-08-25-restore-interactive-cli.md`。

### 🔍 搜索历史 mode/variant 链路（7 个提交）

| 短哈希 | 提交消息 |
|--------|----------|
| `6828bb8` | fix: search_history 迁移加 PRAGMA user_version 一次性守卫，避免重复执行改写新数据 |
| `736b9a4` | feat: 前端搜索历史链路传递 mode/variant（记录 + 回填 + 面板回传） |
| `fe1ff53` | feat: 搜索历史路由透传 mode/variant 字段 |
| `9b9988f` | feat: 搜索历史回填恢复 mode/variant，mode 为空默认 requests |
| `1ce034b` | feat: 搜索历史面板展示 mode/variant 徽标 |
| `9952fa6` | docs: CHANGELOG 记录搜索历史去重 + mode/variant 字段功能 |

搜索历史记录/回填完整携带 `mode`/`variant` 字段：记录搜索时保存，回填时恢复原搜索模式与 variant（mode 为空默认 `requests`）；历史面板展示 mode/variant 徽标；迁移加 `PRAGMA user_version` 一次性守卫防止重复执行改写新数据。

## 2026-08-25 晚间变更（sites 配置 variant 感知 + CLI variant 选择，6 个提交）

### 🧩 sites 配置 variant 感知（5 个提交）

| 短哈希 | 提交消息 |
|--------|----------|
| `9216bfd` | feat: shared.config 新增 variant 感知辅助（get_mode_variant_config/load_mode_config/mode_variants），find_variant_options 跨 mode 查找 |
| `b5e4287` | feat: sites 配置 browser/requests 嵌套 default variant 层（template 4 平台） |
| `5255d43` | refactor: CLI 配置读取改 variant 感知（build_options/交互菜单读写 default variant） |
| `ad90aab` | refactor: backend 引擎创建与 config 路由改 variant 感知（sites 配置嵌套 default） |
| `3f7d0aa` | feat: 前端设置页适配 sites 配置嵌套 variant（browser/requests 读写 default） |

sites 配置统一为「mode → variant → 配置」三层：browser/requests 嵌套 `default` 层（如 `browser.default.headless`），api 的每个 provider（`oiapi`/`rain`）即 variant。shared.config 提供 variant 感知辅助；CLI/backend/前端设置页均改为 variant 感知读写。

### 🎯 CLI 双入口 variant 选择（1 个提交）

| 短哈希 | 提交消息 |
|--------|----------|
| `c06c46e` | feat: CLI 双入口支持 variant 选择（交互询问/非交互提示 --variant） |

variant 选择规则（所有模式一致）：某模式只有一个 variant 时自动使用（browser/requests 未指定默认 `default`）；多于一个时——交互式 `main.py` 弹出菜单询问并会话级记住 `(platform, mode)`；非交互 `cli.py` 的 `search`/`download`/`update`/`info` 新增 `--variant` 参数，未指定时列出所有 variant 名称并提示后以退出码 2 退出。
