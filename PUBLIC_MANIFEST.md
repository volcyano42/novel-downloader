# PUBLIC_MANIFEST — 公开迁移白名单（.gitignore 的反面）

> `novel-crawler` 公开仓库的迁移依据。**Agent 迁移前必读本文件**。
> 白名单 = 允许复制到 public；红名单 = 禁止复制。**未列出的文件一律不迁移**。
> 每次迁移前，Agent 必须另行输出「本次迁移清单」（本次实际复制列表 + 依据条目 + 红名单确认）。

## 白名单（允许复制）

### 源码

- `novelbase/**`
  - **排除**：`novelbase/sources/qidian/**`、`novelbase/sources/qimao/**`、`novelbase/sources/92xs/**`、`novelbase/sources/fanqie/api/**`、`novelbase/utils/_manifest.py`（书源清单，含未公开书源信息）
  - 保留：`novelbase/sources/fanqie/browser/**`、`novelbase/sources/fanqie/requests/**`
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
- `pyproject.toml`
- `requirements.txt`
- ~~`CHANGELOG.md`~~（不迁移：公开仓库 changelog 从 1.0.0 空开始）

## 迁移规则

- **版本号改写**：迁移后 `novelbase/__init__.py` 的 `__version__` 必须与 `pyproject.toml` 的 `version` 一致（public 当前 1.0.0）；`check_public.py` 防线 4 会校验，不一致报 `[版本]` 错误

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
- 任何含 `api` 书源（oiapi/rain）、密钥字样、逆向/破解实现的内容
