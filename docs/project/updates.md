# 更新记录 — v4.2.3（9a51b561）之后

> 基准：tag v4.2.3 = commit `9a51b561`（main 分支）。
> 本文按**日期分节**记录 dev 分支在此之后的变更：先是 2026-08-02 那批 21 个非合并提交（提交时间线 + 主题归纳），
> 再往下按日期追加后续批次（最新在最下方）。面向发布的跨版本汇总见仓库根 `CHANGELOG.md`。

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


---

## 2026-09-24 Android APK 构建打通（`build-apk` 首次成功）

> 背景：`build-apk.yml` 自 2026-08-02 落地起**从未成功跑过一次**（两库历史 run 数均为 0）。2026-09-19~24 逐层剥开 8 处阻塞后，公开库 `novel-crawler` 的 build-apk 首次构建成功：run `35975357459` → `success`，artifact `novel-crawler-apk-dev`（≈28.6 MB，未签名）。

### 阻塞链（按暴露顺序）

| # | 层 | 现象 | 修复 |
|---|----|------|------|
| 1 | Gradle KTS | 用 `#` 当注释（Kotlin 只能 `//`）→ `Script compilation errors: 19 errors` | 改为 `//` |
| 2 | Chaquopy API | `pip { exclude("x") }` —— Chaquopy 的 `pip` 块只有 `install`/`options`，**没有 `exclude`** → `Unresolved reference` | 改由 `build-apk.sh` 生成预过滤清单 `android/.req-android.txt` |
| 3 | Gradle KTS | `java.util.Properties()`：KTS 里 `java` 被解析为 `Project.java` 扩展而非包名 → `Unresolved reference: util` | `import java.util.Properties` + `Properties()` |
| 4 | Chaquopy wheel | `lxml`/`PyYAML` 的 cp311 wheel 只有 `android_24` tag，app `minSdk=21` → pip 回退 PyPI sdist → 编译失败（缺 libxml2/libxslt） | `minSdk 21 → 24` |
| 5 | 依赖冲突 | `fastapi 0.141.1` 要求 `pydantic>=2.9`，与第 4 步引入的 `pydantic<2` 冲突 | pin `fastapi==0.120.0` |
| 6 | Kotlin | `Python.start(ServerService::class.java, "server")` —— Chaquopy 只接受 `Python.Platform`，且模块不会以 `__main__` 方式执行 | `Python.start(AndroidPlatform(this@ServerService))` + `getModule("server").callAttr("_start")` |
| 7 | Kotlin | `this@healthPoll`（标签不存在） | 直接引用 `healthPoll` 字段 |
| 8 | Kotlin | 显式标注 `healthPoll: Runnable` 后又触发「属性初始化表达式自引用」 | `run()` 内改用 `this`（匿名 Runnable 自身） |

### 关键结论

- **Chaquopy wheel tag 规则**：pip 只接受 tag ≤ app `minSdk` 的 wheel；`android_24` 的包在 `minSdk=21` 下匹配不上，会回退 sdist 源码编译（Android 上必然失败）。Chaquopy 17.0 已把 **24 定为官方最低要求**（24 也是其 build-wheel 默认 API level）。
- **pydantic v2 在 Android 上不可用**：`pydantic-core` 是 Rust 扩展、PyPI 无 Android wheel，ChaquoPy 官方建议装 `pydantic<2`（v1 纯 Python）。为此 `backend/schemas/export_config.py` 做了 **v1/v2 双兼容**（`field_validator`/`model_config` ↔ `validator`/`class Config`），桌面端行为不变（v1.10.26 与 v2.13.4 两端实测一致）。
- **public 仓库没有 `pyproject.toml`**（`PUBLIC_MANIFEST.md` 规定 public 自维护版本元数据），而 `android/app/build.gradle.kts` 里 `install("file:../..")` 需要它 → 公开库必然报 `Directory '.' is not installable`。改为由 `build-apk.sh` 复制 `novelbase/` 源码进 `src/main/python/`（与 `backend/`、`shared/` 同法）。
  > **2026-09-26 修正**：这与「有 `pyproject.toml` 的仓库」最终走同一条路。本仓库（**有** `pyproject.toml`）用 `install("file:../..")` 同样必然失败 —— pip 会解析 `dependencies` 里的 `playwright`（被清单刻意排除、Chaquopy 仓库无 wheel）→ `No matching distribution found for playwright`。**两个仓库现在都改由 `build-apk.sh` 复制 `novelbase/` 源码**，见本文 2026-09-26 节与 `docs/build/android-apk.md`。
