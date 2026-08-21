# PUBLIC_MANIFEST — 公开迁移白名单（.gitignore 的反面）

> `novel-downloader-public` 公开仓库的迁移依据。**Agent 迁移前必读本文件**。
> 白名单 = 允许复制到 public；红名单 = 禁止复制。**未列出的文件一律不迁移**。
> 每次迁移前，Agent 必须另行输出「本次迁移清单」（本次实际复制列表 + 依据条目 + 红名单确认）。

## 白名单（允许复制）

### 源码

- `novelbase/**`
  - **排除**：`novelbase/sources/qidian/**`、`novelbase/sources/qimao/**`、`novelbase/sources/92xs/**`、`novelbase/sources/fanqie/api/**`
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
- `CHANGELOG.md`

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
