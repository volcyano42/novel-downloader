# novel-downloader

多平台小说下载器。Python 后端 + React 前端，SQLite 存储。

## Commands

```powershell
# 后端导入验证
python -c "from novelbase import *; print('OK')"

# 运行测试（118 passed）
python -m pytest tests/ -v --tb=short

# 启动 CLI（交互式）
python main.py

# 启动 CLI（非交互）
python cli.py search --platform fanqie "关键词"
python cli.py download --url "https://..." --mode requests

# 启动 FastAPI 后端
uvicorn services.backend.main:app --reload

# 前端
cd services/frontend
npm run dev              # 开发服务器
npm run build            # 生产构建
npx tsc --noEmit --project tsconfig.app.json   # 类型检查
```

## Architecture

```
novelbase/              ← 核心库（source 驱动）
  core/                   engine.py, downloader.py, storage.py, options.py, exceptions.py
  sources/                fanqie/, qidian/, qimao/（每平台三个 mode：browser/requests/api）
  exporters/              epub, txt, img
  models/                 Novel, Chapter, Chapters, SearchResult, Illustration
  utils/                  registry.py（动态分发）, logger.py, hooks.py

app/                    ← CLI 应用层
  core.py, config.py, menus.py, ui.py, notify.py

services/
  backend/                FastAPI (main.py) → routers/ + services/（task_manager, engine_manager）
  frontend/               React SPA (Vite + Tailwind + shadcn/ui + @tanstack/react-query)

app_data/               ← 运行时数据（gitignored）
  config/                 config.yaml, sites/*.yaml, groups.yaml, formats/*.yaml
  storage/                novels.db（每本小说独立 .db 文件）
  exports/                导出输出
```

## Key Conventions

- **API v2** 响应格式 `{ok, message, data}`，无分页
- **Registry 动态分发** `registry.resolve(name, mode, function, provider?)` → 底层函数，`FUNC_FILE_MAP` 映射逻辑名到实际文件名
- **Source** 函数直接放在 `sources/{platform}/{mode}/{provider}/` 下
- **引擎三种模式** `browser`（Playwright）、`requests`（httpx）、`api`（Rain.ink 代理）
- **前端状态** `@tanstack/react-query`，不用手动 `useEffect` 加载
- **SSE 章节流** `GET /api/v2/novel/{id}/chapters/stream`
- **BS4 选择器** 只用 `select_one`/`select`（CSS 选择器），不用 `find`/`find_all`
- **CSS flex 陷阱** flex column 中 `flex-1` 不约束宽度，需 `min-w-0` + `overflow-hidden`；flex row 子元素默认 `min-width: auto`
- **提交** 中文消息，一个方面一条 commit，禁止 `git add -A`
- **配置** `app_data/config/` 下全部 YAML，不提交到 git

## Notes

