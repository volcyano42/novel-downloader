# novel-downloader 项目上下文（会话速览）

> 完整文档按主题分类存放，见文末「文档索引」。本文件是**新会话必读速览**：概述 + 关键约定 + 目录索引。

## 项目概述

多平台小说下载器。Python 后端（FastAPI + novelbase 核心库）+ React 前端（TypeScript + Tailwind + shadcn/ui），SQLite 做本地存储，SSE 推送章节。版本 **v4.4.0**（2026-08-17 发布至 main；v4.2.3 的 Windows portable 漏打包 init_config.py 问题早已修复）。

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

> 2026-08-20：**209 passed, 2 skipped**（本机实测；含 search_history、source_async、task_manager_async 等异步测试）。注：Windows 上 Steam++ 加速器运行期间 pytest 每个 tmp_path 会因 symlink 慢约 31s。

## 关键约定

- **API v2** 响应格式 `{ok, message, data}`，无分页
- **Git 提交** 消息用中文；一个方面一条 commit；禁止 `git add -A`（显式指定文件）；提交前自查这四个规则。**dev 分支的提交与推送可自动执行**（无需逐次请示，2026-08-02 用户授权），main 分支例外
- **分支管理** **dev 分支可自动提交/推送**（2026-08-02 用户授权）；**main 分支的合并与推送必须用户临时同意**：不自动 `git merge` 到 main、不自动 `git push origin main`（含 fast-forward 同步）——必须由用户明确指示后才执行。已授权的合并/推送：2026-07-31（v4.2.1）、2026-08-01（v4.2.3-dev 多次）、2026-08-02（v4.2.3 发布 + 目录重组后推送 dev/main）、2026-08-02（Android APK 功能完成，用户选择推送 dev，commit 6023f3a）
- **远程凭证** origin 使用 Git Credential Manager（Windows 凭据库存 token），URL 不含 token；中文 commit 消息用 `-F <file>` 传入（cmd 引号会吞中文）
- **手动触发** 手动构建 workflow 由用户自行在 GitHub 界面触发；**例外**：用户在"构建目标产物"类任务中明确授权时，agent 可自行 dispatch（2026-07-31 起多次授权，含 build-dist / release / 单平台 build-*.yml），但重试前先取消旧 run 保证单 run 运行。**workflow yml 配置支持使用 dev 分支的**：dispatch 用 `ref=dev` 即运行 dev 分支的 yml/构建脚本（workflow 文件本体从默认分支 main 解析注册；已存在的 workflow 文件在 dev 上的修改无需合并 main 即可生效——2026-08-02 build-windows 实测，run 30746855971）
- **版本号更新** 用户明确要求更新版本时，同步更新 `CHANGELOG.md`（新增 `## v{版本}` 段落）与项目版本号（`pyproject.toml` + `novelbase/__init__.py`）；若版本号不确定，先询问用户
- **状态管理** 前端用 `@tanstack/react-query`，不再手动 `useEffect` 加载
- **SSE** 章节流式推送（`GET /api/v2/novel/{id}/chapters/stream`）
- **引擎** 三种模式：`browser`（**Playwright**，2026-08-16 从 DrissionPage 迁移）、`requests`（httpx）、`api`（Rain.ink 代理）
- **存储** SQLite，每本书独立 `.db` 文件，包含 meta/chapters/illustrations 表
- **Rain API** key 在配置文件中，fanqie 和 qimao 各有独立 key
- **配置** `app_data/config/config.yaml` 控制下载并发、通知等
- **BS4 选择器** 使用 `select_one`/`select`（CSS 选择器），不用 `find`/`find_all`
- **搜索** `platform="all"` 全平台搜索，结果按平台分组，失败平台静默跳过
- **SearchResult** 有 `platform: str` 字段，`search()` 函数统一打标签
- **搜索缓存** SessionCache 存完整搜索参数（query/platform/mode/variant），切回 tab 自动恢复
- **下载器 API** `skip_delay=False` 参数通过 `**kwargs` 传递到底层函数
- **Source 架构** `source.resolve(name, mode, function, variant?)` 动态分发到底层函数（`novelbase.source` 命名空间）；`source.capabilities()` 统一返回 `dict[str, dict[str, list[str]]]`（单 variant mode 用 `"default"` key）；`variant=None` 时默认取 `"default"`
- **CLI** `python -m cli`（`cli/` 包，2026-08-13 由 cli.py + cli_lib 合并；argparse 子命令）
- **Novel.origin_id** 只读属性，值为去掉 `{website}_` 前缀的源站原始 ID（如 `fanqie_7123...` → `7123...`）
- **ORIGIN_ID_PATTERN** 每个 source 新增，匹配去前缀的 origin_id（`ID_PATTERN` 匹配带前缀 Novel.id，两者并存）
- **导出器** 纯函数 `export()`，无类实例状态（BASEExporter 已删除）
- **SHOW_NAME** 每个 source 有中文显示名，`register_source()` 返回 `{name: {name, show_name, hosts, id_pattern, origin_id_pattern, ...}}`
- **前端动态平台** 模式/方案从 `GET /api/v2/download/sources` 动态获取，不硬编码
- **encoding 参数** `engine.fetch_text(url, encoding=...)` 可指定编码，默认自动检测（`apparent_encoding`）
- **Android APK**（2026-08-02 落地，**2026-09-24 首次构建成功** run `35975357459`）：`android/` 目录 + `build-apk.yml` workflow，用 **Chaquopy 嵌入 Python**（插件 15.0.1，wheel 仓库 `chaquo.com/pypi-13.1`；见 [build/android-apk.md](build/android-apk.md)）。硬约束：**`minSdk 24`**（pip 只接受 tag ≤ minSdk 的 wheel，`lxml`/`PyYAML` 只有 `android_24`）、**必须 `pydantic<2`**（`pydantic-core` 是 Rust 无 Android wheel）且 `fastapi` pin `==0.120.0`、**依赖排除不能写 `pip { exclude }`**（无此 API）而由 `build-apk.sh` 生成 `android/.req-android.txt`、public 无 `pyproject.toml` 故 `novelbase` 走源码复制；产物**未签名**（缺 `KEYSTORE_*` secrets）、**真机启动未验证**；musl 构建仍移除
- **本机不构建任何平台产物**（2026-08-02 确认）：构建全走 CI workflow；衍生产物（email_downloader.py、调试脚本）放 novel-downloader-tools/
- **variant 命名**（2026-08-05）：`capabilities()` 第二层 key 统一命名为 variant（替代旧 provider），语义为 "同一 mode 下的不同实现/方案"；单实现 mode（browser/requests）用 `"default"` 占位；`resolve()` 签名 `variant=None` 默认取 `"default"`。向后端 API 传送的 Query 参数同理改为 `variant`，前端 sessionStorage key `nd:variant`
- **私有源隔离**（2026-08-05）：环境变量 `NLD_PRIVATE_SOURCES` 指向外部私有目录（镜像 `sources/{name}/` 结构），`capabilities()` 自动合并，`resolve()` 从私有目录动态加载。公开仓库不包含敏感实现（如逆向/破解），本地开发设 env var 即可使用全部功能
- **BrowserOptions extra_args**（2026-08-05）：支持传入额外 Chromium 命令行参数（如 `--remote-debugging-port`），解决 Termux SSH 等无桌面环境的 browser 模式可用性问题
- **Novel.serial 兜底**（2026-08-20）：serial=0 的书源（如 92xs）进入 `_serial_auto` 自动模式，`update_chapter` 持续同步 `serial=len(chapters)`；显式非零 serial 不被覆盖
- **搜索历史 API**（2026-08-20）：`/api/v2/history/search` GET（按天分组：今天/昨天/M月D日/跨年加年份）POST（添加）DELETE（单条）；前端未搜索时替代 tips 显示、垃圾桶删除模式、点击回填不自动搜
- **分支状态**（2026-08-20）：main = **v4.4.0**（`6b3eb0f`，2026-08-17）；**dev 领先 main 14 个提交**（8-17 前端 10 个 + 8-20 体验清单 4 个，已推送 origin/dev，未合并 main）

