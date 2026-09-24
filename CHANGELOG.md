# 更新日志

## Unreleased（书源扁平化收口）

> 2026-09-25 dev 分支：书源模型从「四层目录（platform/mode/variant）+ registry 硬编码兜底」
> 扁平化为「一层目录 + `source.json`」，backend / CLI / 前端 / 配置全面改到 `source_name` 维度。
> 本条为**未发布**变更汇总，发布时另起 `## v{版本}` 段落。

### 变更

1. **书源扁平化为一层 + `source.json`** — `novelbase/sources/{dir}/` 一层目录，每源含 `__init__.py` + `source.json`（`source_name`/`enabled`/`common`/`default_config`）+ 4 个能力文件；`platform` / `SHOW_NAME` / `HOSTS` / `NAME` / `variant` / `register_source()` / `platform_from_url()` / `canonical_book_url()` 全部移除。`novelbase/source.py` 只暴露 `list_sources` / `get_manifest` / `capabilities(source_name) -> {capability: mode}` / `resolve(source_name, capability) -> (fn, mode)`
2. **CLI 参数改按书源** — `--platform/--mode/--variant` 改为 `--source`（`source_name`）；`search` 省略 `--source` 时并发全部启用书源；`dev new-source` 生成新一层结构并默认写 `sites/{source_name}.yaml`（`--no-config` 跳过）；`dev new-variant` 与 `do_visit_site`（访问平台）删除
3. **删除废弃路由** — `/api/v2/download/platform`、`/api/v2/download/detect`、`/api/v2/engine` 删除；下载路由统一以 `source` Query 表达书源，`source` 为空 = 并发全部启用书源
4. **配置改按书源 + 三层合并** — 逐书源配置改为 `sites/{source_name}.yaml`（顶层 `enabled` 覆盖 `source.json` 出厂值），三层合并由 `shared.config.merged_source_config()` 提供；新增 `/api/v2/config/sources/{source_name}`（GET 三层合并 / PUT 只写用户层）；全局 `mode` 设置项删除
5. **前端删除 mode/variant 两级选择器** — 搜索改「已启用书源并发」，URL 解析改「手选书源」；新增**书源管理页** `/sources`（按书源编辑，含 `enabled` 开关）
6. **Novel.id 改 `sha256(url)[:32]`** — 取代旧的 `hash(canonical url)`；库内 `meta.id` 存书源返回的 url 原样；不再做 url 规范化（92xs/qidian 平台特例随 core 站点知识一并删除）
7. **`storage` 段成为死配置** — 实现恒取 `shared.config.get_database_url()`，`config.yaml` 的 `storage.backend` / `storage.database_url` 不再生效（模板保留仅为兼容旧文件）

### 不迁移

- `sites/{platform}.yaml`（`fanqie.yaml` / `qidian.yaml` / `qimao.yaml` / `92xs.yaml`）与旧的 `search_history`（platform/mode/variant 维度）**不做迁移**，用户按新 `source_name` 重新配置、历史重新积累

## v4.4.1

### 修复

1. **前端 hooks 依赖缺陷** — `DownloadDialog` 初始化 effect 依赖每次渲染都重建的 `visibleModes`/`variantsByMode`，父组件重渲染会把刚选中的模式重置回初始值（点 API 后界面闪回 browser）：改为仅在对话框打开时同步一次。`BookCard` 导出文件名 `useCallback` 缺 `title` 依赖；`DetailPage` 章节流 effect 缺 `isRemote` 依赖；`SearchBar` URL 模式漏 `urlHideApi` 依赖
2. **`build-nuitka.sh` Linux 构建修正** — 去掉 `--static-libpython=yes`（标准发行版 Python 无静态 libpython，该参数在 Linux 必失败；onefile 会自动打包动态库），并补 `patchelf` 预检与安装提示
3. **构建脚本/workflow 适配 `scripts/` 目录** — `build-portable.ps1` 改用 `$PROJECT_ROOT`（`$PSScriptRoot/..`）解析仓库根与 `dist/`；`build-windows.yml`、`build-linux-x64.yml`、`build-linux-arm64.yml` 的脚本调用补 `scripts/` 前缀

### 重构