- **Android 依赖清单在 `build-apk.sh` 第 1b 步生成**：排除 `playwright`/`psutil`/`pillow-heif`（Chaquopy 仓库无 wheel），pin `lxml==5.3.0`、`Pillow==11.0.0`、`yarl==1.9.3`、`PyYAML==6.0.3`、`fastapi==0.120.0`，`uvicorn[standard]` → `uvicorn`（去 C/Rust extras），追加 `pydantic<2`。

### 遗留

- APK **未签名**（未配置 `KEYSTORE_BASE64`/`KEYSTORE_PASSWORD`/`KEY_ALIAS`/`KEY_PASSWORD` secrets）→ 仅可用于侧载测试；产物名跟随 `inputs.version`（不传则为 `-dev`）。
- **真机启动未验证**（Chaquopy 首次解压 → uvicorn 起服务 → WebView 加载）；**私有库未触发构建验证**（代码已同步修复）。
- `buildPython 3.12.3` 与 app Python 3.11 不匹配 → `.pyc` 预编译被跳过（仅警告，运行时可解释执行）。
- APK 内 `versionName` 仍是 gradle 硬编码（public `1.0.1` / private `1.0.0`），未与项目版本联动。

---

## 2026-09-24 变更（Novel.id 改 sha256(url) + 书源扁平化 core）

- `Novel.id` 由各书源手工拼接平台前缀改为中心化生成 `sha256(url)[:32]`；库内 `meta.id` 存书源返回的 url 原样
- 书源目录扁平化：四层 `{platform}/{mode}/{variant}/` → 一层目录 + `source.json`（`source_name` / `enabled` / `common` / `default_config`）
- 退役 `platform` / `SHOW_NAME` / `HOSTS` / `NAME` / `variant` / `register_source()` / `platform_from_url()` / `canonical_book_url()` / `ID_PATTERN` 等符号；`novelbase/source.py` 只暴露 `list_sources` / `get_manifest` / `capabilities` / `resolve` / `resolve_book_url`
- 设计：`docs/superpowers/specs/2026-09-24-book-source-flattening-design.md`；计划：`docs/superpowers/plans/2026-09-24-source-flattening-core.md`

## 2026-09-25 变更（扁平化遗留改造 + 收尾）

- 契约收口 15 任务：backend / CLI / 前端 / 配置全部改到 `source_name` 维度（`--source` Query；`/download/sources` 新形状；`/config/sources/{name}` 三层合并；前端去 mode/variant 选择器 + 新增书源管理页 `/sources`）
- 删除失去基础的端点/入口：`/api/v2/download/platform`、`POST /download/detect`、`/api/v2/engine*`、CLI `do_visit_site`
- 搜索历史改 `(source_name, keyword)` 唯一键；`enabled` 用户层覆盖落地为 `sites/{source_name}.yaml` 顶层
- 收尾：未知 `source_name` 统一 404、前端书源配置表单去重 + `enabled` 双向失效修复、CLI 引擎按 mode 解析、脚手架 `common` 与出厂默认同源、docs 位置归一
- 设计：`docs/superpowers/specs/2026-09-25-source-flattening-followup-design.md`、`docs/superpowers/specs/2026-09-25-flattening-closeout-design.md`

## 2026-09-25 变更（来源读点 + mode 用户覆盖 + 前端整合）

