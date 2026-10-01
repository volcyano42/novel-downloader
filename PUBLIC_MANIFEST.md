# PUBLIC_MANIFEST — 公开迁移白名单（.gitignore 的反面）

> `novel-crawler` 公开仓库的迁移依据。**Agent 迁移前必读本文件**。
> 白名单 = 允许复制到 public；红名单 = 禁止复制。**未列出的文件一律不迁移**。
> 每次迁移前，Agent 必须另行输出「本次迁移清单」（本次实际复制列表 + 依据条目 + 红名单确认）。

## 白名单（允许复制）

### 源码

- `novelbase/**`
  - **排除**（2026-09-30 按扁平化后的一层目录名修正）：`novelbase/sources/qidian_requests_default/**`、`novelbase/sources/qidian_browser_default/**`、`novelbase/sources/qimao_requests_default/**`、`novelbase/sources/qimao_browser_default/**`、`novelbase/sources/qimao_api_rain/**`、`novelbase/sources/92xs_requests_default/**`、`novelbase/sources/fanqie_api_rain/**`、`novelbase/sources/fanqie_api_oiapi/**`（`api` 书源一律不进 public，与 `AGENTS.md` 一致）、`novelbase/utils/_manifest.py`（书源清单，含未公开书源信息）
  - 保留：`novelbase/sources/fanqie_browser_default/**`、`novelbase/sources/fanqie_requests_default/**`
  - ⚠️ 排除项**必须**用扁平化后的实际目录名：旧的四层路径（如 `novelbase/sources/qidian/**`）在 `check_public.py` 的 `fnmatch` 下匹配不到任何文件，会让这些源被判成白名单**必需内容**，闸门反过来报「缺失」——照提示补齐即泄漏

> **机器可读清单**：全部排除项（白名单内排除 + 红名单工具项）以 `pyproject.toml` 的 `[tool.novel-downloader.migration] exclude` 为唯一数据源，`check_public.py` 从此读取，本文件的排除列表需与其保持一致。
- `backend/**`
- `frontend/**`
  - **排除**：`frontend/node_modules/**`、`frontend/dist/**`
- `cli/**`
- `shared/**`
- `scripts/**`
- `tests/**`

### workflow

- `.github/workflows/**`

### 根文件

- `README.md`
- `LICENSE`
- ~~`pyproject.toml`~~（不迁移：版本元数据由 public 自行维护，不在迁移清单内）
- `requirements.txt`
- ~~`CHANGELOG.md`~~（不迁移：公开仓库 changelog 从 1.0.0 空开始）

## 迁移规则

- **版本号**：`pyproject.toml` 不迁移，public 的版本由 `novelbase/__init__.py` 的 `__version__` 与 public 自行维护的 `pyproject.toml` 决定；迁移时无需改写版本号

### 文档

- `docs/README.md`
- `docs/project/**`
- `docs/build/**`
- `docs/conventions/**`

## 红名单（禁止，双保险）

- `app_data/**`
- `.env`
- `会话归档/**`
- `AGENTS.md`
- `docs/superpowers/**`
- `docs/session-prompt.md`
- `docs/learning/**`
- `docs/planning/**`（发展方向分析：含对仓库可见性、书源合规风险、红名单书源的自我披露）
- `*.log`（构建日志）
- `.reasonix/**`、`.codegraph/**`、`.superpowers/**`、`.refer/**`
- 任何含 `api` 书源（rain）、密钥字样、逆向/破解实现的内容
