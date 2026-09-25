# novel-downloader 项目上下文（会话速览）

> 完整文档按主题分类存放，见文末「文档索引」。本文件是**新会话必读速览**：概述 + 关键约定 + 目录索引。

## 项目概述

多平台小说下载器。Python 后端（FastAPI + novelbase 核心库）+ React 前端（TypeScript + Tailwind + shadcn/ui），SQLite 做本地存储，SSE 推送章节。版本号见 `novelbase/__init__.py`（**main 已发布 v4.4.0**，dev 领先；v4.2.3 的 Windows portable 漏打包 init_config.py 问题早已修复）。

## 目录结构（2026-08-13 重组后）

```
D:\Linux\novel-downloader\            ← 外层容器（非 git 仓库）
├── novel-downloader\                ← 核心 git 仓库（dev/main 分支）
│   ├── novelbase/  shared/  backend/  cli/  frontend/  tests/  app_data/  docs/  template/
│   ├── android/                     ← Android APK 项目（2026-08-02 新增，Chaquopy 嵌入 Python）
│   ├── scripts/                     ← 构建脚本（workflow 调用）
│   └── .git
└── novel-downloader-tools\          ← 衍生产物（仓库外，git 永远管不到）
```

> **docs/ 已纳入 private 版本库**（2026-08-21 起，位于 `novel-downloader/docs/`）；公开迁移时 superpowers/session-prompt/learning 在红名单不迁 public。架构速览见 [project/overview.md](project/overview.md)。

## CI 测试状态 — ✅ 全部通过

> 2026-09-25（扁平化 followup 收口后）：**389 passed, 1 skipped, 0 failed**（本机实测，约 4.9s；1 个 skip 是 `test_android_server.py` 既有的 `@pytest.mark.skip`）；前端 `npx tsc --noEmit` = 0 错。注：Windows 上 Steam++ 加速器运行期间 pytest 每个 tmp_path 会因 symlink 慢约 31s。

## 关键约定

