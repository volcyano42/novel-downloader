# novel-downloader 项目上下文（会话速览）

> 完整文档按主题分类存放，见文末「文档索引」。本文件是**新会话必读速览**：概述 + 关键约定 + 目录索引。

## 项目概述

多平台小说下载器。Python 后端（FastAPI + novelbase 核心库）+ React 前端（TypeScript + Tailwind + shadcn/ui），SQLite 做本地存储，SSE 推送章节。版本号见 `novelbase/__init__.py`（**main = dev = v4.5.2**；2026-10-14 已 ff 合并 main 并推送，tag/Release `v4.5.2` 由 release 工作流创建；v4.2.3 的 Windows portable 漏打包 init_config.py 问题早已修复）。⚠️ **本仓库（`volcyano42/novel-downloader`）2026-10-14 被发现处于 public 状态**（意外，含 api 书源等敏感源码），已改回 **private** —— 「公开迁移」只走公开仓库 `novel-crawler`（见 `PUBLIC_MANIFEST.md`）。

## 目录结构（2026-08-13 重组后）

```
D:\Linux\novel-downloader\            ← 外层容器（非 git 仓库）
├── novel-downloader\                ← 核心 git 仓库（dev/main 分支）
│   ├── novelbase/  shared/  backend/  cli/  frontend/  tests/  app_data/  docs/  template/
│   ├── scripts/                     ← 构建脚本（workflow 调用）
│   └── .git
└── novel-downloader-tools\          ← 衍生产物（仓库外，git 永远管不到）
```

> **docs/ 已纳入 private 版本库**（2026-08-21 起，位于 `novel-downloader/docs/`）；公开迁移时 superpowers/session-prompt/learning 在红名单不迁 public。架构速览见 [project/overview.md](project/overview.md)。

## CI 测试状态 — ✅ 全量通过

