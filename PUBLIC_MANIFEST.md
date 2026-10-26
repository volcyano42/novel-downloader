# PUBLIC_MANIFEST — 公开迁移白名单（.gitignore 的反面）

> `novel-crawler` 公开仓库的迁移依据。**Agent 迁移前必读本文件**。
> 白名单 = 允许复制到 public；红名单 = 禁止复制。**未列出的文件一律不迁移**。
> 每次迁移前，Agent 必须另行输出「本次迁移清单」（本次实际复制列表 + 依据条目 + 红名单确认）。

## 白名单（允许复制）

### 源码

- `novelbase/**`
  - **排除**（2026-09-30 按扁平化后的一层目录名修正）：`novelbase/sources/qidian_requests_default/**`、`novelbase/sources/qidian_browser_default/**`、`novelbase/sources/qimao_requests_default/**`、`novelbase/sources/qimao_browser_default/**`、`novelbase/sources/qimao_api_rain/**`、`novelbase/sources/92xs_requests_default/**`、`novelbase/sources/fanqie_api_rain/**`、`novelbase/utils/_manifest.py`（书源清单，含未公开书源信息）
  - **2026-10-14 变更**：`novelbase/sources/fanqie_api_oiapi/**` **移出排除、进入白名单**（用户决定公开）—— 它是公开第三方服务 `https://oiapi.net/api/FqRead` 的封装，`key` 由用户在 `sources/*.yaml` 自备（仓库内为空占位），**非逆向/破解实现**；同时放开它依赖的 `template/config/sources/fanqie-api-oiapi.yaml` 与 `tests/test_source_oiapi_contract.py`。其余 `api` 书源（`*/api_rain/**`）**仍排除**，与 `AGENTS.md` 的「不公开逆向/破解实现」一致
  - 保留：`novelbase/sources/fanqie_browser_default/**`、`novelbase/sources/fanqie_requests_default/**`、`novelbase/sources/fanqie_api_oiapi/**`（2026-10-14 起）
  - ⚠️ 排除项**必须**用扁平化后的实际目录名：旧的四层路径（如 `novelbase/sources/qidian/**`）在 `check_public.py` 的 `fnmatch` 下匹配不到任何文件，会让这些源被判成白名单**必需内容**，闸门反过来报「缺失」——照提示补齐即泄漏

> **机器可读清单**：全部排除项（白名单内排除 + 红名单工具项）以 `pyproject.toml` 的 `[tool.novel-downloader.migration] exclude` 为唯一数据源，`check_public.py` 从此读取，本文件的排除列表需与其保持一致。
- `backend/**`
- `frontend/**`
  - **排除**：`frontend/node_modules/**`、`frontend/dist/**`
- `cli/**`
- `shared/**`
- `scripts/**`
  - **排除**：`scripts/migrate_public.py`（2026-10-14：内部迁移工具，与 `check_public.py` 配合使用；不进 public）
- `tests/**`
  - **排除**（2026-10-14 按 public 侧实跑补齐；public 只保留 fanqie 系的源，下列文件整体失败）：`tests/test_source_async.py`、`tests/test_source_contracts.py`、`tests/test_browser_sources.py`、`tests/test_source_layout.py`、`tests/test_backend_download_routes.py`、`tests/test_backend_config_routes.py`、`tests/test_config_effective_mode.py`、`tests/test_cli_effective_mode.py`、`tests/test_source_api.py`、`tests/test_novel_id_stability.py`、`tests/test_task_manager_async.py`、`tests/test_source_names_unique.py`、`tests/test_delay_default.py`（`tests/test_source_oiapi_contract.py` 已随 oiapi 源进入白名单）
- `init_config.py`（2026-10-14 补：运行必需 —— `backend/main.py` 的 lifespan 用它做首次配置初始化，`tests/test_paths.py` 也依赖它）
- `template/**`（2026-10-14 补：配置模板，public 靠它初始化 `app_data/config`）
  - **排除**（含未公开源名的站点配置）：`template/config/sources/92xs-requests-default.yaml`、`template/config/sources/fanqie-api-rain.yaml`、`template/config/sources/qidian-browser-default.yaml`、`template/config/sources/qidian-requests-default.yaml`、`template/config/sources/qimao-api-rain.yaml`、`template/config/sources/qimao-browser-default.yaml`、`template/config/sources/qimao-requests-default.yaml`（`fanqie-api-oiapi.yaml` 已随 oiapi 源进入白名单）

### workflow

- `.github/workflows/**`

### 根文件

- `LICENSE`
- ~~`pyproject.toml`~~（不迁移：版本元数据由 public 自行维护，不在迁移清单内）
- `requirements.txt`
- `init_config.py`（运行必需，见上）
- ~~`CHANGELOG.md`~~（不迁移：public 自维护。**每次同步后须在 public 侧补对应版本段** —— 版本号与 `novelbase/__init__.py` 的 `__version__` 一致（2026-10-14 起对齐，此前是独立的 `1.0.x` 版本线），内容只写可公开的变化）
- ~~`README.md`~~（2026-10-14 改判：private 根**没有** README.md，它是 public 自维护文件，已移入下方「public 自维护文件」）

## public 自维护文件（白名单外允许存在）

`check_public.py::PUBLIC_ONLY_FILES` 登记；迁移时既不复制也不删除：

- `README.md`（private 不提供）、`.gitignore`、`CHANGELOG.md`、`CONTRIBUTING.md`

## 迁移规则

- **迁移是「同步」而非「只增」**（2026-10-14 明确）：public 中既不在白名单、也不在「public 自维护」清单里的文件一律**删除**（清掉历史残留 —— 旧四层书源目录 `novelbase/sources/fanqie/**`（含旧结构的 `api/oiapi`、`api/rain` 实现）、`android/**`、`app.py`、`main.py`、`cli.py`、`backend/routers/engine.py`、`docs/add_source.md`、旧 `template/config/sites/fanqie.yaml` 等）
- **版本号**：`pyproject.toml` 不迁移，public 的版本由 `novelbase/__init__.py` 的 `__version__` 与 public 自行维护的 `pyproject.toml` 决定；迁移时无需改写版本号

### 文档

- `docs/README.md`
- `docs/project/**`
- `docs/build/**`
  - **排除**：`docs/build/docker.md`（2026-10-14：配套 `Dockerfile` / `.dockerignore` 不在白名单，且该工作在工作区尚未提交 —— 待完成并审阅后再放开）
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