- **来源读点**：`GET /storage/novel`（列表）与 `GET /storage/novel/{id}/meta` 返回 `source_name`（源 `user_data.novel_sources`）；书架卡片以来源替掉 novelId 小字行、详情页显示来源，详情页「检查更新 / 下载选中」默认用该书来源
- **mode 用户覆盖**（约定反转）：书源 `source.json` 声明为**默认**，用户可在 `sites/{source_name}.yaml` **逐能力覆盖** `{cap}.mode`；唯一入口 `shared.config.effective_capabilities()`（非法值忽略回退声明、`null` 恢复声明）；core `novelbase/core/downloader.py` 四个分发函数新增可选 `mode_overrides`（能力名 → mode）由调用方（backend 路由/`task_manager`、CLI）关键字透传，`capabilities()` / `resolve()` 语义不变
- **API**：`GET /api/v2/config/sources/{name}` 增返 `declared_capabilities`（`capabilities` 改为**有效 mode**）；`PUT` 传 `config[cap].mode = null` 即删除覆盖、恢复声明
- **前端整合**：书源管理并入设置页（每源一个折叠条，展开可编辑能力字段 + mode 下拉 + 「恢复默认」），`/sources` 改为重定向 `/settings`、侧边栏去「书源」入口；`headers` 字段改 `json` 类型控件（不再显示 `[object Object]`，写回为 JSON 对象）
- **CLI**：删书（`cmd_delete` / 交互式 `do_delete`）会清理 `novel_sources`
- 测试：`python -m pytest tests -q` = **444 passed, 1 skipped**；前端 `npx tsc -b` = 0 错
- 设计：`docs/superpowers/specs/2026-09-25-source-reads-mode-override-design.md`；计划：`docs/superpowers/plans/2026-09-25-source-reads-mode-override.md`

## 2026-09-25 变更（详情页换源）

- **详情页那一行**：`novelId` 行改为「书源名 + 换源按钮」（深灰字/浅灰底）；书源名取本地 `source_name` 或远端 `state.source`，无记录时显示「未记录书源」
- **换源弹窗**：新建 `SourcePickerDialog`（结构照搬原 `DownloadDialog`），列出全部书源，当前书源条目右侧标「当前」；确定按钮在请求 pending 时 `disabled` 并显示「保存中…」
- **两个操作不再弹窗**：详情页「检查更新 / 下载选中」直接沿用该书书源执行；无来源时 toast 提示「请先点旁边「换源」选定书源」、不发请求
- **未下载的书也能先换源**：后端**不校验**小说是否已入库（来源独立于 storage，「先换源、再下载」合法）；换源成功后前端用本地 `sourceOverride` **立即**反映新书源（远端/未下载书无 `localMeta` 可刷新）
- **删除 `DownloadDialog`**：改造后无使用处，文件删除
- **API**：新增 `PUT /api/v2/storage/novel/{id}/source`（body `{source_name}`；未知书源 404，不校验已入库），落库到 `user_data.novel_sources`（UPSERT），前端失效 `["novel-meta", id]` / `["novels"]`
- **下载管理条目新增书源与下载时间**：`create_task` 记录 `created_at`，`list_tasks` 透出 `source_name`/`created_at`，下载任务项在书名下方显示「书源名 · 下载时间」小字
- 测试：`python -m pytest tests -q` = **449 passed, 1 skipped**；前端 `npx tsc -b` 0 错、`npm run lint` 0 告警
- 设计：`docs/superpowers/specs/2026-09-25-detail-source-switch-design.md`

## 2026-09-25 变更（下载并发模型重做）

