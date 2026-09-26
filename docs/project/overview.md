# 项目概述与架构

## 项目概述

多平台小说下载器。Python 后端（FastAPI + novelbase 核心库）+ React 前端（TypeScript + Tailwind + shadcn/ui），SQLite 做本地存储，SSE 推送章节。版本号见 `novelbase/__init__.py`（**main = v4.4.0，dev = v4.5.0**，dev 未合并 main）。

## 目录结构（2026-08-02 重组后）

```
D:\Linux\novel-downloader\            ← 外层容器（非 git 仓库）
├── novel-downloader\                ← 核心 git 仓库（dev/main 分支）
│   ├── novelbase/  backend/  frontend/  cli/  shared/  scripts/  tests/
│   ├── cli.py  main.py  app.py      ← 非交互 CLI / 交互式 CLI / 一键启动 入口
│   ├── init_config.py  template/  app_data/  docs/
│   └── .git
└── novel-downloader-tools\          ← 衍生产物（仓库外，git 永远管不到）
    ├── email_downloader.py          番茄小说邮件下载脚本（衍生，不进远程）
    └── scripts/                     调试/工具脚本（debug_source/debug_exporter/debug_parser、
                                      cloud_sync/recover_db/archive 等）
```

> **docs/ 随核心仓库入库**（`novel-downloader/docs/`）。外层容器 `D:\Linux\novel-downloader\docs` 仅存一份指向本目录的指针。

## 架构速览

```
novelbase/          ← 核心库（source 驱动，引擎/存储/下载/导出）
  core/               engine.py, downloader.py, storage.py, options.py, exceptions.py
  sources/            一层书源目录（{source_dir}/，如 fanqie_requests_default/）
    每个书源            __init__.py + source.json + 4 个能力文件
                        (search.py / novel_info.py / chapter_list.py / chapter_content.py)
  models/             Novel, Chapter, Chapters, Illustration, SearchResult（models/novel.py）
  exporters/          export() 纯函数（txt, epub, img；base.py/contracts.py）
  utils/              logger.py, hooks.py, encoding.py, urls.py, template_utils.py, build_manifest.py
  source.py           ← 公共 API（list_sources / get_manifest / capabilities / resolve / resolve_book_url）
  sources/contracts.py ← Protocol 契约 + CAPABILITY_META 单一数据源
  sources/manifest.py  ← source.json 加载与校验

backend/              FastAPI 入口 (main.py) + 内嵌前端静态文件 serve
  routers/          download.py, storage.py, export.py, config.py, history.py
  services/         task_manager.py, engine_manager.py, source_guard.py
  schemas/          download.py, storage.py, export.py, export_config.py

frontend/             React SPA (Vite)
  src/features/     bookshelf/, detail/, download/, reader/, settings/, sources/
  src/hooks/        useNovels, useChapters, useDownloadMutation, useGlobalConfig, useSources …
  src/api/          endpoints.ts（API 函数）, client.ts（fetch 封装）
  src/components/   Toast, ErrorBoundary, UI 组件库 (alert-dialog, button, dropdown-menu, select, sheet, tooltip)
  src/utils/        sessionCache, chapterCache
  src/lib/          utils.ts

cli/                  CLI 层（2026-08-02 起为 cli/ 包）
  main.py           ← 非交互 argparse 命令入口（cli.py 委托于此）
  interactive.py    ← 交互式主菜单（main.py 委托于此）
  menus.py  ui.py  notify.py  config.py  core.py
cli.py                ← 非交互 CLI 入口（委托 cli.main）
main.py               ← 交互式 CLI 入口（委托 cli.interactive.main，2026-08-25 还原）
app.py                ← 统一启动器（一键启动前后端，Ctrl+C 优雅关闭）

shared/               config.py, user_data.py（跨端共享：配置加载 / 用户数据库模板）

app_data/
  config/             config.yaml, sites/{source_name}.yaml, formats/*.yaml
  storage/novels/       SQLite，每本小说一个独立 <id>.db 文件（id = sha256(url)[:32]）
  exports/            导出输出目录
tests/                check_imports.py, test_downloader.py, test_export_config.py, test_models.py,
                      test_options.py, test_storage.py, conftest.py 等
```

## CI 测试状态 — ✅ 全部通过

> 2026-09-25（书源扁平化收口后本机实测）：`python -m pytest tests/ -q` = **401 passed, 1 skipped, 0 failed**（约 4.9s；1 个 skip 是 `test_android_server.py` 既有的 `@pytest.mark.skip`）。前端 `npx tsc --noEmit --project tsconfig.app.json` = 0 错。
>
> 2026-09-25（来源读点 + mode 用户覆盖 + 前端整合收口后本机实测）：`python -m pytest tests -q` = **444 passed, 1 skipped, 0 failed**；前端 `npx tsc -b` = 0 错。
>
> 2026-09-25（详情页换源 + 下载管理书源/时间收口后本机实测）：`python -m pytest tests -q` = **449 passed, 1 skipped, 0 failed**（约 7.6s）；前端 `npx tsc -b` = 0 错、`npm run lint` 0 告警。
>
> 2026-09-26（Android 前端交付修复 + 环境能力表后本机实测）：`python -m pytest tests -q` = **507 passed, 0 failed**（约 13s；原先 skip 的 `TestClient` 用例随死代码挂载一并删除）；前端 `npx tsc -b` = 0 错、`npm run lint` 0 告警。
>
> 2026-09-26（移除 Android 套壳与环境能力表后本机实测）：`python -m pytest tests -q` = **482 passed, 0 failed**（约 10.9s）；前端 `npx tsc -b` = 0 错、`npm run lint` 0 告警。