1. **workflow 分层：Windows portable 与 Nuitka 拆开** — Nuitka onefile 从 `build-windows.yml` 拆出为独立 `build-windows-nuitka.yml`（仅 `workflow_dispatch` 手动触发），`build-windows.yml` 只保留 portable；两种产物不再共用一个 workflow。`build-dist.yml` 行为不变（仍是一键全平台 portable）
2. **迁移校验唯一数据源** — 非迁移文件清单改由私有仓库 `pyproject.toml` 的 `[tool.novel-downloader.migration] exclude` 提供，`check_public.py` 不再硬编码排除项，并移除版本一致性防线（public 版本号自维护、`pyproject.toml` 不再迁移）；`PUBLIC_MANIFEST.md` 同步
3. **前端非组件导出拆分** — 拆出 `toast-context.ts` 与 `button-variants.ts`，修复 Vite Fast Refresh 失效（改该文件时整页刷新而非热更新）

### 变更

1. **文档维护边界** — 私有仓库不再维护 `README.md`/`CONTRIBUTING.md`/`docs/add_source.md`（由公开仓库 `novel-crawler` 维护），`pyproject.toml` 同步去掉 `readme` 声明；`cli.py`/`cli/interactive.py` 文案与公开仓库对齐
2. **删除遗留 PyPI 上传脚本** `build-pypi.ps1`/`build-pypi.sh`

## v4.4.0

### 新增

1. **全链路异步化** — 引擎、下载器、书源、CLI、task_manager 全面改为 asyncio 原生：`async_fetch_text/json/images` 抽象方法贯穿三引擎，downloader 四函数（search/resolve_meta/resolve_chapter_list/resolve_chapter）改 async，fanqie/qidian/qimao/92xs 书源 async 化，backend 路由直接 await，CLI 下载改 `asyncio.run` + `asyncio.gather`
2. **Playwright 替换 DrissionPage** — browser 模式改用 Playwright 原生 async（懒启动 + 真异步，去 `asyncio.to_thread` 假异步），统一内置 chromium（`playwright install chromium`，不依赖系统 Chrome）；BrowserEngine 加 page 池复用（懒加载，省每次 new_page/close 的 CDP 往返），qidian/qimao 书源交互改 Playwright API
3. **`async_fetch_images` 批量图片下载** — 三引擎统一实现；browser 模式用 httpx 直抓（不开 tab），requests/api 用 `httpx.AsyncClient` + `asyncio.Semaphore`；书源封面/插图下载归 engine
4. **导出器插件化** — 导出器改为动态发现（扫描 exporters/ + `NLD_PRIVATE_EXPORTERS` 外部目录，外部同格式覆盖内置），新增契约校验（Protocol + 运行时签名校验）与 `list_exporter_formats()`；registry.py 改名 exporter.py 上提 novelbase 根目录
5. **`NLD_PRIVATE_SOURCES` 外部私有书源** — 支持通过环境变量注入私有书源目录，敏感代码与核心库隔离
6. **收藏功能 + 分组迁 SQLite** — groups 从 YAML 迁移到 SQLite（`user_data.db`），新增收藏 API；共享层 `shared/`（config 单一数据源 + user_data 归位），backend/cli 均依赖 shared 而非互调
7. **下载管理面板折叠章节队列** — 前端下载任务改为折叠面板，逐章实时进度 + 取消真正生效
8. **`build-nuitka.sh`（Linux/Termux 版）** — 与 Windows build-nuitka.ps1 对应；Termux 分支后续移除（portable 替代）
9. **搜索历史去重 + mode/variant 字段** — 搜索历史以 `(platform, keyword, mode, variant)` 为唯一键去重（重复搜索更新时间为最新，不新增行）；新增 `mode`/`variant` 列并自动迁移旧库（fanqie 旧记录标 `api`/`rain`，其余平台留空）；历史面板展示 mode/variant 徽标，点击历史回填完整恢复搜索条件（mode 为空时默认 requests）

### 重构

1. **目录结构重构** — `services/backend` → `backend/`、`services/frontend` → `frontend/`、`cli.py + cli_lib` → `cli/`，新增 `shared/` 共享层，构建脚本收纳进 `scripts/`
2. **HTTP 层 requests → httpx** — 三引擎同步 httpx.Client + 异步 httpx.AsyncClient 双接口，书源 requests 全量替换，新增 `detect_encoding`（chardet 替代 apparent_encoding）
3. **书源注册去硬编码** — 注册发现机制改为目录扫描 + manifest（Nuitka 模式），source 函数归一 `novelbase.source`
4. **provider 重命名 variant** — 单实现模式占位改用 default，移除 API variant 的 enabled 字段
5. **BrowserEngine page 池复用** — 懒加载复用 page，并发限流由下载器 Semaphore 负责