- **`max_workers` 语义反转**：不再表示「任务内章节并发」，改为「**最多同时运行的下载任务数**」（`download.max_workers`，默认 3）；超额任务进 `status="queued"`（前端「排队中」），拿到额度才转 `downloading`；排队中暂停**不占任务槽**（`resume` 后才抢额度）；下调该值最多 1 秒生效（TTL 缓存，仅影响之后排队/启动的任务）。设置页并发标签 →「**最大下载任务数**」（原「并发线程数」口径）
- **新增书源级 `concurrency`**（默认 1，可配）：`source.json` 顶层可选字段 + 用户层 `sites/{name}.yaml` **顶层**覆盖（与 `enabled` 同级），语义为「该书源同时最多几个请求在飞，**跨任务共享**」；读取入口 `shared.config.source_concurrency()`（非正整数忽略回退 1）；约束任务内 `resolve_meta` 与每章 `resolve_chapter` 的请求；`GET /api/v2/config/sources/{name}` 返回有效值、`PUT` 支持顶层写入，前端书源折叠条加「并发数」输入
- **`delay` 出厂默认 `[3,5]` → `[0, 0]`**（不设置 = 不限速）：10 个 `novelbase/sources/*/source.json` 的 `common.delay` 与代码兜底（`shared/config.py`、`backend/services/engine_manager.py`、`novelbase/core/options.py` 的 dataclass 默认）同步；用户层显式值仍优先（**历史写入过 `delay` 的老用户**——旧版 `sites/*.yaml` 里已写入的 `[3,5]` 会继续覆盖新出厂默认，属三层合并语义的正常结果；当前出厂层与模板已不再写 `delay`，全新安装不受影响）
- **用户层模板精简**：`template/config/sites/*.yaml` 只留必要字段（非 api 源仅 `enabled`；api 类源为 `enabled` + 四个能力段各 `key: ''`）
- **CLI**：章节并发上限改为 `min(max_workers, source_concurrency(source_name))`，默认 `concurrency=1` 下即**单章串行**（提速靠 `delay=0`）；`cli/main.py --workers`、`cli/menus.py` 文案改为「并行章节数（受书源并发额度约束）」
- **已知边界**（如实写明）：① 已是 `downloading` 的任务被暂停仍占任务槽；② 独立路由（检查更新 `GET /storage/novel/{id}/chapters`、搜索、远端章节列表）**不经**书源额度；③ `max_workers` 下调最多 1 秒生效（TTL 缓存）
- 测试：`python -m pytest tests -q` = **471 passed, 1 skipped**；前端 `npx tsc -b` 0 错、`npm run lint`（oxlint）0 告警
- 设计：`docs/superpowers/specs/2026-09-25-download-concurrency-design.md`

## 2026-09-26 变更（Android 套壳前端交付 + 环境能力表 + APK 构建修复）

> 触发：真机装 APK 后 WebView 显示后端的「前端尚未构建」占位页。排查发现这不是单个 bug ——「APK 内前端资源如何交付给后端」这一机制从未被验证过（CI 全绿、真机白页）。

### 前端交付（修白页）

- **根因 1（层级）**：`build-apk.sh` 把 `frontend/dist/*` 复制到 `src/main/python/frontend/`（少了 `dist` 层），而 `backend/main.py` 的 `_find_frontend_dist()` 只认 `frontend/dist` → `_frontend=None` → 占位页
- **根因 2（机制）**：Chaquopy 把 `src/main/python/` 打成 APK 资产，其中数据文件**不是真实目录**（`os.listdir`/`os.scandir` 不可用）→ `StaticFiles` 的「真实目录」假设不成立；`server.py` 里注册在 SPA catch-all 之后的根挂载是**永不命中的死代码**，而 `tests/test_android_server.py` 只断言「mount 存在」→ 掩盖了问题
- **改法**：构建期把 `frontend/dist` 打成 `frontend.zip` 随 APK 资产分发；`server.py` 新增 `_extract_frontend()`，在 `import backend.main` **之前**解压到 `$HOME/frontend/dist`（`HOME` 缺失回退 `NLD_APP_DATA/.frontend/dist`；sha256 标记幂等 + zip-slip 防护；失败只打日志并回落占位页），经 `NLD_FRONTEND_DIR` 交给 SPA fallback；`backend/main.py` 的候选列表抽为 `_frontend_candidates()`，第一候选即该 env（其余候选与顺序不变 → 桌面/portable/Nuitka 零变化）；删除死挂载与 `assets/frontend` 旧路径
- **测试**：`tests/test_android_server.py` 重写——删除「只断言 mount 存在」的用例，改为止端到端断言（`httpx.ASGITransport`：`/` 必须返回前端 index.html 而非占位页、`/assets/*` 200、SPA 路由回 index.html、`/api/v2/health` 200）+ zip 解压幂等、zip-slip、候选全落空等用例

### 环境能力表：Android 不支持 browser

