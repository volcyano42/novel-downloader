# novel-downloader

多平台小说下载器。Python 后端 + React 前端，SQLite 存储。

## Commands

```powershell
# 后端导入验证
python -c "from novelbase import *; print('OK')"

# 运行测试（449 passed, 1 skipped）
python -m pytest tests/ -v --tb=short

# 启动 CLI（交互式）
python main.py

# 启动 CLI（非交互）
python -m cli search --source fanqie-requests-default "关键词"
python -m cli download --source fanqie-requests-default --url "https://..."

# 启动 FastAPI 后端
uvicorn backend.main:app --reload

# 前端
cd frontend
npm run dev              # 开发服务器
npm run build            # 生产构建
npx tsc --noEmit --project tsconfig.app.json   # 类型检查
```

## Key Conventions

- **API v2** 响应格式 `{ok, message, data}`，无分页
- **书源契约** 书源 = `novelbase/sources/{dir}/`，身份在 `source.json`，能力在 `{capability}.py`。
  对外 API：`list_sources()` / `get_manifest(name)` / `capabilities(name) -> {capability: mode}` / `resolve(name, capability) -> (fn, mode)`。
  `source_name`（source.json 里）与目录名解耦；目录名是合法 Python 标识符，能力通过 `import_module("novelbase.sources.{dir}.{capability}")` 加载。
  `source_name` **全局唯一**（内置根 + 私有根同一命名空间）：撞名在加载期抛 `DuplicateSourceNameError`（`ManifestError` 子类），检测点 `novelbase/sources/manifest.py::scan_source_names()`；私有源须自带独立 `source_name`。
  新增书源：建目录 + 空 `__init__.py` + `source.json` + 4 个能力文件，无注册表改动。
- **引擎三种模式** `browser`（Playwright）、`requests`（httpx）、`api`（Rain.ink 代理）
- **前端状态** `@tanstack/react-query`，不用手动 `useEffect` 加载
- **SSE 章节流** `GET /api/v2/storage/novel/{id}/chapters/stream`
- **BS4 选择器** 只用 `select_one`/`select`（CSS 选择器），不用 `find`/`find_all`
- **CSS flex 陷阱** flex column 中 `flex-1` 不约束宽度，需 `min-w-0` + `overflow-hidden`；flex row 子元素默认 `min-width: auto`
- **提交** 中文消息，一个方面一条 commit，禁止 `git add -A`
- **配置** `app_data/config/` 下全部 YAML，不提交到 git
- **文档** 一律写在 `docs/` 下（按子目录分类），**可提交到 private 仓库**（2026-08-21 起，原"不入 git"约定废弃）；公开迁移时 superpowers/session-prompt/learning 仍在红名单不迁 public

## Public 迁移约定（novel-crawler）

- **迁移必须用 subagent 执行**（task/subagent 工具）：主 Agent 不亲自做复制/校验/文件遍历，避免大量文件清单与敏感判断污染主上下文导致降智
- subagent 职责：读 `PUBLIC_MANIFEST.md` → **输出「本次迁移清单」**（复制列表 + 依据条目 + 红名单确认）→ 按白名单复制（**迁移后改写 `novelbase/__init__.py` 的 `__version__` 与 pyproject 一致**）→ 跑 `python scripts/check_public.py` → 返回校验结果
- 主 Agent 收到 subagent 报告后**向用户展示本次迁移清单与校验结果**，用户确认后再提交
- 迁移前**必读** `PUBLIC_MANIFEST.md`（白名单 = 允许复制；红名单 = 禁止；未列出一律不迁移）
- public 仓库（同级 `novel-crawler/`）独立提交/推送，不混入 private 的 commit 习惯
- 敏感判定：`api` 书源（oiapi/rain）、`app_data`、私有配置、`docs/superpowers`、`AGENTS.md` 一律不进 public

## Notes

