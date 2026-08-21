# novel-downloader

多平台小说下载器。Python 后端 + React 前端，SQLite 存储。

## Commands

```powershell
# 后端导入验证
python -c "from novelbase import *; print('OK')"

# 运行测试（152 passed）
python -m pytest tests/ -v --tb=short

# 启动 CLI（交互式）
python -m cli

# 启动 CLI（非交互）
python -m cli search --platform fanqie "关键词"
python -m cli download --url "https://..." --mode requests

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
- **Registry 动态分发** `registry.resolve(name, mode, function, provider?)` → 底层函数，`FUNC_FILE_MAP` 映射逻辑名到实际文件名
- **Source** 函数直接放在 `sources/{platform}/{mode}/{provider}/` 下
- **引擎三种模式** `browser`（Playwright）、`requests`（httpx）、`api`（Rain.ink 代理）
- **前端状态** `@tanstack/react-query`，不用手动 `useEffect` 加载
- **SSE 章节流** `GET /api/v2/novel/{id}/chapters/stream`
- **BS4 选择器** 只用 `select_one`/`select`（CSS 选择器），不用 `find`/`find_all`
- **CSS flex 陷阱** flex column 中 `flex-1` 不约束宽度，需 `min-w-0` + `overflow-hidden`；flex row 子元素默认 `min-width: auto`
- **提交** 中文消息，一个方面一条 commit，禁止 `git add -A`
- **配置** `app_data/config/` 下全部 YAML，不提交到 git
- **文档** 一律写在 `docs/` 下（按子目录分类），**绝不提交到 git**（`.gitignore` 已忽略 `docs/`）

## Public 迁移约定（novel-downloader-public）

- 迁移前**必读** `PUBLIC_MANIFEST.md`（白名单 = 允许复制；红名单 = 禁止；未列出一律不迁移）
- **每次迁移先输出「本次迁移清单」**：本次复制文件/目录列表（来源→目标）+ 依据条目 + 红名单确认，供用户审查
- 复制完**必跑** `python scripts/check_public.py`（三道防线：缺失/多余/敏感），通过才允许在 public 仓库提交
- public 仓库（同级 `novel-crawler/`）独立提交/推送，不混入 private 的 commit 习惯
- 敏感判定：`api` 书源（oiapi/rain）、`app_data`、私有配置、`docs/superpowers`、`AGENTS.md` 一律不进 public

## Notes