### 变更

1. **httpx 提升主依赖** — 移除 requests/urllib3，编码探测改用 chardet
2. **恢复 Nuitka 打包方案** — 4.1.3 锁版本，与 portable 共存
3. **app_data/ 脱离 git 跟踪** — 磁盘保留，不再入库
4. **构建产物 artifact 加 retention-days:3** — 防止私有仓库配额溢出
5. **Windows portable 删 ChromeSetup.exe** — 统一 `playwright install chromium`，不再依赖系统 Chrome

### 修复

1. **engine close() 泄漏** — 新增 `Engine.aclose()` 异步关闭，shutdown 时 await 彻底释放浏览器进程；async_fetch_json 补 NetworkError 包装
2. **task_manager 暂停失效** — 修复 `asyncio.Event.wait()` 反用 + 排队/收尾检查点，暂停真正生效
3. **engine_manager 并发竞态** — 缓存操作加 threading.Lock（double-checked），消除并发双创建
4. **DetailPage 章节状态 Tooltip** — 补 TooltipProvider 包裹，修复检查更新后渲染报错
5. **下载进度条** — 逐章实时推进 + engine 同步创建移出事件循环
6. **前端 TypeScript 语法** — variant 缺符号、TooltipVariant 不存在、DownloadDialog 参数重名
7. **Nuitka onefile 前端资源定位** — 改用 `__file__` 目录，修复 exe 访问 404
8. **CLI 存储路径与 backend 不一致** — `cli.core._get_storage` 与 `cli.config.build_options` 硬编码 `sqlite:///app_data/storage/novels.db`（父目录），扫不到 `app_data/storage/novels/` 下的小说，交互式菜单"更新已有小说"误报"没有已下载的小说"；改为与 backend 统一使用 `shared.config.get_database_url()`，并修正 template/config 的 `storage.database_url`
9. **搜索失败自动重试导致重复请求** — 搜索请求配置 `retry: 1`，不支持的平台/模式组合（如 qidian requests 搜索）返回 500 后自动重试一次，后端日志出现两条相同请求；改为搜索 `retry: 0`（用户主动操作失败不重试），后端将 `FeatureNotSupportedError` 转为 400 友好提示，前端搜索区展示真实错误信息（替代误导性的"未找到相关小说"）
10. **搜索历史回填残留旧 variant** — 点击历史条目回填时，历史 `variant` 为空不重置 state，残留上一次选择的变体（如 fanqie api 的 `rain`），导致回填后搜索记录 `browser` 模式 + `rain` 变体的不匹配历史（如 qidian/browser/rain）；改为回填时始终同步 variant（空则清空）
8. **便携版 Ctrl+C 退出** — Windows 去 pause、Linux/Termux 加 trap 清理

### 说明

- FastAPI `version="2.0.0"`（backend/main.py）为独立 API 版本，与项目版本 4.4.0 分属不同命名空间，非矛盾

### 补充（2026-08-20，16 项体验清单）

**新增**
1. **搜索历史** — 后端 `/api/v2/history/search`（GET 按天分组：今天/昨天/M月D日/跨年加年份，POST 添加，DELETE 单条）；前端未搜索时替代 tips 显示、垃圾桶删除模式、点击回填不自动搜
2. **搜索结果封面图** — `SearchResult.cover_url` 后端透传，前端缩略图展示（无封面降级放大镜），评分移至作者行
3. **Novel.serial 兜底** — serial=0 的书源（92xs 等无总数）进入自动模式，`update_chapter` 持续同步本地章节数；显式非零不被覆盖

**变更**
1. **下载开始改 toast 通知** — 不再自动跳转下载管理；下载管理任务列表逆序渲染 + 加载骨架（列表/章节行）
2. **设置自动保存** — 取消保存按钮，字段变更即时提交 + toast「设置已保存」；apikey 输入框加灰色方框与占位
3. **收藏入口移入三点菜单** — 书籍卡片封面左上角 Heart 移至右下角菜单顶部（收藏/取消收藏）
4. **导航改 react-router Link** — 侧边栏/底部导航不再整页刷新，保持 SPA 前进后退历史

