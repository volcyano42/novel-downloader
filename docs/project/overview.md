# 项目概述与架构

## 项目概述

多平台小说下载器。Python 后端（FastAPI + novelbase 核心库）+ React 前端（TypeScript + Tailwind + shadcn/ui），SQLite 做本地存储，SSE 推送章节。版本 v4.2.3（已发布 tag）；dev 已升级至 v4.3.0（2026-08-05）。

## 目录结构（2026-08-02 重组后）

```
D:\Linux\novel-downloader\            ← 外层容器（非 git 仓库）
├── novel-downloader\                ← 核心 git 仓库（dev/main 分支）
│   ├── novelbase/  cli_lib/  cli.py  services/  tests/  app_data/  docs/  template/
│   ├── android/                     ← Android APK 项目（2026-08-02 新增，Chaquopy 嵌入 Python）
│   ├── build-portable.ps1/.sh  build-pypi.ps1/.sh   ← 构建脚本（workflow 调用）
│   └── .git
└── novel-downloader-tools\          ← 衍生产物（仓库外，git 永远管不到）
    ├── email_downloader.py          番茄小说邮件下载脚本（衍生，不进远程）
    └── scripts/                     调试/工具脚本（debug_source/debug_exporter/debug_parser、
                                      cloud_sync/recover_db/archive 等）
```

> **docs/ 在外层容器**（`D:\Linux\novel-downloader\docs\`），被 .gitignore 忽略，不入版本库。

## 架构速览

```
novelbase/          ← 核心库（source 驱动，引擎/存储/下载/导出）
  core/               engine.py, downloader.py, storage.py, exporter.py
  sources/            fanqie/, qidian/, qimao/, 92xs/
    fanqie/             browser/ requests/ api/(oiapi/ rain/)
    qidian/             browser/ requests/
    qimao/              browser/ requests/ api/(rain/)
    92xs/                requests/
    每个 mode/variant 下: search.py, novel_info.py, chapter_list.py, chapter_content.py
  models/             Novel, Chapter, Chapters, Illustration, SearchResult
  exporters/          export() 纯函数（txt, epub, img）
  utils/              logger.py, registry.py, hooks.py, template_utils.py
  source.py           ← 公共 API（capabilities/resolve/list_sources）
  sources/contracts.py ← Protocol 契约 + CAPABILITY_META 单一数据源

services/
  backend/            FastAPI 入口 (main.py) + 内嵌前端静态文件 serve
    routers/          download.py, storage.py, export.py, config.py, engine.py
    services/         task_manager.py, engine_manager.py, config_service.py
    schemas/          download.py, storage.py, export.py, export_config.py, engine.py
  frontend/           React SPA (Vite)
    src/features/     bookshelf/, detail/, download/, settings/, reader/
    src/hooks/        useNovels, useChapters, useDownload, useConfig, useSources …
    src/api/          endpoints.ts（API 函数）, client.ts（fetch 封装）
    src/components/   Toast, ErrorBoundary, UI 组件库 (alert-dialog, button, dropdown-menu, select, sheet, tooltip)
    src/utils/        sessionCache, chapterCache

cli_lib/              CLI 辅助层（原 app/，2026-08-02 更名）
  config.py           app_data/config 配置加载（load_main_config/load_site_config/build_options 等）
  core.py             下载/更新编排（_do_download_inner/do_update/_get_storage，纯非交互）
cli.py                ← 唯一 CLI 入口（非交互，9 个子命令）

app_data/
  config/             config.yaml, sites/*.yaml, groups.yaml, formats/*.yaml
  storage/            novels.db（SQLite，每本小说一个独立 .db 文件）
  exports/            导出输出目录
tests/                check_imports.py, test_downloader.py, test_export_config.py, test_models.py,
                      test_options.py, test_storage.py, test_android_server.py, conftest.py

android/              ← Android APK（Chaquopy 嵌入 Python，2026-08-02 新增，见「Android APK 方案」章节）
  app/src/main/python/   server.py + frontend/（构建时复制）+ services/backend + init_config.py + template/
  app/src/main/java/     MainActivity.kt, ServerService.kt, AndroidBridge.kt, EnvironmentCompat.kt
  scripts/build-apk.sh   CI 构建脚本
```

## CI 测试状态 — ✅ 全部通过

> 2026-08-05：新增 TestPrivateSources（5 个测试，1 个因 monkeypatch 超时暂 skip）。
