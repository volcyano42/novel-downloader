# PUBLIC_MANIFEST — 公开迁移白名单（.gitignore 的反面）

> `novel-crawler` 公开仓库的迁移依据。**Agent 迁移前必读本文件**。
> 白名单 = 允许复制到 public；红名单 = 禁止复制。**未列出的文件一律不迁移**。
> 每次迁移前，Agent 必须另行输出「本次迁移清单」（本次实际复制列表 + 依据条目 + 红名单确认）。

## 白名单（允许复制）

### 源码

- `novelbase/**`
  - **排除**：`novelbase/sources/qidian/**`、`novelbase/sources/qimao/**`、`novelbase/sources/92xs/**`、`novelbase/sources/fanqie/api/rain/**`、`novelbase/utils/_manifest.py`（书源清单，含未公开书源信息）
  - 保留：`novelbase/sources/fanqie/api/oiapi/**`、`novelbase/sources/fanqie/browser/**`、`novelbase/sources/fanqie/requests/**`

> **机器可读清单**：全部排除项（白名单内排除 + 红名单工具项）以 `pyproject.toml` 的 `[tool.novel-downloader.migration] exclude` 为唯一数据源，`check_public.py` 从此读取，本文件的排除列表需与其保持一致。
- `backend/**`
- `frontend/**`
  - **排除**：`frontend/node_modules/**`、`frontend/dist/**`
- `cli/**`
- `shared/**`
- `android/**`
  - **排除**：`android/.gradle/**`、`android/app/build/**`、`android/local.properties`、`android/keystore.properties`、`android/*.jks`
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
- `*.log`（构建日志）
- `.reasonix/**`、`.codegraph/**`、`.superpowers/**`、`.refer/**`
- 任何含 `api` 书源（rain）、密钥字样、逆向/破解实现的内容