- APK 构建时排除 `playwright`（Chaquopy 无浏览器内核）→ 本环境无 `browser` 引擎；此前**没有任何一层知道**这件事：3 个 browser 书源出厂 `enabled=true`，会被 `enabled_source_names()` 收进搜索并发
- `NLD_PLATFORM=android`（`server.py` 注入）→ `shared.config.supported_modes()` = `(requests, api)`，**全链唯一真源**（桌面/portable/Nuitka 未设该 env → 全量，行为逐字不变）
- `effective_capabilities()` 的覆盖判定改用 `supported_modes()`：本环境不支持的 `{cap}.mode` 覆盖被**忽略并回退书源声明**（用户 yaml 不动，回桌面版自动生效）
- 新增 `available_capabilities()` / `is_source_available()`（**源级全能力**判定，避免混 mode 私有源「半可用」踩到执行路径）；`enabled_source_names()` 追加可用性过滤
- API：`GET /download/sources` 与 `GET /config/sources/{name}` 带 `available`（前者仍**全量**返回，供前端置灰）；新增 `GET /config/environment`；`PUT` 启用不可用源或覆盖成不可用 mode → 400（校验先于落盘，整体拒绝）；执行入口经 `source_guard.require_available_source()`（沿用「HTTP 边界唯一校验点」）
- core：新增 `ModeUnavailableError`，`engine._async_playwright()` 在依赖缺失时抛它（而非裸 `ImportError`）；core **不读环境变量**（保持纯库边界）
- 前端：browser 源折叠条置灰 + 标注「本环境不支持 browser」+ 禁用启用开关（仍列出）；`toSourceOptions()` 滤掉 `available=false`（搜索 / 换源 `SourcePickerDialog` / 书架共用）；`SourceConfigEditor` 的 mode 下拉只列 `supported_modes`（新增 `useEnvironment()`）；`Toggle` 支持 `disabled`
- 测试：新增 `tests/test_source_availability.py`（环境声明三态、覆盖回退、可用性与启用集、API available/400/environment、core 兜底）；`tests/conftest.py` 增 autouse fixture 隔离 `NLD_*`（`server.py` 直接写 `os.environ` 的键不受 monkeypatch 管理，曾把 `NLD_PLATFORM=android` 泄漏给桌面用例）
- 设计：`docs/superpowers/specs/2026-09-26-android-shell-no-browser-design.md`

### APK 构建修复（本仓库首次构建成功）

- run `36240609118` 失败在 `:app:generateReleasePythonRequirements`：`No matching distribution found for playwright (from novelbase==4.4.1)` —— `install("file:../..")` 让 pip 解析 novelbase 的 `dependencies`，而 `playwright` 正是被清单刻意排除的包
- 改为与 `backend/`、`shared/` 同法：`build-apk.sh` 复制 `../novelbase` 源码进 `src/main/python/`，`build.gradle.kts` 删除 `install("file:../..")`；依赖仍由 `.req-android.txt` 提供（与 `pyproject.toml` 的 `dependencies` 同源，已核对覆盖一致）
- 结果：run `36240821327` **success**，artifact `novel-downloader-apk-4.5.0`（≈28.6 MB，未签名）
- 本机等价演练（只把「APK 内运行时目录」加入 `sys.path` 后导入 `server`）：`/` 返回真实前端、SPA 与 assets 正常、`platform=android`、browser 源 `available=False`

### 版本号

- `pyproject.toml` / `novelbase/__init__.py`：4.4.1 → **4.5.0**（并对外导出 `ModeUnavailableError`）；`CHANGELOG.md` 的 `## Unreleased（书源扁平化收口）` 升级为正式 `## v4.5.0` 段落
- 测试：`python -m pytest tests -q` = **507 passed, 0 failed**；前端 `npx tsc -b` 0 错、`npm run lint`（oxlint）0 告警

### 遗留（需真机确认）

- APK 未签名（仅可侧载）；真机链路（`HOME` 可写 / 解压 / WebView 显示 / browser 源置灰）未验证
- **真机上 novelbase 的书源目录遍历仍是未知点**：`list_sources()` 需枚举 `sources/{dir}/source.json`，而 Chaquopy 资产不支持目录列举（与前端白页同一类根因，尚未被真机暴露）
- APK 内 `versionName` 仍为 gradle 硬编码 `1.0.0`（独立遗留）