**修复**
1. **收藏空态无返回入口** — 空态下保留全部/收藏切换按钮
2. **下载管理完成态无法展开** — completed/partial 条目展开显示全部章节（成功/失败状态）
3. **封面放大** — 遮罩恢复半透明（bg-black/70 + blur），移除缩放（纯弹窗展示）
4. **详情页加载** — 本地模式"加载中..."改骨架屏统一；进阅读页回顶强化（内容加载后再次回顶）
5. **API 模式未选 variant** — 取消兜底，搜索按钮触发 variant 区整体抖动并拦截；variant 区独立成行修手机端错位
6. **依赖补 lxml** — 代码用 `BeautifulSoup(html, 'lxml')` 但依赖未声明，CI（无预装 lxml）9 个测试失败

## v4.3.0

### 新增

1. **BrowserOptions 新增 `extra_args`** — 支持传入额外 Chromium 命令行参数（如 `--remote-debugging-port`、`--no-sandbox` 等），通过 CLI `--extra-args`、前端设置、配置文件均可配置
2. **Linux 环境自动适配 Chromium 启动参数** — `BrowserEngine._init_browser()` 在 Linux 下自动追加 `--no-sandbox`、`--disable-gpu`、`--disable-setuid-sandbox`、`--disable-dev-shm-usage`，解决 Termux / SSH / Docker 等无桌面环境的 sandbox 报错

### 重构

1. **书源注册机制去硬编码** — `_hardcoded_sources()` / `_HARDCODED_CAPABILITIES` / `_hardcoded_exporters()` / `_hardcoded_export_options()` 全部移除；改为开发模式目录扫描 + Nuitka 模式读取构建时预生成的 `novelbase/utils/_manifest.py`
2. **URL 推断数据驱动** — `_platform_from_url()` / `_resolve_url()` 改为基于书源 `HOSTS` / `ID_PATTERN` / `BOOK_URL_TEMPLATE` 匹配，无法识别时明确报错（不再静默回落 "fanqie"）
3. **新增 consts** — 各书源 `__init__.py` 添加 `BOOK_URL_TEMPLATE`
4. **新增 API** — `POST /api/v2/download/detect`（根据 URL/ID 推断平台）
5. **新增工具** — `python -m novelbase.utils.build_manifest`（扫描 sources/ 生成 manifest）

### 说明

- FastAPI `version="2.0.0"`（`services/backend/main.py:35`）为独立 API 版本，与项目版本 4.3.0 分属不同命名空间，非矛盾

## v4.2.3

### 新增

1. **跨平台 portable 便携版** — 新增 `build-portable.sh`，替代 Nuitka onefile 编译（耗时/易错），改为「Python 解释器 + 源码 + 预装依赖」打包：
   - **Linux x64/arm64**：python-build-standalone 独立解释器（pip 用 manylinux wheel 免编译），解压即用
   - **Termux**：依赖在 termux-docker 容器按 bionic 环境预编译打包（`python-deps/`），仅需 `pkg install python` 一条命令，无 pip/编译
   - 支持 `--deps-dir`（预装 site-packages）与 `--pyroot-dir`（内置 Python，PYTHONHOME 重定位，已实测通过）参数
2. **便携版 CI 内启动验证** — termux workflow 在容器内实测 `uvicorn` 启动 + HTTP 200（前端与 API 均验证）
3. **Novel.origin_id 派生属性** — 只读属性，值为去掉 `{website}_` 前缀的源站原始 ID（如 `fanqie_7123...` → `7123...`）
4. **所有源新增 `ORIGIN_ID_PATTERN`** — 匹配去前缀的源站原始 ID（`Novel.origin_id`），与 `ID_PATTERN`（匹配带前缀的 Novel.id）并存；registry 扫描/硬编码兜底与 `cli.py source list --json` 同步暴露
### 变更

