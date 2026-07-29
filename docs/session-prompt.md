# novel-downloader 项目上下文

## 项目概述

多平台小说下载器。Python 后端（FastAPI + novelbase 核心库）+ React 前端（TypeScript + Tailwind + shadcn/ui），SQLite 做本地存储，SSE 推送章节。

## 架构速览

```
novelbase/          ← 核心库（source 驱动，引擎/存储/下载/导出）
  core/               engine.py, downloader.py, storage.py, exporter.py
  sources/            fanqie/, qidian/, qimao/（每个平台三个引擎：Requests/Browser/Rain API）
  models/             Novel, Chapter, Chapters, SearchResult
  exporters/          epub, txt, img
  utils/              logger.py, registry.py, hooks.py, template_utils.py

services/
  backend/            FastAPI 入口 (main.py)
    routers/          download.py, storage.py, export.py, config.py, engine.py
    services/         task_manager.py（下载任务线程池）, engine_manager.py, config_service.py
    schemas/          download.py, storage.py, export.py, export_config.py, engine.py
  frontend/           React SPA (Vite)
    src/features/     bookshelf/, detail/, download/, settings/, reader/
    src/hooks/        useNovels, useChapters, useDownload, useConfig …
    src/api/          endpoints.ts（API 函数）, client.ts（fetch 封装）
    src/components/   Toast, ErrorBoundary, UI 组件库 (alert-dialog, button, dropdown-menu, select, sheet, tooltip)
    src/utils/        sessionCache, chapterCache

app/
  config.py, core.py, menus.py, notify.py, ui.py    ← CLI 应用层

app_data/
  config/             config.yaml, sites/*.yaml, groups.yaml
  storage/            novels.db（SQLite，每本小说一个独立 .db 文件）
  exports/            导出输出目录

scripts/              cloud_sync.py, debug_exporter.py, debug_source.py, debug_parser.py, recover_db.py
                      archive/（已归档的一次性脚本：fix_chapter_order.py, migrate_to_sqlite.py）
tests/                check_imports.py, test_downloader.py, test_export_config.py, test_models.py,
                      test_options.py, test_storage.py, conftest.py
```

## CI 测试状态 — ✅ 全部通过（118 passed）

## 关键约定

- **API v2** 响应格式 `{ok, message, data}`，无分页
- **状态管理** 前端用 `@tanstack/react-query`，不再手动 `useEffect` 加载
- **SSE** 章节流式推送（`GET /api/v2/novel/{id}/chapters/stream`）
- **引擎** 三种模式：`browser`（Playwright）、`requests`（httpx）、`api`（Rain.ink 代理）
- **存储** SQLite，每本书独立 `.db` 文件，包含 meta/chapters/illustrations 表
- **Rain API** key 在配置文件中，fanqie 和 qimao 各有独立 key
- **配置** `app_data/config/config.yaml` 控制下载并发、通知等
- **BS4 选择器** 使用 `select_one`/`select`（CSS 选择器），不用 `find`/`find_all`
- **搜索** `platform="all"` 全平台搜索，结果按平台分组，失败平台静默跳过
- **SearchResult** 有 `platform: str` 字段，`search()` 函数统一打标签
- **搜索缓存** SessionCache 存完整搜索参数（query/platform/mode/provider），切回 tab 自动恢复
- **移动端 header** DetailPage 不再有独立 sticky header；返回按钮在 App.tsx 的移动端 header 里（`/novel/` 和 `/search/` 路由自动显示）
- **下载器 API** `skip_delay=False` 参数通过 `**kwargs` 传递到底层函数
- **Source 架构** `registry.resolve(name, mode, function, provider?)` 动态分发到底层函数；`capabilities()` 返回每个 mode/provider 的功能列表

## CSS/布局陷阱（反复踩坑）

- **BS4 CSS 选择器 100% 等价映射**：`find("div", class_="foo")` → `select_one("div.foo")`；链式 `.find().find()` → 单次 `select_one("a b")`；`attrs={}` → `[attr="val"]`
- **`flex-1` 在 flex column 中只约束高度不约束宽度**：宽度默认跟随内容。必须加 `width: 100%` + `max-width: 100%` 才能限宽
- **`overflow-x: hidden` 只裁视觉不阻止布局撑宽**：flex 子元素仍可被内容撑宽，需配合 `width: 100%` 或 `min-w-0` 强制约束
- **`min-w-0` 允许收缩但不阻止撑宽**：`min-width: 0` 让元素可以比内容小，但不能阻止内容把它撑大。需配合 `overflow: hidden`
- **flex row 子元素默认 `min-width: auto`**：允许内容撑宽父容器 → 给 flex 子元素加 `min-w-0`
- **页面偏右/溢出**：flex 链上某处 `min-width: auto` 导致容器超出 viewport，root `overflow: hidden` 裁掉左侧 → 视觉偏右。**给 `main` 加 `min-w-0`**
- **`sr-only` 隐藏 input 获得焦点时浏览器自动滚动**：用 label `onClick` + `e.preventDefault()` + input `tabIndex={-1}` 代替 input `onChange`
- **DetailPage `isRemote` 判断**：来自 `remoteUrl`（state）或本地 meta 404（自动推断）→ 纯数字 novelId 推断番茄 URL
- **`tailwindcss-animate`** 需在 `tailwind.config.js` 的 `plugins` 中注册，且需在 `package.json` 中声明依赖

## 平台 source 状态

| 平台 | 搜索 | URL 解析 | 章节列表 | 正文 | 备注 |
|------|------|----------|----------|------|------|
| fanqie (番茄) | ✅ browser/requests/api | ✅ id_pattern+standardize_id | ✅ | ✅ | 短链 `changdunovel.com/t/` 需重定向 |
| qidian (起点) | ✅ browser/requests | ✅ `/book/` `/info/` | 部分（JS 动态加载） | ✅ | 长 share URL 自动提取 book_id |
| qimao (七猫) | ✅ browser/requests/api | ✅ `/shuku/` | ✅ Rain API (4K+章) | ✅ | search 返回 `data.books` 格式 |

## 配置文件说明

### config.yaml
```
download.max_workers: 3     # 下载并发数
download.notify.on_complete: true
mode: api                   # 默认下载模式
storage.backend: sqlite
storage.database_url: sqlite:///app_data/storage/novels.db
export.formats: [epub]
```

### sites/*.yaml
每个平台三个引擎段的配置（api/browser/requests），含 delay、retry_times、timeout、backoff_factor。fanqie 的 `api.oiapi.enabled` 设为 false。

### groups.yaml
分组管理，格式 `{group_name: {novel_id: {}}}`, 当前为空：`default: {}`。

## 验证命令

```powershell
# 后端导入
python -c "from novelbase import *; print('OK')"

# 前端编译
cd services/frontend
npx tsc --noEmit --project tsconfig.app.json

# 运行测试
python -m pytest tests/ -v --tb=short
```

## 开发环境

- Windows 10/11 (PowerShell) 或 Android Termux
- Python 3.13
- Node 24.15, npm 11.14
- Playwright Chromium 可用（桌面端）
- pip 依赖：beautifulsoup4, drissionpage, fastapi, Pillow, PyYAML, Requests, rich, uvicorn, yarl 等