## 文档索引

| 分类 | 文档 | 内容 |
|------|------|------|
| 入口 | [README.md](README.md) | 全部文档导航 |
| 项目基础 | [project/overview.md](project/overview.md) | 概述、目录结构、架构速览、测试状态 |
| 项目基础 | [project/cli.md](project/cli.md) | CLI 命令一览 |
| 项目基础 | [project/sources.md](project/sources.md) | 平台 source 状态 + 注册机制 |
| 项目基础 | [project/config.md](project/config.md) | 配置文件说明 |
| 项目基础 | [project/development.md](project/development.md) | 验证命令、开发环境、衍生产物 |
| 项目约定 | [conventions/git.md](conventions/git.md) | Git 提交/分支/workflow/版本号约定 |
| 构建发布 | [build/packaging.md](build/packaging.md) | 打包方案（pip/portable/CI 矩阵） |
| 构建发布 | [build/termux.md](build/termux.md) | Termux 构建方案 |
| 构建发布 | [build/android-apk.md](build/android-apk.md) | Android APK 方案 |
| 构建发布 | [build/pitfalls.md](build/pitfalls.md) | CI 构建经验（踩坑记录） |
| 设计文档 | [superpowers/specs/](superpowers/specs/) | 功能设计文档（`-design.md`） |
| 实施计划 | [superpowers/plans/](superpowers/plans/) | 实施计划 |