- **API v2** 响应格式 `{ok, message, data}`，无分页
- **Git 提交** 消息用中文；一个方面一条 commit；禁止 `git add -A`（显式指定文件）；提交前自查这四个规则。**dev 分支的提交与推送可自动执行**（无需逐次请示，2026-08-02 用户授权），main 分支例外
- **分支管理** **dev 分支可自动提交/推送**（2026-08-02 用户授权）；**main 分支的合并与推送必须用户临时同意**：不自动 `git merge` 到 main、不自动 `git push origin main`（含 fast-forward 同步）——必须由用户明确指示后才执行。已授权的合并/推送：2026-07-31（v4.2.1）、2026-08-01（v4.2.3-dev 多次）、2026-08-02（v4.2.3 发布 + 目录重组后推送 dev/main）、2026-08-02（Android APK 功能完成，用户选择推送 dev，commit 6023f3a）
- **远程凭证** origin 使用 Git Credential Manager（Windows 凭据库存 token），URL 不含 token；中文 commit 消息用 `-F <file>` 传入（cmd 引号会吞中文）
- **手动触发** 手动构建 workflow 由用户自行在 GitHub 界面触发；**例外**：用户在"构建目标产物"类任务中明确授权时，agent 可自行 dispatch（2026-07-31 起多次授权，含 build-dist / release / 单平台 build-*.yml），但重试前先取消旧 run 保证单 run 运行。**workflow yml 配置支持使用 dev 分支的**：dispatch 用 `ref=dev` 即运行 dev 分支的 yml/构建脚本（workflow 文件本体从默认分支 main 解析注册；已存在的 workflow 文件在 dev 上的修改无需合并 main 即可生效——2026-08-02 build-windows 实测，run 30746855971）
- **版本号更新** 用户明确要求更新版本时，同步更新 `CHANGELOG.md`（新增 `## v{版本}` 段落）与项目版本号（`pyproject.toml` + `novelbase/__init__.py`）；若版本号不确定，先询问用户
- **状态管理** 前端用 `@tanstack/react-query`，不再手动 `useEffect` 加载
- **SSE** 章节流式推送（`GET /api/v2/storage/novel/{id}/chapters/stream`）
- **引擎** 三种模式：`browser`（**Playwright**，2026-08-16 从 DrissionPage 迁移）、`requests`（httpx）、`api`（Rain.ink 代理）。**mode 由书源自己在 `source.json` 里声明**，用户不再选 mode（2026-09-25）
- **存储** SQLite，每本书独立 `.db` 文件，包含 meta/chapters/illustrations 表
- **Rain API** key 在配置文件中，fanqie 和 qimao 各有独立 key
- **配置** `app_data/config/config.yaml` 控制下载并发、通知等；**逐书源配置**在 `app_data/config/sites/{source_name}.yaml`（2026-09-25 起旧 `sites/*.yaml` 不迁移，用户重配）
- **BS4 选择器** 使用 `select_one`/`select`（CSS 选择器），不用 `find`/`find_all`
- **书源（Source）架构**（2026-09-25 扁平化后）：`novelbase/sources/{dir}/` **一层**目录，每个书源含空 `__init__.py` + `source.json`（`source_name`/`enabled`/`common`/`default_config`）+ 4 个能力文件（`search.py` / `novel_info.py` / `chapter_list.py` / `chapter_content.py`）。`novelbase/source.py` 只暴露 4 个能力函数 + 1 个 URL 入口：`list_sources()` / `get_manifest(source_name)` / `capabilities(source_name) -> {capability: mode}` / `resolve(source_name, capability) -> (fn, mode)` / `resolve_book_url(raw)`。**`platform` 概念已彻底移除**（`platform_from_url` / `register_source` / `NAME` / `SHOW_NAME` / `HOSTS` 全部删除）；书源**没有中文显示名**，界面与日志统一显示 `source_name`（如 `fanqie-requests-default`）。**不设 `_common.py`**：各书源自包含，共享逻辑内联进需要它的能力文件（明确接受书源间重复的代价）
- **书源 `source.json` 规范**：`source_name` 唯一 id（也是 `sites/{source_name}.yaml` 的文件名）；`enabled` 出厂开关（**api 类默认 `false`，requests/browser 默认 `true`**）；顶层 `common` 段并入每个能力段（能力段覆盖 `common`，且 `common` 的字段必须对**所有出现的 mode** 合法）；**能力段存在 ⇔ 同名 `.py` 文件存在**，不一致直接报 `ManifestError`；字段命名全链用 `retry_times`
- **下载器 API**（2026-09-25 新签名）：`async search(sources, query, engines, **kwargs)` / `resolve_meta(url, source_name, engines, **kwargs)` / `resolve_chapter_list(url, source_name, engines, **kwargs)` / `resolve_chapter(chapter, source_name, engines, **kwargs)`。`engines` 是 `engines(mode) -> engine` 解析器，由调用方按 `capabilities(source_name)` 懒建并复用；`skip_delay=False` 仍经 `**kwargs` 传递到底层函数
- **搜索** 按书源并发（`search(sources, ...)`），失败书源静默跳过；`SearchResult.source_name` 由 **downloader 分发层统一打标**（书源侧不写死，直接调书源 `search()` 会得到空 `source_name`）
- **SearchResult** 字段为 `source_name: str`（旧 `platform` 已删；`Novel` 也新增 `source_name: str = ""` 标记来源）
- **搜索缓存** SessionCache 存 `query` / `source_name`（`mode`/`variant` 概念已取消）
- **Novel.id = sha256(url)、库内 meta.id = url**（2026-09-24 改，取代 2026-08-22 的 `hash(canonical url)`）：对外标识（模型字段 / 磁盘文件名 / API / 前端 / CLI）= `sha256(url)[:32]`；库内 `meta.id` 列存**书源返回的 url 原样**（不做规范化，可按 url 查书）。`canonical_book_url` 及其平台特例（92xs/qidian）已删除，url 归一由书源负责——core 不再承载站点知识
- **不做 url 规范化**（2026-09-24）：同一本书的不同 url 形态会得到不同 id（如 92xs 的 `/book/{id}.html` 与 `/html/{id}/`），入库与后续使用须保持同一形态。**重构不得改变书源返回的 url**（变更 = 已有书籍 id 漂移）；`tests/test_novel_id_stability.py` 用 AST 快照兜底
- **导出器** 纯函数 `export()`，无类实例状态（BASEExporter 已删除）
- **私有源隔离**（2026-08-05，2026-09-25 适配新结构）：环境变量 `NLD_PRIVATE_SOURCES` 指向外部私有目录（镜像新的 `sources/{dir}/` 结构，走 `spec_from_file_location` 加载，因它在包外），与内置书源合并，**同名能力内置优先**。公开仓库不包含敏感实现（如逆向/破解），本地开发设 env var 即可使用全部功能
- **Nuitka 编译链路**：`python -m novelbase.utils.build_manifest` 遍历 `sources/*/source.json` 生成 `novelbase/utils/_manifest.py`（`SOURCES`，键 = 目录名；`SOURCE_DIRS`，映射 `source_name → 目录名`）；`source.py` 的 `_is_compiled()` 分支读它。两个 `build-nuitka` 脚本本身无需改
- **BrowserOptions extra_args**（2026-08-05）：支持传入额外 Chromium 命令行参数（如 `--remote-debugging-port`），解决 Termux SSH 等无桌面环境的 browser 模式可用性问题
- **Novel.serial 兜底**（2026-08-20）：serial=0 的书源（如 92xs）进入 `_serial_auto` 自动模式，`update_chapter` 持续同步 `serial=len(chapters)`；显式非零 serial 不被覆盖
- **搜索历史 API**（2026-08-20）：`/api/v2/history/search` GET（按天分组：今天/昨天/M月D日/跨年加年份）POST（添加）DELETE（单条）；前端未搜索时替代 tips 显示、垃圾桶删除模式、点击回填不自动搜
- **中间态收口状态**（2026-09-25 扁平化 followup + 收尾完成）：core 层遗留中间态**已全部收口**——`/api/v2/download/platform`、`/api/v2/download/detect`、`/api/v2/engine` 路由**已删除**；`source.json` 的 `enabled` **已有消费者**（`shared.config.enabled_source_names()`）；前端 mode/variant 两级选择器**已删除**（搜索改「已启用书源并发」，URL 解析改「手选书源」，书源管理页 `/sources`）。收尾阶段补齐：① 未知 `source_name` 在 **HTTP 边界统一 404**（`backend/services/source_guard.py` 唯一校验点，覆盖 `download` 与 `config/sources` 全部入口）；② 书源配置表单抽为 `frontend/src/features/sources/sourceConfigForm.tsx` 共享实现（`SettingsPage` / `SourcesPage` 复用），`useSaveSourceConfig` 同时失效 `["source-config", src]` 与 `["sources"]`；③ CLI `cmd_info` / `cmd_download` 引擎按 mode 懒建（不再共用单引擎）；④ `dev new-source` 脚手架 `source.json.common` 与出厂默认同源（`shared.config.mode_defaults()`）。**仍缺**（后续增强，非缺陷）：前端 URL **自动**匹配书源（core 无 `platform_from_url`，`source` 由用户手选）；重复 `source_name` 无实现层检测；`novel.extra["platform"]` 键名保留（值为 `source_name`，数据兼容）
- **分支状态**（2026-09-25）：main = **v4.4.0**（`ef7f21d`，2026-08-17 后仅 CHANGELOG 补充）；**dev 领先 origin/dev 27 个提交（未推送，用户 2026-09-25 明确选择留在本地）**——含书源扁平化 core 层 23 个提交（`7ccb608`..`2c694b9`）与之前的 4 个；未合并 main

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
| 构建发布 | [build/android-apk.md](build/android-apk.md) | Android APK 方案 |
| 构建发布 | [build/pitfalls.md](build/pitfalls.md) | CI 构建经验（踩坑记录） |
| 设计文档 | [superpowers/specs/](superpowers/specs/) | 功能设计文档（`-design.md`） |
| 实施计划 | [superpowers/plans/](superpowers/plans/) | 实施计划 |
