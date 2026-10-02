# novel-downloader 项目上下文（会话速览）

> 完整文档按主题分类存放，见文末「文档索引」。本文件是**新会话必读速览**：概述 + 关键约定 + 目录索引。

## 项目概述

多平台小说下载器。Python 后端（FastAPI + novelbase 核心库）+ React 前端（TypeScript + Tailwind + shadcn/ui），SQLite 做本地存储，SSE 推送章节。版本号见 `novelbase/__init__.py`（**main = dev = v4.5.1**；2026-09-27 起 dev 领先 main 一批提交尚未合并，main 停在 `fd12a2c`；v4.2.3 的 Windows portable 漏打包 init_config.py 问题早已修复）。

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
- **Git 提交** 消息用中文；一个方面一条 commit；禁止 `git add -A`（显式指定文件）；提交前自查这四个规则。**dev 分支的提交与推送可自动执行**（无需逐次请示，2026-08-02 用户授权），main 分支例外
- **分支管理** **dev 分支可自动提交/推送**（2026-08-02 用户授权）；**main 分支的合并与推送必须用户临时同意**：不自动 `git merge` 到 main、不自动 `git push origin main`（含 fast-forward 同步）——必须由用户明确指示后才执行。已授权的合并/推送：2026-07-31（v4.2.1）、2026-08-01（v4.2.3-dev 多次）、2026-08-02（v4.2.3 发布 + 目录重组后推送 dev/main）、2026-08-02（Android APK 功能完成，用户选择推送 dev，commit 6023f3a）
- **远程凭证** origin 使用 Git Credential Manager（Windows 凭据库存 token），URL 不含 token；中文 commit 消息用 `-F <file>` 传入（cmd 引号会吞中文）
- **手动触发** 手动构建 workflow 由用户自行在 GitHub 界面触发；**例外**：用户在"构建目标产物"类任务中明确授权时，agent 可自行 dispatch（2026-07-31 起多次授权，含 build-dist / release / 单平台 build-*.yml），但重试前先取消旧 run 保证单 run 运行。**workflow yml 配置支持使用 dev 分支的**：dispatch 用 `ref=dev` 即运行 dev 分支的 yml/构建脚本（workflow 文件本体从默认分支 main 解析注册；已存在的 workflow 文件在 dev 上的修改无需合并 main 即可生效——2026-08-02 build-windows 实测，run 30746855971）
- **版本号更新** 用户明确要求更新版本时，同步更新 `CHANGELOG.md`（新增 `## v{版本}` 段落）与项目版本号（`pyproject.toml` + `novelbase/__init__.py`）；若版本号不确定，先询问用户
- **状态管理** 前端用 `@tanstack/react-query`，不再手动 `useEffect` 加载
- **SSE** 章节流式推送（`GET /api/v2/storage/novel/{id}/chapters/stream`）
- **引擎** 三种模式：`browser`（**Playwright**，2026-08-16 从 DrissionPage 迁移）、`requests`（httpx）、`api`（Rain.ink 代理）。**mode 默认由书源在 `source.json` 里声明**（`common.mode` 并入各能力段）；**用户可逐能力覆盖**（`sites/{source_name}.yaml` 的 `{cap}.mode`，唯一入口 `shared.config.effective_capabilities()`，2026-09-25 二次修订；覆盖为「值 + 引擎默认字段」替换，`null` 表示恢复声明）。core 的 `capabilities()` / `resolve()` 恒取声明值，覆盖只在调用方生效
- **存储** SQLite，每本书独立 `.db` 文件，包含 meta/chapters/illustrations 表
- **Rain API** key 在配置文件中，fanqie 和 qimao 各有独立 key
- **配置** `app_data/config/config.yaml` 控制下载任务数、通知等；**逐书源配置**在 `app_data/config/sites/{source_name}.yaml`（2026-09-25 起旧 `sites/*.yaml` 不迁移，用户重配）
- **并发模型**（2026-09-25 重做，见 [superpowers/specs/2026-09-25-download-concurrency-design.md](superpowers/specs/2026-09-25-download-concurrency-design.md)）三层：① **任务级** `download.max_workers`（默认 3）= **最多同时运行的下载任务数**（超额任务 `status="queued"`、前端「排队中」；排队中暂停**不占任务槽**，`resume` 后抢额度）；② **书源级** `concurrency`（`source.json` 顶层可选 + 用户层 `sites/{name}.yaml` **顶层**覆盖，默认 1，**跨任务共享**，约束任务内 `resolve_meta`/`resolve_chapter` 的请求，读取入口 `shared.config.source_concurrency()`，非正整数回退 1）；③ **逐能力** `delay`（每请求前随机等待，**出厂默认由 `[3,5]` 改为 `[0,0]` = 不限速**；优先级 `dataclass 默认 → source.json 的 common → 能力段自身 → 用户层 sites yaml`）。CLI 章节并发上限 = `min(max_workers, source_concurrency)`，默认即单章串行（提速靠 `delay=0`）。**已知边界**：已是 `downloading` 的任务被暂停仍占任务槽；独立路由（检查更新 `GET /storage/novel/{id}/chapters` / 搜索 / 远端章节列表）**不经**书源额度；`max_workers` 下调最多 1 秒生效（TTL 缓存）
- **BS4 选择器** 使用 `select_one`/`select`（CSS 选择器），不用 `find`/`find_all`
- **书源（Source）架构**（2026-09-25 扁平化后）：`novelbase/sources/{dir}/` **一层**目录，每个书源含空 `__init__.py` + `source.json`（`source_name`/`source_alias`/`source_group`/`common`/`default_config`）+ 4 个能力文件（`search.py` / `novel_info.py` / `chapter_list.py` / `chapter_content.py`）。`novelbase/source.py` 只暴露 4 个能力函数 + 1 个 URL 入口：`list_sources()` / `get_manifest(source_name)` / `capabilities(source_name) -> {capability: mode}` / `resolve(source_name, capability) -> (fn, mode)` / `resolve_book_url(raw)`。**`platform` 概念已彻底移除**（`platform_from_url` / `register_source` / `NAME` / `SHOW_NAME` / `HOSTS` 全部删除）；书源显示名 = 别名 `source_alias`（未设回落 `source_name`），界面与日志经 `shared.config.display_name()` 统一显示（如 `fanqie-requests-default`）。**不设 `_common.py`**：各书源自包含，共享逻辑内联进需要它的能力文件（明确接受书源间重复的代价）
- **书源 `source.json` 规范**：`source_name` 唯一 id（也是 `sites/{source_name}.yaml` 的文件名）——**全局唯一**（内置根 + 私有根同一命名空间，**私有源复用内置 id 也报错**），撞名在加载期抛 `DuplicateSourceNameError`（检测点 `novelbase/sources/manifest.py::scan_source_names()`）；元信息为**可选**顶层 `source_alias`（显示别名，未设回落 `source_name`）/ `source_group`（分组，一个源一个组，空 = 未分组），读取入口 `shared.config.source_group()` / `source_alias()` / `display_name()`，用户层可覆盖；顶层 `common` 段并入每个能力段（能力段覆盖 `common`，且 `common` 的字段必须对**所有出现的 mode** 合法）；**能力段存在 ⇔ 同名 `.py` 文件存在**，不一致直接报 `ManifestError`；字段命名全链用 `retry_times`
- **书源元信息与选择**（2026-09-27）：`enabled` **已彻底废弃**——`source.json` 与用户层都不再有该字段（旧键不读、`PUT` 时清理），`is_source_enabled()` / `enabled_source_names()` 已删除。书源以 `source_group`（分组，一个源一个组，空 = 未分组）+ `source_alias`（显示别名，未设回落 `source_name`）表达；读取入口 `shared.config.source_group()` / `source_alias()` / `display_name()`。**默认参与集** = `shared.config.default_source_names()`（= **全部**书源，`sorted(list_sources())`，**无任何环境过滤**）。搜索支持 `GET /api/v2/download/search?sources=a,b,c`（逗号分隔；缺省 = 全部书源；未知源静默跳过，筛完为空 400）。前端搜索页（标题 tab）为「全选/分组/未分组」分段单选 + 逐源复选（**默认全选、不持久化**），URL tab 单选按分组分节显示别名，结果来源 tab 显示别名。
- **下载器 API**（2026-10-01 修订 search）：`async search(source_name, query, engines, skip_delay=False, mode_overrides=None, **kwargs) -> SearchResult | None`（**单源**搜索，返回该源**第一条**命中，无结果 → `None`；源报错 / `FeatureNotSupportedError` **上抛**） / `resolve_meta(url, source_name, engines, skip_delay=False, mode_overrides=None, **kwargs)` / `resolve_chapter_list(url, source_name, engines, skip_delay=False, mode_overrides=None, **kwargs)` / `resolve_chapter(chapter, source_name, engines, skip_delay=False, mode_overrides=None, **kwargs)`。`engines` 是 `engines(mode) -> engine` 解析器，由调用方按**有效 mode**（`shared.config.effective_capabilities(source_name)`）懒建并复用；`mode_overrides`（能力名 → mode，可选）由调用方（backend 路由/task_manager、CLI）关键字透传，缺省则用书源声明；`skip_delay=False` 仍经 `**kwargs` 传递到底层函数
- **搜索**（2026-10-01 修订）：core `search(source_name, ...)` 只搜**单个**书源、返回**第一条**命中（无结果 → `None`）；**多源并发在调用方**（backend / CLI 逐源 gather 并各自兜底失败），core **不再吞异常**（源报错 / `FeatureNotSupportedError` 上抛）。**每源最多贡献 1 条结果**。`SearchResult.source_name` 由 **downloader 分发层统一打标**（书源侧不写死，直接调书源 `search()` 会得到空 `source_name`）
- **SearchResult** 字段为 `source_name: str`（旧 `platform` 已删）。**来源不再挂在 `Novel` 上**（2026-09-25 剥离）：`Novel.source_name` 与 `novel.extra["platform"]` 均已删除，来源改由 `user_data.db` 的 `novel_sources` 表承载（`GET /storage/novel` 与 `/storage/novel/{id}/meta` 据此返回 `source_name`）
- **搜索缓存** SessionCache 存 `query` / `source_name`（`mode`/`variant` 概念已取消）
- **Novel.id = sha256(url)、库内 meta.id = url**（2026-09-24 改，取代 2026-08-22 的 `hash(canonical url)`）：对外标识（模型字段 / 磁盘文件名 / API / 前端 / CLI）= `sha256(url)[:32]`；库内 `meta.id` 列存**书源返回的 url 原样**（不做规范化，可按 url 查书）。`canonical_book_url` 及其平台特例（92xs/qidian）已删除，url 归一由书源负责——core 不再承载站点知识
- **不做 url 规范化**（2026-09-24）：同一本书的不同 url 形态会得到不同 id（如 92xs 的 `/book/{id}.html` 与 `/html/{id}/`），入库与后续使用须保持同一形态。**重构不得改变书源返回的 url**（变更 = 已有书籍 id 漂移）；`tests/test_novel_id_stability.py` 用 AST 快照兜底
- **导出器** 纯函数 `export()`，无类实例状态（BASEExporter 已删除）
- **私有源隔离**（2026-08-05，2026-09-25 适配新结构，2026-09-27 收紧为全局唯一）：环境变量 `NLD_PRIVATE_SOURCES` 指向外部私有目录（镜像新的 `sources/{dir}/` 结构，走 `spec_from_file_location` 加载，因它在包外），与内置书源合并；**`source_name` 全局唯一**（2026-09-27 收紧）——内置根与私有根同一命名空间，任何重名（含私有源复用内置 id）加载期抛 `DuplicateSourceNameError`，原「同名能力内置优先」机制已取消，私有源须自带独立 `source_name`。公开仓库不包含敏感实现（如逆向/破解），本地开发设 env var 即可使用全部功能
- **Nuitka 编译链路**：`python -m novelbase.utils.build_manifest` 遍历 `sources/*/source.json` 生成 `novelbase/utils/_manifest.py`（`SOURCES`，键 = 目录名；`SOURCE_DIRS`，映射 `source_name → 目录名`）；`source.py` 的 `_is_compiled()` 分支读它。两个 `build-nuitka` 脚本本身无需改
- **BrowserOptions extra_args**（2026-08-05）：支持传入额外 Chromium 命令行参数（如 `--remote-debugging-port`），解决 Termux SSH 等无桌面环境的 browser 模式可用性问题
- **Novel.serial 兜底**（2026-08-20）：serial=0 的书源（如 92xs）进入 `_serial_auto` 自动模式，`update_chapter` 持续同步 `serial=len(chapters)`；显式非零 serial 不被覆盖
- **搜索历史 API**（2026-08-20）：`/api/v2/history/search` GET（按天分组：今天/昨天/M月D日/跨年加年份）POST（添加）DELETE（单条）；前端未搜索时替代 tips 显示、垃圾桶删除模式、点击回填不自动搜
- **中间态收口状态**（2026-09-25 扁平化 followup + 收尾完成）：core 层遗留中间态**已全部收口**——`/api/v2/download/platform`、`/api/v2/download/detect`、`/api/v2/engine` 路由**已删除**；书源元信息（`source_alias`/`source_group`）经 `shared.config.display_name()` / `source_group()` 读取，**默认参与集** = `shared.config.default_source_names()`（`enabled` 已彻底废弃）；前端 mode/variant 两级选择器**已删除**（搜索改「按选择书源并发（默认全选）」，URL 解析改「手选书源」，书源管理**并入设置页**折叠条）。收尾阶段补齐：① 未知 `source_name` 在 **HTTP 边界统一 404**（`backend/services/source_guard.py` 唯一校验点，覆盖 `download` 与 `config/sources` 全部入口）；② 书源配置表单抽为 `frontend/src/features/sources/sourceConfigForm.tsx` 共享实现（设置页每源一个折叠条 `SourceAccordion` 复用；原独立 `SourcesPage` 已删除，`/sources` 仅重定向 `/settings`、侧边栏无「书源」入口），`useSaveSourceConfig` 同时失效 `["source-config", src]` 与 `["sources"]`；③ CLI `cmd_info` / `cmd_download` 引擎按 mode 懒建（不再共用单引擎）；④ `dev new-source` 脚手架 `source.json.common` 与出厂默认同源（`shared.config.mode_defaults()`）。**仍缺**（后续增强，非缺陷）：前端 URL **自动**匹配书源（core 无 `platform_from_url`，`source` 由用户手选）
- **分支状态**（2026-09-27）：**main = dev = v4.5.1**（版本号一致，但 **dev 尚未合并 main**：main 停在 `fd12a2c`，dev 领先一批提交，内容 = `source_name` 全局唯一检测（实现层；私有源同名叠加机制取消）+ 文档口径收口 + review 修复）。v4.5.1 内容：书源扁平化（core + backend/CLI/前端收口）、下载并发模型重做、详情页换源、**Android 套壳与环境能力表移除（移动端改走 Termux）**、同步 `fetch_text` 登录态修复、CI 触发分支加 `dev`、文档与版本号收尾。**此处刻意不写死「领先几个提交」**（每次提交都会变）：要看当前值请跑 `git rev-list --count origin/dev..dev`（查「dev 领先 main 多少」用 `git rev-list --count main..dev`）；权威口径用 `git ls-remote origin dev` 对比

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