> **2026-09-30 复核**：本机全量 `python -m pytest tests -q` → **513 passed, 0 failed**（22.7s）——2026-09-27 记录的「每个 `tmp_path` 用例约 62s（Steam++ 加速器 symlink 拖慢）、全量跑不完」已不复现。CI run [77](https://github.com/volcyano42/novel-downloader/actions/runs/36699778387)（dev `e7f769b`）Python 3.10 / 3.11 / 3.12 **全绿**。前端 `npx tsc -b` = 0 错（`tsconfig.json` 是 solution 风格，`tsc --noEmit` 会空转，须用 `tsc -b`）、`npm run lint`（oxlint）0 告警。UI 冒烟：headless Chromium 打开设置页 / 搜索页，别名、分组双框与 browser 源「用户数据目录」均按预期渲染（截图存于 `tmp/nld-ui-20260930/`）。
>
> 历史：2026-09-27 只做了定向验证（`tests/test_source_metadata.py` 5 个 `tmp_path` 用例逐个 PASSED + 三条 grep 验收），全量当时未跑通；更早一次全量 = 2026-09-27 `source_name` 全局唯一检测后 **499 passed, 0 failed**（约 12s）。

## 关键约定

- **API v2** 响应格式 `{ok, message, data}`，无分页
- **novelbase 公共 API 稳定性**（2026-10-14）：`novelbase` 面向**所有开发者**（含第三方），**公共函数的参数与语义不轻易更改**——改 `novelbase/` 的公开签名（`core/downloader.py` 的 `search` / `resolve_meta` / `resolve_chapter_list` / `resolve_chapter`，`core/engine.py` 的 `create_engine`，`Options` 等）前必须先与用户确认，并同步**全部**调用方（backend / cli / task_manager）与文档。纯增益改动（补类型标注 / docstring / 文档）不受此限，但仍需如实描述实际契约
- **Git 提交** 消息用中文；一个方面一条 commit；禁止 `git add -A`（显式指定文件）；提交前自查这四个规则。**dev 分支的提交与推送可自动执行**（无需逐次请示，2026-08-02 用户授权），main 分支例外
- **分支管理** **dev 分支可自动提交/推送**（2026-08-02 用户授权）；**main 分支的合并与推送必须用户临时同意**：不自动 `git merge` 到 main、不自动 `git push origin main`（含 fast-forward 同步）——必须由用户明确指示后才执行。已授权的合并/推送：2026-07-31（v4.2.1）、2026-08-01（v4.2.3-dev 多次）、2026-08-02（v4.2.3 发布 + 目录重组后推送 dev/main）、2026-08-02（Android APK 功能完成，用户选择推送 dev，commit 6023f3a）
- **远程凭证** origin 使用 Git Credential Manager（Windows 凭据库存 token），URL 不含 token；中文 commit 消息用 `-F <file>` 传入（cmd 引号会吞中文）
- **手动触发** 手动构建 workflow 由用户自行在 GitHub 界面触发；**例外**：用户在"构建目标产物"类任务中明确授权时，agent 可自行 dispatch（2026-07-31 起多次授权，含 build-dist / release / 单平台 build-*.yml），但重试前先取消旧 run 保证单 run 运行。**workflow yml 配置支持使用 dev 分支的**：dispatch 用 `ref=dev` 即运行 dev 分支的 yml/构建脚本（workflow 文件本体从默认分支 main 解析注册；已存在的 workflow 文件在 dev 上的修改无需合并 main 即可生效——2026-08-02 build-windows 实测，run 30746855971）
- **版本号更新** 用户明确要求更新版本时，同步更新 `CHANGELOG.md`（新增 `## v{版本}` 段落）与项目版本号（`pyproject.toml` + `novelbase/__init__.py`）；若版本号不确定，先询问用户
- **状态管理** 前端用 `@tanstack/react-query`，不再手动 `useEffect` 加载
- **SSE** 章节流式推送（`GET /api/v2/storage/novel/{id}/chapters/stream`）
- **引擎** 三种模式：`browser`（**Playwright**，2026-08-16 从 DrissionPage 迁移）、`requests`（httpx）、`api`（Rain.ink 代理）。**mode 默认由书源在 `source.json` 里声明**（顶层 `mode`）；**用户可在用户层顶层整体覆盖**（`sources/{source_name}.yaml` 顶层 `mode`，唯一入口 `shared.config.effective_capabilities()`，2026-10-25 起不再逐能力覆盖：一个 mode 对四类能力全部生效；`null` 表示恢复声明）。core 的 `capabilities()` / `resolve()` 恒取声明值，覆盖只在调用方生效
- **存储** SQLite，每本书独立 `.db` 文件，包含 meta/chapters/illustrations 表
- **Rain API** key 在配置文件中，fanqie 和 qimao 各有独立 key
- **配置** `app_data/config/config.yaml` 控制下载任务数、通知等；**逐书源配置**在 `app_data/config/sources/{source_name}.yaml`（2026-09-25 起旧 `sources/*.yaml` 不迁移，用户重配）
- **并发模型**（2026-09-25 重做，见 [superpowers/specs/2026-09-25-download-concurrency-design.md](superpowers/specs/2026-09-25-download-concurrency-design.md)）三层：① **任务级** `download.max_workers`（默认 3）= **最多同时运行的下载任务数**（超额任务 `status="queued"`、前端「排队中」；排队中暂停**不占任务槽**，`resume` 后抢额度）；② **书源级** `concurrency`（`source.json` 顶层可选 + 用户层 `sources/{name}.yaml` **顶层**覆盖，默认 1，**跨任务共享**，约束任务内 `resolve_meta`/`resolve_chapter` 的请求，读取入口 `shared.config.source_concurrency()`，非正整数回退 1）；③ **逐能力** `delay`（每请求前随机等待，**出厂默认由 `[3,5]` 改为 `[0,0]` = 不限速**；优先级 `dataclass 默认 → source.json 的 common → 能力段自身 → 用户层 sources yaml`）。CLI 章节并发上限 = `min(max_workers, source_concurrency)`，默认即单章串行（提速靠 `delay=0`）。**已知边界**：已是 `downloading` 的任务被暂停仍占任务槽；独立路由（检查更新 `GET /storage/novel/{id}/chapters` / 搜索 / 远端章节列表）**不经**书源额度；`max_workers` 下调最多 1 秒生效（TTL 缓存）
- **BS4 选择器** 使用 `select_one`/`select`（CSS 选择器），不用 `find`/`find_all`
- **书源（Source）架构**（2026-09-25 扁平化后）：`novelbase/sources/{dir}/` **一层**目录，每个书源含空 `__init__.py` + `source.json`（`source_name`/`source_alias`/`source_group`/`common`/`default_config`）+ 4 个能力文件（`search.py` / `novel_info.py` / `chapter_list.py` / `chapter_content.py`）。`novelbase/source.py` 只暴露 4 个能力函数 + 1 个 URL 入口：`list_sources()` / `get_manifest(source_name)` / `capabilities(source_name) -> {capability: mode}` / `resolve(source_name, capability) -> (fn, mode)` / `resolve_book_url(raw)`。**`platform` 概念已彻底移除**（`platform_from_url` / `register_source` / `NAME` / `SHOW_NAME` / `HOSTS` 全部删除）；书源显示名 = 别名 `source_alias`（未设回落 `source_name`），界面与日志经 `shared.config.display_name()` 统一显示（如 `fanqie-requests-default`）。**不设 `_common.py`**：各书源自包含，共享逻辑内联进需要它的能力文件（明确接受书源间重复的代价）
- **书源 `source.json` 规范**：`source_name` 唯一 id（也是 `sources/{source_name}.yaml` 的文件名）——**全局唯一**（内置根 + 私有根同一命名空间，**私有源复用内置 id 也报错**），撞名在加载期抛 `DuplicateSourceNameError`（检测点 `novelbase/sources/manifest.py::scan_source_names()`）；元信息为**可选**顶层 `source_alias`（显示别名，未设回落 `source_name`）/ `source_group`（分组，一个源一个组，空 = 未分组），读取入口 `shared.config.source_group()` / `source_alias()` / `display_name()`，用户层可覆盖；顶层字段即唯一一套参数（2026-10-25 起 `common` / 能力段已删除）；**能力段存在 ⇔ 同名 `.py` 文件存在**，不一致直接报 `ManifestError`；字段命名全链用 `retry_times`
- **书源元信息与选择**（2026-09-27）：`enabled` **已彻底废弃**——`source.json` 与用户层都不再有该字段（旧键不读、`PUT` 时清理），`is_source_enabled()` / `enabled_source_names()` 已删除。书源以 `source_group`（分组，一个源一个组，空 = 未分组）+ `source_alias`（显示别名，未设回落 `source_name`）表达；读取入口 `shared.config.source_group()` / `source_alias()` / `display_name()`。**默认参与集** = `shared.config.default_source_names()`（= **全部**书源，`sorted(list_sources())`，**无任何环境过滤**）。搜索支持 `GET /api/v2/download/search?sources=a,b,c`（逗号分隔；缺省 = 全部书源；未知源静默跳过，筛完为空 400）。前端搜索页（标题 tab）为「全选/分组/未分组」分段单选 + 逐源复选（**默认全选、不持久化**），URL tab 单选按分组分节显示别名，结果来源 tab 显示别名。
- **下载器 API**（2026-10-14 修订 engine / 删除 mode_overrides）：`async search(source_name, query, engine, skip_delay=False, **kwargs) -> SearchResult | None`（**单源**搜索，返回该源**第一条**命中，无结果 → `None`；源报错 / `FeatureNotSupportedError` **上抛**） / `resolve_meta(url, source_name, engine, skip_delay=False, **kwargs)` / `resolve_chapter_list(url, source_name, engine, skip_delay=False, **kwargs)` / `resolve_chapter(chapter, source_name, engine, skip_delay=False, **kwargs)`。`engine` 是**单个 `Engine` 实例**（`novelbase.Engine`，第 3 位），由调用方按该能力的**有效 mode**（`shared.config.effective_capabilities(source_name)`）自行 `create_engine` 后注入；core **不关心 mode**（原 `mode_overrides` 参数已删除），传旧 `engines(mode)` 解析器会抛 `TypeError`；`skip_delay=False` 仍经 `**kwargs` 传递到底层函数
- **搜索**（2026-10-01 修订）：core `search(source_name, ...)` 只搜**单个**书源、返回**第一条**命中（无结果 → `None`）；**多源并发在调用方**（backend / CLI 逐源 gather 并各自兜底失败），core **不再吞异常**（源报错 / `FeatureNotSupportedError` 上抛）。**每源最多贡献 1 条结果**。`SearchResult.source_name` 由 **downloader 分发层统一打标**（书源侧不写死，直接调书源 `search()` 会得到空 `source_name`）
- **SearchResult** 字段为 `source_name: str`（旧 `platform` 已删）。**来源不再挂在 `Novel` 上**（2026-09-25 剥离）：`Novel.source_name` 与 `novel.extra["platform"]` 均已删除，来源改由 `config/library/books.yaml` 的 `source` 字段承载（`GET /storage/novel` 与 `/storage/novel/{id}/meta` 据此返回 `source_name`）
- **搜索缓存** SessionCache 存 `query` / `source_name`（`mode`/`variant` 概念已取消）
- **Novel.id = sha256(url)、库内 meta.id = url**（2026-09-24 改，取代 2026-08-22 的 `hash(canonical url)`）：对外标识（模型字段 / 磁盘文件名 / API / 前端 / CLI）= `sha256(url)[:32]`；库内 `meta.id` 列存**书源返回的 url 原样**（不做规范化，可按 url 查书）。`canonical_book_url` 及其平台特例（92xs/qidian）已删除，url 归一由书源负责——core 不再承载站点知识
- **不做 url 规范化**（2026-09-24）：同一本书的不同 url 形态会得到不同 id（如 92xs 的 `/book/{id}.html` 与 `/html/{id}/`），入库与后续使用须保持同一形态。**重构不得改变书源返回的 url**（变更 = 已有书籍 id 漂移）；`tests/test_novel_id_stability.py` 用 AST 快照兜底
- **导出器** 纯函数 `export()`，无类实例状态（BASEExporter 已删除）
- **书源源根**（2026-10-26「书源与 core 结构分离」）：官方源下沉到 `novelbase/sources/builtin/{dir}/`，`novelbase/sources/` 只留 core 机制（`contracts.py` / `manifest.py`）。发现层按**有序源根列表**扫描，所有根**走同一条加载路径**（`spec_from_file_location`，包内包外无差别）：`NLD_SOURCE_ROOTS`（`os.pathsep` 多根） → 旧 `NLD_PRIVATE_SOURCES` → `add_source_root()` 注入（`<APP_DATA>/sources`，由 `shared.config` 在 import 时注册） → 官方 `builtin` 根。**用户源安装**：解压进 `<APP_DATA>/sources/` 即生效，无需 env、无需重装。**`source_name` 全局唯一跨所有根**，撞名加载期抛 `DuplicateSourceNameError`（`scan_source_names()`）。编译模式（Nuitka）静态表只覆盖 `builtin`，用户源仍从文件系统加载，两表合并后查撞名。能力模块按「根哈希+目录名+能力」缓存进 `sys.modules`：改源文件需重启，增删源目录即时生效。公开仓库只保留能公开的源，敏感实现放用户源根，不进任何仓库
- **Nuitka 编译链路**：`python -m novelbase.utils.build_manifest` 遍历 `sources/*/source.json` 生成 `novelbase/utils/_manifest.py`（`SOURCES`，键 = 目录名；`SOURCE_DIRS`，映射 `source_name → 目录名`）；`source.py` 的 `_is_compiled()` 分支读它。两个 `build-nuitka` 脚本本身无需改
- **BrowserOptions extra_args**（2026-08-05）：支持传入额外 Chromium 命令行参数（如 `--remote-debugging-port`），解决 Termux SSH 等无桌面环境的 browser 模式可用性问题
- **Novel.serial 兜底**（2026-08-20）：serial=0 的书源（如 92xs）进入 `_serial_auto` 自动模式，`update_chapter` 持续同步 `serial=len(chapters)`；显式非零 serial 不被覆盖
- **搜索历史 API**（2026-08-20）：`/api/v2/history/search` GET（按天分组：今天/昨天/M月D日/跨年加年份）POST（添加）DELETE（单条）；前端未搜索时替代 tips 显示、垃圾桶删除模式、点击回填不自动搜
- **中间态收口状态**（2026-09-25 扁平化 followup + 收尾完成）：core 层遗留中间态**已全部收口**——`/api/v2/download/platform`、`/api/v2/download/detect`、`/api/v2/engine` 路由**已删除**；书源元信息（`source_alias`/`source_group`）经 `shared.config.display_name()` / `source_group()` 读取，**默认参与集** = `shared.config.default_source_names()`（`enabled` 已彻底废弃）；前端 mode/variant 两级选择器**已删除**（搜索改「按选择书源并发（默认全选）」，URL 解析改「手选书源」，书源管理**并入设置页**折叠条）。收尾阶段补齐：① 未知 `source_name` 在 **HTTP 边界统一 404**（`backend/services/source_guard.py` 唯一校验点，覆盖 `download` 与 `config/sources` 全部入口）；② 书源配置表单抽为 `frontend/src/features/sources/sourceConfigForm.tsx` 共享实现（设置页每源一个折叠条 `SourceAccordion` 复用；原独立 `SourcesPage` 已删除，`/sources` 仅重定向 `/settings`、侧边栏无「书源」入口），`useSaveSourceConfig` 同时失效 `["source-config", src]` 与 `["sources"]`；③ CLI `cmd_info` / `cmd_download` 引擎按 mode 懒建（不再共用单引擎）；④ `dev new-source` 脚手架 `source.json.common` 与出厂默认同源（`shared.config.mode_defaults()`）。**仍缺**（后续增强，非缺陷）：前端 URL **自动**匹配书源（core 无 `platform_from_url`，`source` 由用户手选）
- **公开迁移（public 同步）**：公开仓库是 **`novel-crawler`**（本地 `../novel-crawler`，SSH remote），依据 `PUBLIC_MANIFEST.md` + `pyproject.toml` 的 `[tool.novel-downloader.migration] exclude`（排除清单唯一数据源）；复制后**必跑** `python scripts/check_public.py`（缺失 / 多余 / 敏感三道防线）。**迁移是「同步」而非「只增」**：public 中既不在白名单、也不在 `check_public.PUBLIC_ONLY_FILES`（`README.md` / `CHANGELOG.md` / `CONTRIBUTING.md` / `.gitignore`）的文件一律删除。2026-10-14 实测：public 只保留 fanqie 两个源 ⇒ 依赖未公开源的测试必须排除；`hashFiles` 不可用于 job 级 `if`（会让 workflow 静默失效）。**每次同步后还要在 public 侧补 CHANGELOG 版本段**（`CHANGELOG.md` 属 public 自维护，版本号对齐 `novelbase/__init__.py` 的 `__version__`，内容只写可公开变化）
- **分支状态**（2026-10-14）：**main = dev = v4.5.2**（2026-10-14 以 `git merge --ff-only` 合并 dev 并推送 main；tag `v4.5.2` 与 GitHub Release 由 `release.yml` 创建，附件 = Windows portable + **Windows Nuitka exe** + Linux x64/arm64 + Termux portable）。v4.5.2 内容：`source_name` 全局唯一检测、书源元信息（分组/别名）与按选择搜索、browser 登录态与下载顺序 FIFO 修复、core `search` 改「单源单结果」、WebUI 导出 txt 的文件名占位符修复、**Nuitka exe 读不到同目录 `app_data` 修复**（新增 `shared/paths.py`，统一三处定位）、发行产物纳入 exe。**此处刻意不写死「领先几个提交」**（每次提交都会变）：要看当前值请跑 `git rev-list --count origin/dev..dev`（查「dev 领先 main 多少」用 `git rev-list --count main..dev`）；权威口径用 `git ls-remote origin dev` 对比

## 文档索引

| 分类 | 文档 | 内容 |
|------|------|------|
| 入口 | [README.md](README.md) | 全部文档导航 |
| 项目基础 | [project/overview.md](project/overview.md) | 概述、目录结构、架构速览、测试状态 |
| 项目基础 | [project/cli.md](project/cli.md) | CLI 命令一览 |
| 项目基础 | [project/sources.md](project/sources.md) | 书源机制（source.json / 4 个公共 API / 能力声明） |
| 项目基础 | [project/config.md](project/config.md) | 配置文件说明 |
| 项目基础 | [project/development.md](project/development.md) | 验证命令、开发环境、衍生产物 |
| 项目约定 | [conventions/git.md](conventions/git.md) | Git 提交/分支/workflow/版本号约定 |
| 构建发布 | [build/packaging.md](build/packaging.md) | 打包方案（pip/portable/CI 矩阵） |
| 构建发布 | [build/termux.md](build/termux.md) | Termux 构建方案 |
| 构建发布 | [build/pitfalls.md](build/pitfalls.md) | CI 构建经验（踩坑记录） |
| 设计文档 | [superpowers/specs/](superpowers/specs/) | 功能设计文档（`-design.md`） |
| 实施计划 | [superpowers/plans/](superpowers/plans/) | 实施计划 |
| 规划 | [planning/roadmap.md](planning/roadmap.md) | 发展方向分析（实勘现状 + 十维度方向表 + 路线图 + MVP；**红名单，不迁 public**） |