1. **Android 与 musl 产物移除** — 删除 `android/` 目录、`build-apk.yml`、`build-linux-arm64-musl.yml`（musl 动态产物 Termux 无法运行）；产物矩阵为 Windows x64 / Linux x64 / Linux arm64
2. **Linux 构建改用 portable 方案** — `build-linux-x64.yml` / `build-linux-arm64.yml` / `build-linux-arm64-termux.yml` 由 Nuitka 编译改为 `build-portable.sh`（构建 10-20 分钟，免 C 编译）
3. **打包版判断修正** — 用 Nuitka `__compiled__` 特性替代 `sys.frozen`（Nuitka 不设置 sys.frozen，导致 exe 误走 reload 分支报 WinError 10013）
4. **Windows 产物统一 portable 命名** — build-windows 产物改为 `novel-downloader-web-portable-{version}-windows-x64`（与 Linux 系列命名一致）
5. **workflow 显示名称统一** — `Build Windows x64` → `Build Windows x64 portable`（与 Linux portable 系列命名一致）
6. **Windows 构建改用 portable 方案** — build-windows.yml 由 Nuitka 编译（build-web.ps1）改为 `build-portable.ps1`（Embedded Python + 源码 + 依赖 zip），产物统一为 `novel-downloader-web-portable-{version}-windows-x64.zip`
7. **Termux 加回 build-dist（内置 Python）** — Termux portable 采用 pyroot 全内置方案（Python 本体 + 依赖库随包，PYTHONHOME 重定位，开箱即用无需 `pkg install python`）；build-dist 覆盖 Windows x64 / Linux x64 / Linux arm64 / Termux 四平台
8. **移除交互式 CLI** — 删除 `main.py` 及 app 交互层（`app/menus.py` / `app/ui.py` / `app/notify.py`），`cli.py` 重构为纯非交互唯一 CLI 入口：新增 `delete`（删除小说）、`novel list`（书架）、`source list`（书源，`source`/`sources` 均可）；`export` 改为直接导出不再走交互菜单；scripts 调试脚本改从 `app.config` 加载配置
9. **app/ 目录更名 cli_lib** — CLI 辅助层（配置加载/下载编排）改名，避免与嵌套核心目录命名冲突；cli.py 与调试脚本引用同步更新
10. **scripts/ 移至衍生产物目录** — 调试脚本（debug_source / debug_exporter / debug_parser / cloud_sync / recover_db / archive 等）不进核心仓库；构建辅助 check-termux-psutil.sh（原 probe-termux.sh，孤儿脚本）定位于衍生产物目录
11. **删除废弃 Nuitka 构建脚本** — build-main、build-cli（CLI 版 Nuitka 构建遗留，已只发布 portable 便携版）
12. **portable 构建仅打包 webui** — 移除 cli_lib 打包（webui 运行不依赖 CLI 层）
13. **删除杂项文件** — package.json / package-lock.json（本地 reasonix npm 临时文件误入仓库）
### 修复

1. **build-windows 重命名** — 改为 PowerShell `Copy-Item`（git-bash `mv` 在 CI 上失败）
2. **前端 npm 镜像** — CI 上 `npm install` 改用 npmmirror 镜像 + 时间戳输出（定位 Build 卡点）
3. **Termux 容器兼容** — 容器无 `/tmp`（改用挂载卷）；`ANDROID_API_LEVEL=24`（maturin 构建 pydantic-core 需要）；依赖 `.so` 随 `pyroot` 一并复制（PYTHONHOME 重定位必需）
4. **storage.delete_novel 在 Windows 删除失败** — sqlite 连接对象依赖 GC 销毁、文件句柄延迟释放导致 `os.remove` 撞 `PermissionError`；删除前强制 `gc.collect()` 并加重试
5. **构建脚本同步 cli_lib 改名** — build-portable.ps1/sh 与 build-web.ps1 仍引用已删除的 `app` 目录（打包会失败/漏包），改为 `cli_lib`
---

## v4.2.1

### 新增

1. **单平台构建 workflow** — 新增 `build-windows.yml` / `build-linux-x64.yml` / `build-linux-arm64.yml` / `build-linux-arm64-musl.yml` / `build-apk.yml`，每个可单独手动触发测试（保留 `build-dist.yml` 一键全平台）；新增 **Linux arm64 musl 静态构建**（Termux 可运行）
2. **PyPI 构建上传脚本** — `build-pypi.ps1` / `build-pypi.sh`，token 走环境变量
3. **前端设置页模式动态化** — 平台 / 引擎设置按 mode 过滤；**APK 与 WebUI 不自动跟随系统暗色**（默认亮色，手动可切换）

### 变更

1. **APK 改为通用 ABI** — 去掉 arm64-v8a 限定，任意设备可安装
2. **产物命名追加版本号** — Windows exe / Linux 可执行文件 / APK 均带 `4.2.1` 版本后缀
3. **Linux 构建改用 ubuntu-22.04** — 提升 glibc 兼容性（旧系统可运行）
4. **放弃 Windows/Linux x86 构建** — pillow-heif 无 win32 支持，32 位系统不再出产物
5. Nuitka 静态链接 libpython（Windows 移除不支持的 `--static-libpython`，Linux 保留）

### 修复

1. **Windows Nuitka 依赖分析** — 改用 `--experimental=force-dependencies-pefile`（原 `--windows-dependency-tool` 选项已移除），彻底规避 Dependency Walker 下载失败