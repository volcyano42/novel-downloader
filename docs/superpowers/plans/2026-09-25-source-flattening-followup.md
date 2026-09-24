# 书源扁平化 — 遗留改造（backend / CLI / 前端 / 配置）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已扁平化的 core（`novelbase/source.py` 4-API + `downloader` 新签名）向 backend / CLI / 前端 / 配置收口——删除全部 `platform`/`mode(variant)` 过渡符号，落地「书源 = `source_name`」「`mode` 由书源声明」「三层配置合并」「`enabled` 用户层覆盖」「搜索并发全启用书源」「书源管理界面」。

**Architecture:** 配置层（`shared/config.py`）是地基：新增 `merged_source_config(source_name)`（三层合并）与 `enabled_source_names()`（启用集单一入口）。backend 的 `engine_manager`/`task_manager`/`download` 路由 / `config` 路由全部改以 `source_name` 为键、`mode` 从 `capabilities(source_name)` 取。CLI 复用 `shared.config`，子命令 `--platform/--mode/--variant` → `--source`。前端末尾收口：先定 api/hooks 类型，再改 UI，最后加书源管理界面。

**Tech Stack:** Python 3.10+、FastAPI、pytest、argparse、PyYAML；React 18 + TypeScript + TanStack Query（`frontend/`，Vite）。

**Scope（分批）：**
- 批次 A（地基）：Task 1-3（契约冻结、配置层、搜索历史）
- 批次 B（backend）：Task 4-8（engine_manager、task_manager、schemas、download 路由、engine/config 路由）
- 批次 C（CLI）：Task 9-11（config/core、main、interactive/menus）
- 批次 D（前端）：Task 12-14（api/hooks/cache、UI、书源管理界面）
- 批次 E（docs）：Task 15

---

## 非目标

- **不改书源实现**：`novelbase/sources/*/`（`source.json` 与能力 `.py`）不动。
- **不改导出器**：`novelbase/exporters/*`、`novelbase/exporter.py`、`app_data/config/formats/*.yaml` 不动。
- **不改 Android**：`android/` 不动。
- **不改 core**：`novelbase/source.py`、`novelbase/core/*`、`novelbase/models/*` 除「删除 `split_source_name`/`resolve_source_name`」外不动（Task 2 一并删）。
- **不做兼容层**：旧 `{platform}-{mode}-{variant}` 语义、旧 `sites/{platform}.yaml`、旧 `search_history` 一律抛弃，不留 shim。
- **不迁移用户数据**：`app_data/config/sites/*.yaml`、`search_history` 直接丢/重建。

---

## Global Constraints

以下约束对每个任务都成立；每条都给出它为什么存在。

1. **不得改变任何书源返回的 url**。`Novel.id = make_novel_id(novel.url) = sha256(url)[:32]`，库内 `meta.id` 存该 url 原样。
   *Why:* 改变书源返回的 url = `novel_id` 漂移 = 已有书籍的书架/收藏/分组/阅读进度/下载目录/已导出文件全部对不上。本次改造不碰书源实现，也不得在 backend/CLI 侧做任何 URL「规范化」。
2. **不做旧结构兼容层**。旧 `{platform}-{mode}-{variant}` 名称解析、旧 `sites/{platform}.yaml`（三段 + variant 容器）、旧 `search_history`（`platform/mode/variant` 列）全部直接删除。
   *Why:* 这是一次性切换；留兼容层会让两套语义长期共存、`/download/sources` 的形状歧义永远修不掉（当前前端正是因为「扁平值被当对象」而全空）。
3. **字段命名全链保持 `retry_times`**，不引入 `max_retry`。
   *Why:* 与 `novelbase/core/options.py`、`ENGINE_DEFAULTS`、`source.json` 校验（`manifest.py:16`）、前端表单一致；改名会在配置合并各层之间引入映射 bug。
4. **前后端契约必须先定稿再两侧实现**。契约定稿 = `docs/superpowers/specs/2026-09-25-source-flattening-followup-design.md` §3 的 API 表（Task 1 冻结）。前端任务只引用该表，不得自行发明字段。
   *Why:* `/download/sources` 已是「后端返回扁平 `{cap→mode}`、前端按 `{mode:{variant:[]}}` 解析」的破契约；两侧不同步 = 运行时静默全空或崩溃。
5. **验收口径**：① **每个任务结束后** `python -m pytest tests/ -q` 必须 **0 failed**（`skipped` 可保留；**passed 总数可因合理删除废弃用例低于 379**，基线 `379 passed, 1 skipped`）——中间态窗口（T2–T11）只要求**本任务相关子集 0 failed**，全量 `0 failed` 在 T15 收敛；每个任务在正文「各任务删除用例与预期 passed」表中给出删除用例与预期区间，T15 给最终区间；② `cd frontend; npx tsc --noEmit --project tsconfig.app.json` 通过；③ 涉及构建时 `npm run build` 通过。
   *Why:* 379/1skip 是 `dev` 实测回归基线；tsc 是前端类型契约的唯一自动校验（无前端单测）。
6. **提交纪律**：commit 消息用中文；一个方面一条 commit；禁止 `git add -A`（显式列文件）；中文消息用 `git commit -F <文件>` 传入。
   *Why:* 项目 `docs/conventions/git.md` 约定。
7. **前端契约两侧同步**：`/download/sources`、`/download/search`、`/config/sources/{name}` 的字段名在 backend 与 `endpoints.ts` 必须逐字一致（`source_name`/`enabled`/`capabilities`/`config`）。
   *Why:* 现状正是两侧形状不一致（后端扁平 `{cap→mode}`、前端当 `{mode:{variant:[]}}`）导致前端模式列表全空（L1）；本次重定契约若再不对齐，前端 tsc 不报错但运行时静默错。
8. **模板库 `user_data.db` schema 必须与运行时逐列一致**：`template/storage/users/default/user_data.db` 的 `search_history` 须与新 schema 相同，且 `CREATE TABLE IF NOT EXISTS` 对已存在表无效——必须 `DROP TABLE search_history` 后重建（或删库重生成）。
   *Why:* `test_user_db_template.py::test_template_schema_matches_runtime` 做结构级对比（列 + 索引 + `user_version`）；模板库不真正重建则该测试红。
9. **`init_config.py` 的模板计数依赖 `template/` 下 `*.yaml` 的 glob**（`init_config.py:83` `template.rglob("*.yaml")`）：改 `template/config/sites/*.yaml` 的**数量/命名**会改变 `check_config()` 的 `missing`/`all_missing` 判定。
   *Why:* 从 4 个 sites 文件变 10 个（按 `source_name` 命名）会改变初始化行为与计数；需一并核对 `init_config` 与其测试。
10. **删除函数/模块的「同 commit 清 import」坑**（三条）：
    - `schemas/engine.py` 删除必须与「删 `engine.py` 路由 + `main.py:83` 注册」同一 commit（T8），否则 `backend.main` import 崩、`test_android_server.py` 全红。
    - **T2 删除 `shared.config` 的 `get_mode_variant_config`/`mode_variants`/`find_variant_options` 时，必须同 commit 清理其顶层 import 者**：`backend/services/engine_manager.py:16`、`cli/config.py:17`（已核实全库仅此两处顶层 `from shared.config import <被删名>`；`backend/routers/config.py:5` 是 `import shared.config as config_service` 未 import 具体名、import 不崩但调用点归 T8；`cli/config.py:199` 体内 import 随 `mode_variants` 函数删除）。
    - **`backend/routers/download.py` 的两处顶层 import 必须随删符号的所在任务清**：T2 删 `resolve_source_name` 时清 `download.py:11`；T4 删 `get_cached_engine_for_source` 时清 `download.py:8`（最小过渡见 T2/T4）。两任务提交后 `python -c "import backend.main"` 与 `pytest tests/ -q --co` 均不得崩。
   *Why:* `from shared.config import <被删名>` 在 import 期解析，名字不存在直接 `ImportError` → `backend.main`/`cli` 全崩 → 测试收集失败（比普通中间态红严重）。

---

## 文件结构

**新建**

| 文件 | 职责 |
|---|---|
| `frontend/src/features/sources/SourcesPage.tsx` | 书源管理界面（列表 + `enabled` 开关 + 编辑该书配置） |
| `template/config/sites/{10 个 source_name}.yaml` | 与新逐能力段结构一致的用户配置模板（`fanqie-api-rain.yaml` / `92xs-requests-default.yaml` …） |
| `tests/test_source_enabled.py` | `enabled_source_names()` / `is_source_enabled()` 的单元测试 |

**修改（Python）**

| 文件 | 改动 |
|---|---|
| `novelbase/source.py` | 删 `split_source_name`(198) / `resolve_source_name`(214) / `__all__` 两项(30) |
| `shared/config.py` | 三层合并 `merged_source_config`；`enabled_source_names`/`is_source_enabled`；删 `mode_variants`(194)/`find_variant_options`(201)/`get_mode_variant_config`(167)/`load_mode_config`(188)；`GLOBAL_DEFAULTS` 去 `mode`(68)；`build_options` 重写 |
| `shared/user_data.py` | `search_history` 重建（`source_name`+`keyword`）；删 `_migrate_search_history`(84-119)；`add_search_history(source_name, keyword)` |
| `backend/routers/history.py` | `SearchHistoryAddRequest{source_name, keyword}`；输出 `source_name` |
| `backend/services/engine_manager.py` | 按 `source_name` 缓存/建引擎（`_fingerprint`/`get_cached_engine`/`create_engine_for_request`/`invalidate_engine` 改二参）；删 `get_cached_engine_for_source`(88) 与 explicit engine 段（`_explicit_engines`(110)、`_build_options`(196-216)、`_build_sub_options`(219-238)、`list_explicit_engines`(241-245)、`create_explicit_engine`(248-254)、`get_explicit_engine`(257-261)、`update_explicit_engine`(264-274)、`delete_explicit_engine`(277-286)）。**保留** `_linux_default_browser_args`(117-121)。**T2 阶段先清 16 行顶层 import**（见 T2） |
| `backend/services/task_manager.py` | `_run_download(task, source_name)`；任务字段 `_source`；`create_task(..., source_name, novel_url)` |
| `backend/schemas/download.py` | `SearchResultData.platform`(10) → `source_name` |
| `backend/routers/download.py` | `source` Query；并发全启用搜索；`/download/sources` 新形状；删 `/platform`(171)/`/detect`(194)/`_pick_source`(16) |
| `backend/routers/config.py` | `/config/sources/{name}` GET/PUT；`/config` 去 `mode` |
| `backend/routers/engine.py` | **删除全文件** |
| `backend/schemas/engine.py` | **删除全文件** |
| `backend/schemas/__init__.py` | 删 engine schema 导入(5-8) |
| `backend/main.py` | 删 `include_router(engine.router)`(16,83) |
| `cli/config.py` | 删 `mode_variants`(197)/`resolve_variant`(203)；`build_options(source_name, mode)` 走 `shared.config`。**T2 阶段先清 17 行顶层 import**（见 T2） |
| `cli/core.py` | `_make_engines(source_name)`/`_get_engine(source_name, mode)`；删 `split_source_name`(62) |
| `cli/main.py` | 子命令 `--source`；`search` 默认并发；`_scaffold_source` 重写；删 `_resolve_platform`/`_source_name`/`_resolve_variant`/`_scaffold_variant`/`new-variant` |
| `cli/interactive.py` | 并发全启用搜索；手选书源；删 `do_visit_site`(244)；`source_name` 读法 |
| `cli/menus.py` | 设置菜单改书源维度；删 mode/variant 设置 |
| `template/config/config.yaml` | 删 `mode`(5) |
| `template/storage/users/default/user_data.db` | 重建（`DROP TABLE search_history` 后按新 schema 重建，或删库重生成） |

**修改（前端）**

| 文件 | 改动 |
|---|---|
| `frontend/src/api/endpoints.ts` | `SearchResult.source_name`；`SiteConfig`→`SourceConfig`；`getSiteConfig`(24)/`saveSiteConfig`(34)→`getSourceConfig`/`saveSourceConfig`；请求参数 `source`；`fetchSources` 新形状；`/config/sources`；`SearchHistoryItem.source_name`；删 `GlobalConfig.mode`(72) 与 `EngineInfo`(88) |
| `frontend/src/utils/sessionCache.ts` | `nd:mode/nd:variant/nd:search:mode/nd:search:variant/nd:search:platform` → `nd:search:source`；删 `getSearchPlatform` |
| `frontend/src/hooks/index.ts` | `useSearch`/`useRemoteChapters`/`useAddSearchHistory`/`useDownloadMutation`/`useFetchMeta` 参数改 `source`；**删 `usePlatforms`(109-115)**；`useSiteConfig`/`useSaveSiteConfig` 改名为 `useSourceConfig`/`useSaveSourceConfig`；新增 `useSources`(117-123) 保留 |
| `frontend/src/features/bookshelf/SearchBar.tsx` | 删 mode/variant/域名探测；标题=并发、URL=手选书源 |
| `frontend/src/features/bookshelf/BookshelfPage.tsx` | 删 `modeVariants/platformModes/allEngineModes`(52-81)；删 `SessionCache.getMode/getVariant/getSearchParams`(88-89,105-108) 与 `searchParams.platform`(316,321,323)；结果 tab 用 `r.source_name` |
| `frontend/src/features/bookshelf/SearchHistoryPanel.tsx` | 显示 `source_name` |
| `frontend/src/features/download/DownloadDialog.tsx` | 删 mode/variant 询问 |
| `frontend/src/features/detail/DetailPage.tsx` | 删 `platformFromUrl`(26-33,55,271,289)、`searchMode/searchVariant`(44,46-47,65)、`platModes/platVariantsByMode`(56-64,489)、`sessionStorage nd:mode/nd:variant`(297-306)、`globalConfig.mode`(297,302,305,308)、`SessionCache.setMode/setVariant`(313-314)；只带 `source_name` |
| `frontend/src/features/settings/SettingsPage.tsx` | 删「下载模式」与 `EngineSection` 平台维度；按书源编辑配置 |
| `frontend/src/App.tsx` | 侧栏项 + `/sources` 路由 |

**修改（测试，需同步改写）**

| 文件 | 改动 | 任务 |
|---|---|---|
| `tests/test_source_api.py` | 删 `test_split_source_name`(96)/`test_resolve_source_name`(104) | T2 |
| `tests/test_site_config.py` | 重写：`get_mode_variant_config`/`mode_variants`/`load_mode_config` 删除；改测三层合并 | T2 |
| `tests/test_shared_user_data.py` | 重写：`search_history` 的 `source_name` 键；删旧迁移用例(82-133) | T3 |
| `tests/test_user_db_template.py` | 模板 schema 与新 `search_history` 一致 | T3 |
| `tests/test_engine_manager.py` | `_fingerprint`/`create_engine_for_request`/`get_cached_engine` 新签名 | T4 |
| `tests/test_task_manager_async.py` | `create_task` 的 `source_name` 参数、`_stub(task, source_name)`、task `_source` | T5 |
| `tests/test_backend_download_routes.py` | 重写：`get_cached_engine_for_source` 删除、`platform`→`source`、`/sources` 形状 | T7 |
| `tests/test_cli_variant.py` | 重写 `cli.config` 部分（`resolve_variant`/`build_options(variant)` 删除，T9）；删 `cli.main._resolve_variant` 用例(104-127)（T10） | T9/T10 |
| `tests/test_cli_dev_new_variant.py` | 重写：`_scaffold_variant` 删除、`_scaffold_source` 新结构 | T10 |
| `tests/test_interactive_cli.py` | `do_search`/`_get_delay`/`_set_delay`/`_show_platforms` 按新行为 | T11 |
| `tests/test_cli_storage.py` | `cli.config.build_options(cfg, site_cfg)`(50,60) 改 `build_options(source_name, mode)` | T9 |
| `tests/test_engine_manager.py` | 删 `test_build_options_passes_auto_reconnect`(62-66)（依赖已删的 `_build_options`/`backend.schemas.engine`） | T4 |
| `tests/test_user_db_template.py` | 删 `_migrate_search_history` import(62)/调用(69)；模板 schema 与新 `search_history` 一致 | T3 |

不红（勿动，已核实）：`test_source_layout.py`、`test_source_manifest.py`、`test_downloader.py`、`test_models.py`、`test_exceptions.py`、`test_storage.py`、`test_export_config.py`、`test_exporter.py`、`test_encoding.py`、`test_urls.py`、`test_engine_reconnect.py`、`test_engine_httpx.py`、`test_novel_id_stability.py`、`test_source_contracts.py`、`test_source_async.py`、`test_browser_sources.py`、`test_android_server.py`、`conftest.py`、`check_imports.py`（只断言 10 个书源名，不依赖被删符号）。

---

### 各任务删除用例与预期 passed

> 基线 `379 passed, 1 skipped`。下表给出每个任务**删除/改写的测试用例**与**预期 passed 变化**（用于独立验证；判据始终是**该任务子集 `0 failed`**）。中间态任务（T2–T11）全量可能非绿，收口在 T15。数字为区间估算。

| 任务 | 删除/改写的用例 | 预期 passed |
|---|---|---|
| T1 | 无 | 379（基线） |
| T2 | 删 `test_source_api.py::test_split_source_name`/`test_resolve_source_name`(2)；重写 `test_site_config.py`（6→约 4）；新增 `test_source_enabled.py`(2) | ≈375（373–379） |
| T3 | 重写 `test_shared_user_data.py`：删 4 例（`test_search_history_dedup_same_key_upsert`/`test_search_history_dedup_mode_variant_distinct`/`test_search_history_migration_old_db`/`test_search_history_migration_guard_keeps_new_records`），新增 source_name 键用例(2)；`test_user_db_template.py` 改 import | ≈373（371–377） |
| T4 | 删 `test_engine_manager.py::test_build_options_passes_auto_reconnect`(1)；其余 2 例改签名 | ≈372（370–376） |
| T5 | `test_task_manager_async.py` 改写（不删例数） | 不变 |
| T6 | 无 | 不变 |
| T7 | 重写 `test_backend_download_routes.py`（8→约 6） | ≈370（366–374） |
| T8 | 无删除（重写 config 用例） | 不变 |
| T9 | 重写 `test_cli_variant.py` cli.config 部分：删 `test_resolve_variant_*`(4)/`test_build_options_*_variant`(4)；`test_cli_storage.py` 2 例改签名 | ≈364（360–370） |
| T10 | 删 `test_cli_variant.py::test_main_resolve_variant_*`(3,104-127)；重写 `test_cli_dev_new_variant.py`（10→约 2） | ≈353（348–362） |
| T11 | `test_interactive_cli.py` 改写（不删例数） | 不变 |
| T12 | 无 pytest（前端） | 不变（判据=tsc） |
| T13 | 无 pytest（前端） | 不变（判据=tsc） |
| T14 | 无 pytest（前端） | 不变（判据=tsc） |
| T15 | 无删除 | 最终 ≈350–365 passed, 1 skipped, 0 failed |

---

## Task 1: 前后端契约定稿（冻结 spec §3 API 表）

**Files:**
- Read: `docs/superpowers/specs/2026-09-25-source-flattening-followup-design.md`（§3 API 契约表）
- Verify: 全文（本任务无代码改动，只做契约冻结与交叉核对）

**Interfaces:**
- Produces: 冻结的契约表（`/download/sources` 新形状、`/download/search` 的 `source` 语义、`/config/sources/{name}` GET/PUT、`/history/search` 的 `source_name`、`SearchResultData.source_name`）。后续所有 backend/前端任务引用它。

- [ ] **Step 1: 核对契约表与源码现状一致**

Run: `python -m pytest tests/test_source_api.py -q`
Expected: PASS（确认 core 4-API 的键 = `source_name`，是契约的基础）。

- [ ] **Step 2: 核对删除面**

Run: `rg -n "detect|/api/v2/engine" frontend/src`
Expected: 无输出（前端无 `/detect`、`/engine` 调用点）。另跑 `rg -n "EngineInfo" frontend/src` 应**仅命中 `endpoints.ts:88` 的类型定义行**（无使用），删除该类型即可。确认 D2 三处删除对前端零调用点波及；前端只需删 `SearchBar.tsx:135-142`、`DetailPage.tsx:26-33,55` 的本地域名映射。

- [ ] **Step 3: 记录并冻结**

在 spec 文件头部「状态」一行确认「契约定稿」；若核对发现任何与源码不符之处，先改 spec 再继续。

- [ ] **Step 4: 提交**

```bash
git add docs/superpowers/specs/2026-09-25-source-flattening-followup-design.md docs/superpowers/plans/2026-09-25-source-flattening-followup.md
git commit -F .git/COMMIT_MSG   # 内容：docs: 冻结书源扁平化遗留改造契约与实施计划
```

---

## Task 2: 配置层——三层合并 + `enabled` 覆盖 + 删过渡符号

**Files:**
- Modify: `shared/config.py`
- Modify: `novelbase/source.py`（删 `split_source_name`/`resolve_source_name`）
- Modify: `template/config/config.yaml`（删 `mode`）
- Modify: `backend/services/engine_manager.py`（**仅清 16 行顶层 import**，否则 T2 提交后 `backend.main` import 崩）
- Modify: `cli/config.py`（**仅清 17 行顶层 import**，否则 T2 提交后 `cli` import 崩）
- Modify: `backend/routers/download.py`（**仅清 11 行顶层 import + `_pick_source` 退化为直通 `source`**，否则 T2 提交后 `backend.main` import 崩）
- Create: `template/config/sites/{10 个 source_name}.yaml`（替换 `fanqie.yaml/qidian.yaml/qimao.yaml/92xs.yaml`）
- Test: `tests/test_site_config.py`（重写）、`tests/test_source_api.py`（删两例）、Create `tests/test_source_enabled.py`

> `tests/check_imports.py` 只断言 10 个书源名（`list_sources()`），不依赖被删符号，**无需改**（不列入本任务）。

**Interfaces:**
- Consumes: `novelbase.source.list_sources()`, `get_manifest(source_name)`, `capabilities(source_name)`
- Produces:
  - `shared.config.merged_source_config(source_name: str) -> dict[str, dict]` — 返回 `{capability: 该能力段三层合并后的完整字段}`；未知书源返回 `{}`
  - `shared.config.is_source_enabled(source_name: str) -> bool` — 见 spec §4.2
  - `shared.config.enabled_source_names() -> list[str]` — 排序后的启用 `source_name` 列表（唯一入口）
  - `shared.config.load_site_config(source_name: str) -> dict` / `save_site_config(source_name: str, cfg: dict) -> None` — 保留，语义按 `source_name`
  - `shared.config.build_options(source_name: str, mode: str) -> Options` — 用 `merged_source_config` 第 3 层 + `ENGINE_DEFAULTS[mode]` 组 `Options`
  - 删除：`get_mode_variant_config`、`load_mode_config`、`mode_variants`、`find_variant_options`；`GLOBAL_DEFAULTS` 去掉 `mode` 键

- [ ] **Step 1: 写失败测试**

```python
# tests/test_source_enabled.py（新建）
from shared import config as sc


def test_merged_source_config_three_layers(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr("novelbase.source.capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr("novelbase.source.get_manifest", lambda n: {
        "source_name": n, "enabled": True,
        "default_config": {"search": {"mode": "requests", "timeout": 30, "retry_times": 3}},
    })
    merged = sc.merged_source_config("demo-requests-default")
    assert merged["search"]["mode"] == "requests"
    assert merged["search"]["timeout"] == 30          # 第 2 层
    # 第 3 层覆盖
    sc.save_site_config("demo-requests-default", {"search": {"timeout": 99}})
    merged = sc.merged_source_config("demo-requests-default")
    assert merged["search"]["timeout"] == 99


def test_is_source_enabled_user_override(monkeypatch, tmp_path):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr("novelbase.source.list_sources", lambda: ["a-x-default"])
    monkeypatch.setattr("novelbase.source.get_manifest", lambda n: {"enabled": False})
    assert sc.is_source_enabled("a-x-default") is False                # 出厂 false
    sc.save_site_config("a-x-default", {"enabled": True})              # 用户层覆盖
    assert sc.is_source_enabled("a-x-default") is True
    assert sc.enabled_source_names() == ["a-x-default"]
```

```python
# tests/test_site_config.py（重写：删除 get_mode_variant_config/mode_variants/load_mode_config 用例）
# 只保留/新增对 merged_source_config + enabled 的断言（见上）。
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_source_enabled.py tests/test_site_config.py -q`
Expected: FAIL（`AttributeError: module 'shared.config' has no attribute 'merged_source_config'`）。

- [ ] **Step 3: 实现 `shared/config.py`**

新增：

```python
def _user_site_cfg(source_name: str) -> dict:
    return load_yaml(CONFIG_DIR / "sites" / f"{source_name}.yaml")


def merged_source_config(source_name: str) -> dict[str, dict]:
    from novelbase.source import capabilities, get_manifest
    caps = capabilities(source_name)
    if not caps:
        return {}
    manifest = get_manifest(source_name)
    user = _user_site_cfg(source_name)
    out: dict[str, dict] = {}
    for cap, mode in caps.items():
        base = deep_merge(ENGINE_DEFAULTS.get(mode, {}), manifest["default_config"][cap])
        user_cap = user.get(cap) if isinstance(user.get(cap), dict) else {}
        user_cap = {k: v for k, v in user_cap.items() if k != "mode"}  # mode 恒取书源声明
        out[cap] = deep_merge(base, user_cap)
    return out


def is_source_enabled(source_name: str) -> bool:
    from novelbase.source import get_manifest
    user = _user_site_cfg(source_name)
    if isinstance(user.get("enabled"), bool):
        return user["enabled"]
    return bool(get_manifest(source_name).get("enabled", False))


def enabled_source_names() -> list[str]:
    from novelbase.source import list_sources
    return sorted(n for n in list_sources() if is_source_enabled(n))
```

删除 `get_mode_variant_config`(167-185)、`load_mode_config`(188-191)、`mode_variants`(194-199)、`find_variant_options`(201-211)、`GLOBAL_DEFAULTS["mode"]`(68)。重写 `build_options(source_name, mode)`（243-308）以 `merged_source_config(source_name)[cap]` 取值。**删除** `load_platform_configs`(144-162) 与 `load_platform_raw`(164-165)（grep 确认全库无调用点；其实现依赖已删的 `get_mode_variant_config`/`mode_variants`）。**同 commit 清理顶层 import 者**：`backend/services/engine_manager.py:16` 改为 `from shared.config import load_site_config`；`cli/config.py:17` 整行删除（`cli/config.py` 的 `build_options` 旧实现留 T9 重写）。已核实全库仅此两处顶层 `from shared.config import <被删名>`。**T2 还要同 commit 清 `backend/routers/download.py:11` 的顶层 `resolve_source_name` import**：把该行改为 `from novelbase.source import resolve_book_url, list_sources`，并将 `_pick_source`(16-25) 退化为直通（`return platform`，不再调 `resolve_source_name`）——这是最小过渡，T7 把 `_pick_source` 整体删除、`source` Query 直通 `source_name`。

- [ ] **Step 4: 删 core 过渡符号 + 模板**

删 `novelbase/source.py:198-235`（`split_source_name`+`resolve_source_name`）与 `__all__`(30) 两项。
删 `template/config/config.yaml` 的 `mode: api`(5)。
删 `template/config/sites/{fanqie,qidian,qimao,92xs}.yaml`，新建 10 个 `template/config/sites/{source_name}.yaml`（内容 = 对应 `source.json.default_config` 展开 + 顶层 `enabled`）。
删 `tests/test_source_api.py:96-115`（`test_split_source_name`/`test_resolve_source_name`）。`tests/check_imports.py` 只断言 10 个书源名，**无需改**。

- [ ] **Step 5: 运行测试**

Run: `python -m pytest tests/test_source_enabled.py tests/test_site_config.py tests/test_source_api.py tests/test_user_db_template.py -q`
Expected: PASS（`test_user_db_template.py` 可能因 T3 尚未做而仍绿；若在此阶段已重跑模板库则同步）。

- [ ] **Step 6: 全量回归（确认 import 不崩 + 记录中间态）**

Run: `python -m pytest tests/ -q --co`（仅收集）
Expected: 收集**不报错**（`backend.main`/`cli` 均可 import——已清 `engine_manager.py:16`/`cli/config.py:17`/`download.py:11` 顶层 import）。若收集失败即为 import 崩，必须回 Step 3 修复。另单独跑 `python -c "import backend.main"` 与 `python -c "import cli.main"` 均不得抛 `ImportError`。

Run: `python -m pytest tests/ -q`
Expected: 中间态——`test_engine_manager`/`test_task_manager_async`/`test_backend_download_routes`/`test_cli_*` 等可在后续任务收口前红，但**不得有 collection error**。本任务相关子集（`test_source_enabled`/`test_site_config`/`test_source_api`）**0 failed**。记录 `passed/failed` 数。

- [ ] **Step 7: 提交**

```bash
git add shared/config.py novelbase/source.py template/config/config.yaml template/config/sites backend/services/engine_manager.py cli/config.py backend/routers/download.py tests/test_site_config.py tests/test_source_enabled.py tests/test_source_api.py
git rm -q template/config/sites/fanqie.yaml template/config/sites/qidian.yaml template/config/sites/qimao.yaml template/config/sites/92xs.yaml
git commit -F .git/COMMIT_MSG   # 内容：refactor(config): 三层合并 + enabled 覆盖，删 platform/mode/variant 遗留
```

---

## Task 3: 搜索历史改键（`source_name`）

**Files:**
- Modify: `shared/user_data.py`
- Modify: `backend/routers/history.py`
- Rebuild: `template/storage/users/default/user_data.db`
- Test: `tests/test_shared_user_data.py`（重写）、`tests/test_user_db_template.py`（删 `from shared.user_data import _migrate_search_history`(62) 与对其调用(69)）

**Interfaces:**
- Produces:
  - `shared.user_data.add_search_history(source_name: str, keyword: str) -> None` — 唯一键 `(source_name, keyword)` UPSERT
  - `search_history` 表：`id, source_name TEXT NOT NULL, keyword TEXT NOT NULL, searched_at`
  - `backend/routers/history.py::SearchHistoryAddRequest{source_name: str, keyword: str}`
  - `GET /history/search` item：`{id, source_name, keyword, searched_at}`
- Consumes: 无（T3 不依赖 T2）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_shared_user_data.py（重写核心用例）
def test_search_history_uses_source_name(tmp_path, monkeypatch):
    from shared import user_data
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")
    user_data.add_search_history("fanqie-api-rain", "斗破")
    user_data.add_search_history("fanqie-api-rain", "斗破")     # 同键 upsert
    user_data.add_search_history("92xs-requests-default", "斗破")
    rows = user_data.get_search_history()
    assert len(rows) == 2
    assert {r["source_name"] for r in rows} == {"fanqie-api-rain", "92xs-requests-default"}
    assert "mode" not in rows[0] and "variant" not in rows[0] and "platform" not in rows[0]
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_shared_user_data.py -q`
Expected: FAIL（`add_search_history` 目前签名 `(platform, keyword, mode, variant)`；行含 `platform/mode/variant`）。

- [ ] **Step 3: 改 `shared/user_data.py`**

`_SCHEMA_SQL` 的 `search_history`(44-51) 改为：

```sql
CREATE TABLE IF NOT EXISTS search_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name  TEXT NOT NULL,
    keyword      TEXT NOT NULL,
    searched_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source_name, keyword)
);
```

删 `_migrate_search_history`(84-119) 与 `_ensure_schema` 里对它的调用(75)。`add_search_history(source_name, keyword)`(246-255) 改 UPSERT 键为 `(source_name, keyword)`。**既有用户库需 drop 重建**：在 `_ensure_schema` 里若检出旧列 `platform`（`PRAGMA table_info`），执行 `DROP TABLE search_history` 后重建（一次性，见 spec §7）。

- [ ] **Step 4: 改 `backend/routers/history.py`**

`SearchHistoryAddRequest`(11-15) → `{source_name: str = "", keyword: str}`；GET 输出(46-53) 改 `source_name`；`_add(body.source_name, keyword)`(64)。

- [ ] **Step 5: 重建模板库（`DROP TABLE` 后重建）**

`CREATE TABLE IF NOT EXISTS` 对已存在表无效，必须显式 DROP。执行：

Run: `python -c "import sqlite3, shared.user_data as u; c=sqlite3.connect('template/storage/users/default/user_data.db'); c.execute('DROP TABLE IF EXISTS search_history'); c.executescript(u._SCHEMA_SQL); c.commit(); c.close()"`

验证（列名应为 `id/source_name/keyword/searched_at`）：

Run: `python -c "import sqlite3; print([r[1] for r in sqlite3.connect('template/storage/users/default/user_data.db').execute('PRAGMA table_info(search_history)')])"`
Expected: `['id', 'source_name', 'keyword', 'searched_at']`。

- [ ] **Step 6: 运行测试**

Run: `python -m pytest tests/test_shared_user_data.py tests/test_user_db_template.py -q`
Expected: PASS（先删 `test_user_db_template.py` 的 `_migrate_search_history` import(62) 与调用(69)，并改用 `_SCHEMA_SQL` 直接建表；模板已按 Step 5 重建，`test_template_schema_matches_runtime` 绿）。

- [ ] **Step 7: 提交**

```bash
git add shared/user_data.py backend/routers/history.py template/storage/users/default/user_data.db tests/test_shared_user_data.py tests/test_user_db_template.py
git commit -F .git/COMMIT_MSG   # 内容：refactor(user_data): search_history 改 source_name 键，drop 重建
```

---

## Task 4: `engine_manager` 按书源缓存/建引擎

**Files:**
- Modify: `backend/services/engine_manager.py`
- Modify: `backend/routers/download.py`（**仅清 8 行顶层 import + `_engines_for` 改用 `get_cached_engine(source_name, mode)`**，否则 T4 提交后 `backend.main` import 崩）
- Test: `tests/test_engine_manager.py`（删 `test_build_options_passes_auto_reconnect`(62-66)，依赖已删的 `_build_options`/`backend.schemas.engine`）

**Interfaces:**
- Consumes: `shared.config.merged_source_config(source_name)`（T2）
- Produces:
  - `engine_manager._fingerprint(source_name: str, mode: str) -> str`
  - `engine_manager.get_cached_engine(source_name: str, mode: str = "browser")`
  - `engine_manager.create_engine_for_request(source_name: str, mode: str = "browser")`
  - `engine_manager.invalidate_engine(source_name: str, mode: str = "browser") -> bool`
  - `engine_manager.clear_engine_cache()`（保留）
  - 删除：`get_cached_engine_for_source`(88-97)、explicit engine 段（`_explicit_engines`(110)、`_build_options`(196-216)、`_build_sub_options`(219-238)、`list_explicit_engines`(241-245)、`create_explicit_engine`(248-254)、`get_explicit_engine`(257-261)、`update_explicit_engine`(264-274)、`delete_explicit_engine`(277-286)）。**保留** `_linux_default_browser_args`(117-121) 与 `create_engine_for_request`(123-189，仅换签名)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_engine_manager.py（改写）
def test_get_cached_engine_by_source(monkeypatch):
    from backend.services import engine_manager as em
    em._engine_cache.clear()
    created = []
    def fake_create(source_name, mode="browser"):
        created.append((source_name, mode)); return object()
    monkeypatch.setattr(em, "create_engine_for_request", fake_create)
    e1 = em.get_cached_engine("fanqie-api-rain", "api")
    e2 = em.get_cached_engine("fanqie-api-rain", "api")
    assert e1 is e2 and created == [("fanqie-api-rain", "api")]
    em._engine_cache.clear()


def test_fingerprint_source_and_mode():
    from backend.services import engine_manager as em
    assert em._fingerprint("a-x-default", "requests") != em._fingerprint("a-x-default", "browser")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_engine_manager.py -q`
Expected: FAIL（`create_engine_for_request` 当前签名 `(platform, mode, variant)`；`_fingerprint` 需三参）。

- [ ] **Step 3: 改 `engine_manager.py`**

`_fingerprint(source_name, mode)`(25-48)：raw = `f"{source_name}|{mode}"`（browser 仍需 `merged_source_config(source_name)` 的 `chapter_content`/对应能力段取 browser_type/user_data_dir/viewport/headless）。`get_cached_engine`(51-72)/`invalidate_engine`(75-85) 改两参。`create_engine_for_request(source_name, mode)`(123-189)：配置全部取自 `merged_source_config(source_name)[cap]`（cap 由 mode 反查：`capabilities(source_name)` 里 mode 匹配的能力段；browser/requests/api 分支同现状，去掉 variant 自动发现与 `find_variant_options`）。删 `get_cached_engine_for_source`(88-97) 与 explicit engine 段（`_explicit_engines`(110)、`_build_options`(196-216)、`_build_sub_options`(219-238)、`list_explicit_engines`(241-245)、`create_explicit_engine`(248-254)、`get_explicit_engine`(257-261)、`update_explicit_engine`(264-274)、`delete_explicit_engine`(277-286)）及相应 import（`uuid`、`APIOptions`/`RequestsOptions`/`BrowserOptions`）。**`_linux_default_browser_args`(117-121) 与 `create_engine_for_request`(123-189) 保留**（后者仅换签名）。**同 commit 清 `backend/routers/download.py:8` 的顶层 import**：删 `get_cached_engine_for_source`（保留 `get_cached_engine`），并把 `_engines_for`(35-37) 改为 `lambda mode: get_cached_engine(source_name, mode)`（新二参签名）——最小过渡，T7 再全面定型。

- [ ] **Step 4: 运行测试**

Run: `python -c "import backend.main"`
Expected: 无 `ImportError`（已清 `download.py:8` 顶层 import）。

Run: `python -m pytest tests/test_engine_manager.py -q`
Expected: PASS（删 `test_build_options_passes_auto_reconnect` 后剩 2 例）。

- [ ] **Step 5: 提交**

```bash
git add backend/services/engine_manager.py backend/routers/download.py tests/test_engine_manager.py
git commit -F .git/COMMIT_MSG   # 内容：refactor(engine): 引擎缓存按 source_name+mode，删 explicit engine
```

---

## Task 5: `task_manager` 单字段 `_source`

**Files:**
- Modify: `backend/services/task_manager.py`
- Test: `tests/test_task_manager_async.py`

**Interfaces:**
- Consumes: `engine_manager.get_cached_engine(source_name, mode)`（T4）
- Produces:
  - `task_manager._run_download(task: dict, source_name: str)`（async）
  - `task_manager.create_task(novel_id, chapters, title, source_name="", novel_url="") -> {task_id, total}`
  - 任务字段：`_source`（删 `_mode`/`_variant`/`_platform`）
  - `resume_task` 重放 `_run_download(task, task.get("_source", ""))`

- [ ] **Step 1: 写失败测试**（改写 `_stub` 与 `_install_mocks`）

```python
# tests/test_task_manager_async.py（局部改）
async def _stub(task, source_name):
    task["_stub_ran"] = True; ran.set()
monkeypatch.setattr(tm, "_run_download", _stub)
tid = tm.create_task("fanqie_1", [{"id":"c1","url":"http://x","title":"t","order":0}], "test", source_name="92xs-requests-default")
# resume 用例里 task 字典去掉 _mode/_variant/_platform，加 "_source": "92xs-requests-default"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_task_manager_async.py -q`
Expected: FAIL（`_run_download` 当前 4 参；`create_task` 当前 `mode/variant/.../platform`）。

- [ ] **Step 3: 改 `task_manager.py`**

`_run_download(task, source_name)`(26-206)：删 `split_source_name`(32-37)；`engines(mode)`(47-50) 改 `get_cached_engine(source_name, m)`。`create_task`(209-235) 改签名与字段(226→`"_source": source_name`)、`_run_download(task, source_name)` 调度。`resume_task`(299-302) 改 `_source`。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_task_manager_async.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/services/task_manager.py tests/test_task_manager_async.py
git commit -F .git/COMMIT_MSG   # 内容：refactor(task): 下载任务改单 _source 字段
```

---

## Task 6: `SearchResultData.source_name`

**Files:**
- Modify: `backend/schemas/download.py`
- Test: `tests/test_backend_download_routes.py`（与本任务同批小改，主改在 T7）

**Interfaces:**
- Produces: `SearchResultData{title, author, url, description, source_name: str = "", cover_url, extra}`

- [ ] **Step 1: 写失败测试**

```python
def test_search_result_data_uses_source_name():
    from backend.schemas import SearchResultData
    r = SearchResultData(title="t", author="a", url="http://x", source_name="92xs-requests-default")
    assert r.source_name == "92xs-requests-default"
    assert not hasattr(r, "platform")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_backend_download_routes.py -q -k source_name`
Expected: FAIL（当前字段名 `platform`）。

- [ ] **Step 3: 改字段**

`backend/schemas/download.py:10`：`platform: str = ""` → `source_name: str = ""`。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_backend_download_routes.py -q -k source_name`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/schemas/download.py
git commit -F .git/COMMIT_MSG   # 内容：refactor(schema): SearchResultData 改 source_name
```

---

## Task 7: `download` 路由定型（`source` Query + 并发全启用 + `/sources` 新形状）

**Files:**
- Modify: `backend/routers/download.py`
- Test: `tests/test_backend_download_routes.py`（重写）

**Interfaces:**
- Consumes: `shared.config.enabled_source_names()`（T2）、`engine_manager.get_cached_engine(source_name, mode)`（T4）、`task_manager.create_task(..., source_name, novel_url)`（T5）、`SearchResultData.source_name`（T6）
- Produces（见 spec §3.1）：
  - `search_novels(query: str, source: str = "", page: int = 1)` — `source` 空→并发 `enabled_source_names()`；`query` 为 URL 时 `source` 必填
  - `list_all_sources() -> {source_name: {capabilities: {cap: mode}, enabled: bool}}`
  - `resolve_meta_route(body, source)`, `get_remote_novel(novel_id, url, source)`, `resolve_chapter_list_route(novel_id, url, source)`, `download_chapters(novel_id, body, title, source, novel_url)`
  - 删除 `_pick_source`(16)、`list_platforms`(171)、`detect_platform`(194)、`get_cached_engine_for_source`(import 8)、`resolve_source_name`(import 11)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_backend_download_routes.py（重写关键用例）
def _patch_engine_factory(monkeypatch):
    seen = []
    def fake(source_name, mode):
        seen.append((source_name, mode)); return object()
    monkeypatch.setattr(dl, "get_cached_engine", fake)
    return seen


def test_sources_shape_is_flat(monkeypatch):
    monkeypatch.setattr(dl, "list_sources", lambda: ["92xs-requests-default"])
    monkeypatch.setattr(dl, "capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr(dl, "is_source_enabled", lambda n: True)
    out = asyncio.run(dl.list_all_sources())
    assert out == {"92xs-requests-default": {"capabilities": {"search": "requests"}, "enabled": True}}


def test_search_empty_source_uses_enabled(monkeypatch):
    monkeypatch.setattr(dl, "enabled_source_names", lambda: ["a-x-default", "b-y-default"])
    called = []
    async def fake_search(sources, query, engines, **kw):
        called.append(list(sources)); return ()
    monkeypatch.setattr("novelbase.source.resolve", lambda n, c: (fake_search, "requests"))
    asyncio.run(dl.search_novels(query="关键词", source=""))
    assert called == [["a-x-default", "b-y-default"]]


def test_url_search_requires_source(monkeypatch):
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.search_novels(query="https://x/1", source=""))
    assert ei.value.status_code == 400


def test_detect_and_platform_gone():
    assert not hasattr(dl, "detect_platform")
    assert not hasattr(dl, "list_platforms")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_backend_download_routes.py -q`
Expected: FAIL（`list_all_sources` 仍返回 `hosts/show_name`；`search_novels` 首参为 `platform`）。

- [ ] **Step 3: 实现路由**

按 spec §3.1 重写：`_require_source`(28-32) 保留；`_engines_for(source_name)`(35-37) → `lambda mode: get_cached_engine(source_name, mode)`；`search_novels(query, source="", page=1)` 删 `all` 特例、并发 `enabled_source_names()`、URL 分支要求 `source`；`list_all_sources` 返回 `{capabilities, enabled}`（`capabilities(name)` 直出 + `is_source_enabled(name)`）；各路由 Query 参数改 `source`；删 `/platform`、`/detect`、`_pick_source` 与失效 import。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_backend_download_routes.py tests/test_android_server.py -q`
Expected: PASS（`test_android_server.py` 验证 `backend.main` 可 import，不因删路由而崩）。

- [ ] **Step 5: 提交**

```bash
git add backend/routers/download.py tests/test_backend_download_routes.py
git commit -F .git/COMMIT_MSG   # 内容：refactor(download): source Query + 并发全启用书源 + /sources 新形状
```

---

## Task 8: 删除 `/api/v2/engine` + `config` 路由按书源

**Files:**
- Delete: `backend/routers/engine.py`, `backend/schemas/engine.py`
- Modify: `backend/main.py`, `backend/schemas/__init__.py`, `backend/routers/config.py`
- Test: `tests/test_backend_download_routes.py`（追加 config 路由用例）

**Interfaces:**
- Consumes: `shared.config.merged_source_config(source_name)` / `is_source_enabled(source_name)` / `load_site_config` / `save_site_config`（T2）
- Produces（见 spec §3.2）：
  - `config.get_config() -> {max_workers, notify}`（无 `mode`）
  - `config.get_source_config(source_name) -> {source_name, enabled, capabilities, config}`
  - `config.save_source_config(source_name, body) -> {status}`（只写用户层）
  - 删除：`/config/sites/{website}`、`/api/v2/engine*`、`schemas/engine.py`、`main.py:83` 注册

- [ ] **Step 1: 写失败测试**

```python
def test_get_source_config_merged(monkeypatch, tmp_path):
    from backend.routers import config as cfg
    monkeypatch.setattr(cfg.config_service, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg.config_service, "merged_source_config",
                        lambda n: {"search": {"mode": "requests", "timeout": 30}})
    monkeypatch.setattr(cfg.config_service, "is_source_enabled", lambda n: True)
    monkeypatch.setattr(cfg.config_service, "capabilities", lambda n: {"search": "requests"}, raising=False)
    out = asyncio.run(cfg.get_source_config("92xs-requests-default"))
    assert out["enabled"] is True and out["config"]["search"]["timeout"] == 30
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_backend_download_routes.py -q -k source_config`
Expected: FAIL（`get_source_config` 不存在）。

- [ ] **Step 3: 实现 + 删除**

`config.py`：`get_config`(13-23) 删 `mode`；`save_config`(26-45) 删 `mode` 分支；删 `get_site`/`save_site`(87-126)；新增 `get_source_config`/`save_source_config`。删除 `engine.py`、`schemas/engine.py`、`schemas/__init__.py:5-8` 导入、`main.py:16`(engine import) 与 `main.py:83`(include_router)。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_backend_download_routes.py tests/test_android_server.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/routers/config.py backend/main.py backend/schemas/__init__.py
git rm -q backend/routers/engine.py backend/schemas/engine.py
git commit -F .git/COMMIT_MSG   # 内容：refactor(config): 删 /engine，/config/sources 按书源合并读写
```

---

## Task 9: `cli.config` / `cli.core` 按书源重写

**Files:**
- Modify: `cli/config.py`, `cli/core.py`
- Test: `tests/test_cli_variant.py`（重写 `cli.config` 部分）、`tests/test_cli_storage.py`（`build_options(cfg, site_cfg)`(50,60) 改 `build_options(source_name, mode)`）

**Interfaces:**
- Consumes: `shared.config.merged_source_config` / `is_source_enabled` / `enabled_source_names`（T2）
- Produces:
  - `cli.config.build_options(source_name: str, mode: str) -> Options`（或直接复用 `shared.config.build_options`）
  - `cli.core._make_engines(source_name: str)` — `engines(mode)->engine`，缓存挂 `_engines.cache`
  - `cli.core._get_engine(source_name: str, mode: str | None = None)`
  - 删除：`cli.config.mode_variants`(197)、`cli.config.resolve_variant`(203)、`cli.config.build_options(cfg, site_cfg, variant)` 旧签名；`cli.core._make_engines/_get_engine` 的 `split_source_name`(62-63)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_cli_variant.py（重写）
def test_build_options_by_source(monkeypatch):
    import cli.config
    monkeypatch.setattr("shared.config.merged_source_config",
                        lambda n: {"search": {"mode": "requests", "timeout": 42}})
    opts = cli.config.build_options("92xs-requests-default", "requests")
    assert opts.mode == "requests"


def test_variant_helpers_removed():
    import cli.config
    assert not hasattr(cli.config, "resolve_variant")
    assert not hasattr(cli.config, "mode_variants")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_cli_variant.py -q`
Expected: FAIL（`resolve_variant` 仍存在；`build_options` 旧签名）。

- [ ] **Step 3: 改 `cli/config.py` + `cli/core.py`**

`cli/config.py`：删 `mode_variants`(197-200)/`resolve_variant`(203-218)；`build_options(source_name, mode)` 改为薄封装调用 `shared.config.build_options`。`cli/core.py`：`_make_engines(source_name)`(57-72) 删 `split_source_name`，`_get_engine(source_name, mode)`(75-87) 用 `source_name`；`do_update`(216-312) 的 `novel.extra.get("platform")`(266) 改 `novel.source_name`。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_cli_variant.py tests/test_cli_storage.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add cli/config.py cli/core.py tests/test_cli_variant.py
git commit -F .git/COMMIT_MSG   # 内容：refactor(cli): build_options/_make_engines 按 source_name
```

---

## Task 10: `cli.main` 子命令 `--source` + `dev new-source` 重写

**Files:**
- Modify: `cli/main.py`
- Test: `tests/test_cli_dev_new_variant.py`（重写）；`tests/test_cli_variant.py:104-127`（`cli.main._resolve_variant` 用例随删除）

**Interfaces:**
- Consumes: `shared.config.enabled_source_names()`（T2）、`cli.core`（T9）
- Produces:
  - `search`(61-67)：`--source`（可空=全启用并发）、`--page`；删 `--platform/--mode/--variant`
  - `download`(70-77)：`--source`（必）、`--url`、`--group`、`--workers`
  - `update`(80-86)/`info`(110-115)：`--source`（info 必）；删 mode/variant
  - `_scaffold_source(name: str, modes: list[str], write_config: bool = True)` — 生成「一层目录 + 空 `__init__.py` + `source.json` + 4 能力文件 + 默认 `sites/{source_name}.yaml`」，`--no-config` 跳过用户配置
  - 删除：`_resolve_platform`(31)、`_source_name`(44)、`_resolve_variant`(136)、`_scaffold_variant`(426)、`new-variant` 子命令(125-128)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_cli_dev_new_variant.py（重写）
def test_new_source_builds_flat_layout(monkeypatch, tmp_path):
    import cli.main, cli.config
    root = tmp_path / "sources"; root.mkdir()
    cfg_dir = tmp_path / "config"; cfg_dir.mkdir()
    monkeypatch.setattr(cli.main, "_SOURCES_ROOT", root)
    monkeypatch.setattr(cli.config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("shared.config.CONFIG_DIR", cfg_dir)
    cli.main._scaffold_source("demo-requests-default", ["requests"])
    d = root / "demo_requests_default"
    assert (d / "__init__.py").is_file()
    assert (d / "source.json").is_file()
    for fn in ("search", "novel_info", "chapter_list", "chapter_content"):
        assert (d / f"{fn}.py").is_file()
    assert (cfg_dir / "sites" / "demo-requests-default.yaml").is_file()   # 默认建用户配置
```

（目录名 = `source_name` 的下划线形式；`source.json.source_name` 用连字符。）

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_cli_dev_new_variant.py -q`
Expected: FAIL（`_scaffold_source` 旧四层；`new-variant` 仍在）。

- [ ] **Step 3: 实现**

重写 `_parse_args` 的 search/download/update/info/sources 参数表（`--source`）；`cmd_search`(178-198) 默认并发 `enabled_source_names()`；`cmd_download`/`cmd_info` 用 `--source`；`cmd_update`(214-219) 去 mode/variant；重写 `_scaffold_source`（生成 `source.json` 模板 + 一层目录 + 4 能力文件 + 默认用户配置，`--no-config` 开关）；删 `_scaffold_variant` 与 `new-variant` 解析与分发(382-383)。改 `_get_engine`(152-175)：内部 `build_options(cfg, site_cfg, variant)`(157) → `cli.config.build_options(source_name, mode)`，签名 `_get_engine(source_name, mode)`。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_cli_dev_new_variant.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add cli/main.py tests/test_cli_dev_new_variant.py
git commit -F .git/COMMIT_MSG   # 内容：refactor(cli): 子命令 --source，dev new-source 重写，删 new-variant
```

---

## Task 11: `cli.interactive` / `cli.menus` 书源维度

**Files:**
- Modify: `cli/interactive.py`（含 `split_source_name` import 行 25、247 与调用行 28、256）、`cli/menus.py`、`cli/ui.py`（文案：平台→书源）
- Test: `tests/test_interactive_cli.py`

**Interfaces:**
- Consumes: `shared.config.enabled_source_names()`（T2）、`cli.core`（T9）
- Produces:
  - `cli.interactive.do_search(query) -> (url, source_name) | (None, None)` — 关键字分支并发全启用；URL 分支手选书源
  - `cli.interactive.do_download(url, group, format_configs, max_workers)` — 手选书源
  - `cli.interactive._update_one_async(novel, max_workers)` / `cli.core.do_update` — `novel.source_name`
  - 删除：`cli.interactive.do_visit_site`(244-271)、主菜单 7「访问平台」(310,343-344)
  - `cli.menus.do_settings`/`_settings_download`/`_settings_site*` 改书源维度；`_get_delay/_set_delay`(374-386) 改按 `source_name` 能力段

- [ ] **Step 1: 写失败测试**

```python
# tests/test_interactive_cli.py（改写）
def test_do_search_keyword_uses_enabled_not_select(monkeypatch, capsys):
    from cli import interactive as mod
    monkeypatch.setattr(mod, "enabled_source_names", lambda: ["a-x-default"])
    seen = []
    async def fake_search(sources, query, engines, **kw):
        seen.append(list(sources)); return ()
    monkeypatch.setattr(mod, "search", fake_search)
    url, name = mod.do_search("测试")
    assert seen == [["a-x-default"]] and url is None
    assert "未找到结果" in capsys.readouterr().out


def test_visit_site_removed():
    from cli import interactive as mod
    assert not hasattr(mod, "do_visit_site")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_interactive_cli.py -q`
Expected: FAIL（`do_search` 关键字分支仍手选书源；`do_visit_site` 仍在）。

- [ ] **Step 3: 实现**

`do_search`(59-102)：关键字分支改「`enabled_source_names()` → `search(sources, query, engines)` 并发 → 结果汇总标注来源 → 用户选」；URL 分支手选书源保留。`do_download`(108-134) 手选书源。`_update_one_async`(145) 用 `novel.source_name`。删 `do_visit_site` + 菜单项。`cli.menus`：`do_settings`(19-40)/`_settings_*` 改按书源（选书源 → 逐能力段编辑）；`_get_delay/_set_delay`(374-386) 改按 `source_name` 能力段取 delay。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_interactive_cli.py -q`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add cli/interactive.py cli/menus.py cli/ui.py tests/test_interactive_cli.py
git commit -F .git/COMMIT_MSG   # 内容：refactor(cli): 交互式搜索并发全启用 + 书源设置菜单，删访问平台
```

---

## Task 12: 前端 `api/hooks/cache` 对齐契约

**Files:**
- Modify: `frontend/src/api/endpoints.ts`, `frontend/src/hooks/index.ts`, `frontend/src/utils/sessionCache.ts`

**Interfaces:**
- Consumes: spec §3 API 表（T1 冻结）、T7/T8 的端点
- Produces:
  - `endpoints.ts`：`SearchResult.source_name`；`SourceConfig = {source_name, enabled, capabilities: Record<string,string>, config: Record<string, EngineOptions>}`；`searchDownload({query, source?})`；`fetchMeta(url, source?)`；`fetchChapterList(novelId, url, source?)`；`downloadChapters(novelId, chapters, title, source?, novelUrl?)`；`fetchSources() -> Record<string, {capabilities: Record<string,string>, enabled: boolean}>`；`getSourceConfig(source)`/`saveSourceConfig(source, data)`；`SearchHistoryItem{id, source_name, keyword, searched_at}`；`addSearchHistory(source_name, keyword)`
  - `sessionCache.ts`：键 `nd:search:source`（删 `nd:mode`(3)/`nd:variant`(4)/`nd:search:mode`(7)/`nd:search:variant`(8)/`nd:search:platform`(6)）；删 `getSearchPlatform`(35-37) 及 `saveSearch`/`getSearchParams` 的 `platform/mode/variant` 参数
  - `hooks/index.ts`：`useSearch({query, source?})`、`useRemoteChapters(novelId, url, source?)`、`useAddSearchHistory({source_name, keyword})`、`useDownloadMutation({…, source?})`、`useFetchMeta({url, source?})`、`useSources()`（基于 `fetchSources`）、`useSourceConfig(source)`、`useSaveSourceConfig(source)`；**删除 `usePlatforms`(109-115)**（无保留选项）；`useSiteConfig`(91-98)/`useSaveSiteConfig`(230-236) 改名为 `useSourceConfig`/`useSaveSourceConfig`

- [ ] **Step 1: 改类型与函数**（前端无单测，本任务以 tsc 为失败判据）

先改 `endpoints.ts`/`sessionCache.ts`/`hooks/index.ts`，保留旧参数会导致 `tsc` 在 T13 报错。

- [ ] **Step 2: 运行确认失败（类型未收敛）**

Run: `cd frontend; npx tsc --noEmit --project tsconfig.app.json`
Expected: FAIL（调用方——`SearchBar`/`BookshelfPage`/`DetailPage`/`SettingsPage`——仍用旧参数；本任务先让 `endpoints/hooks/cache` 自身一致，剩余错误即 T13/T14 的待办）。

- [ ] **Step 3: 收敛 api/hooks/cache**

按 Interfaces 改三个文件，使 `endpoints.ts`/`hooks/index.ts`/`sessionCache.ts` 内部类型自洽（不再出现 `platform/mode/variant`）。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/endpoints.ts frontend/src/hooks/index.ts frontend/src/utils/sessionCache.ts
git commit -F .git/COMMIT_MSG   # 内容：refactor(frontend): api/hooks/cache 对齐 source_name 契约
```

---

## Task 13: 前端 UI 去 mode/variant

**Files:**
- Modify: `frontend/src/features/bookshelf/SearchBar.tsx`, `BookshelfPage.tsx`, `SearchHistoryPanel.tsx`
- Modify: `frontend/src/features/download/DownloadDialog.tsx`
- Modify: `frontend/src/features/detail/DetailPage.tsx`
- Modify: `frontend/src/features/settings/SettingsPage.tsx`

**Interfaces:**
- Consumes: T12 的 `endpoints`/`hooks`
- Produces（见 spec §6）：`SearchBar` 无 `ModeSelect`/`variant`/域名探测（标题=并发、URL=手选书源）；`DownloadDialog.onStart(source_name)`；`DetailPage` 只带 `source_name`；`SettingsPage` 无「下载模式」，`EngineSection` 按书源逐能力段；`BookshelfPage` 结果 tab 用 `r.source_name`

- [ ] **Step 1: 改 UI 组件**（按 spec §6 删除面）

删 `SearchBar.tsx:27-42,48-49,53-58,65-71,73-90,101-107,132-158,224-247,297-319` 的 mode/variant 与域名探测；`BookshelfPage.tsx:45`（`usePlatforms`→`useSources`）、`52-81` 的 `modeVariants/platformModes/allEngineModes`、`88-89,105-108` 的 `SessionCache.getMode/getVariant/getSearchParams`、`316,321,323` 的 `searchParams.platform`；`DetailPage.tsx:26-33,44-65,271,289,489`、`297-306` 的 `sessionStorage nd:mode/nd:variant`+`globalConfig.mode`、`313-314` 的 `SessionCache.setMode/setVariant`；`SettingsPage.tsx:113-291,353-390`、`140`（`usePlatforms`→`useSources`）；`DownloadDialog.tsx:9-12,25-65,76-117`；`SearchHistoryPanel.tsx:8,44,48-50`。

- [ ] **Step 2: 运行类型检查**

Run: `cd frontend; npx tsc --noEmit --project tsconfig.app.json`
Expected: PASS。

- [ ] **Step 3: 运行构建**

Run: `cd frontend; npm run build`
Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/features/bookshelf/SearchBar.tsx frontend/src/features/bookshelf/BookshelfPage.tsx frontend/src/features/bookshelf/SearchHistoryPanel.tsx frontend/src/features/download/DownloadDialog.tsx frontend/src/features/detail/DetailPage.tsx frontend/src/features/settings/SettingsPage.tsx
git commit -F .git/COMMIT_MSG   # 内容：refactor(frontend): UI 去 mode/variant 选择器，搜索并发全启用
```

---

## Task 14: 前端新增书源管理界面

**Files:**
- Create: `frontend/src/features/sources/SourcesPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `useSources()`、`useSourceConfig`/`useSaveSourceConfig`（T12）、`/config/sources/{name}`（T8）
- Produces：`SourcesPage`（列表 = `source_name` + `capabilities` 摘要 + `enabled` 开关 + 「编辑配置」）；`App.tsx` 侧栏项 + `/sources` 路由

- [ ] **Step 1: 实现页面与路由**

`SourcesPage.tsx`：用 `useSources()` 渲染列表；`enabled` 开关调 `useSaveSourceConfig(source).mutate({enabled})`；「编辑配置」展开 `useSourceConfig(source)` 的逐能力段表单。`App.tsx`：`NavItem`(11) 加 `"sources"`、`DESKTOP_ITEMS`(13-18)/`TO_PATH`(20-23) 加 `sources`、`activeNav`(38-43) 加 `/sources` 分支、`<Routes>`(86-95) 加 `/sources` 路由。

- [ ] **Step 2: 运行类型检查**

Run: `cd frontend; npx tsc --noEmit --project tsconfig.app.json`
Expected: PASS。

- [ ] **Step 3: 运行构建**

Run: `cd frontend; npm run build`
Expected: PASS。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/features/sources/SourcesPage.tsx frontend/src/App.tsx
git commit -F .git/COMMIT_MSG   # 内容：feat(frontend): 新增书源管理界面（列表/enabled/配置）
```

---

## Task 15: docs 同步

**Files:**
- Modify: `docs/project/sources.md`, `docs/project/cli.md`, `docs/project/overview.md`, `docs/project/config.md`, `docs/README.md`
- Modify: `CHANGELOG.md`（仅追加新条目，不改历史行）、`docs/session-prompt.md`
- Check: `docs/source-plugin.md`

**Interfaces:**
- Consumes: 全部前置任务

- [ ] **Step 1: 重写 `docs/project/sources.md`**

按 recon §6：删「平台状态表」`SHOW_NAME/canonical_book_url/mode`、「四层目录结构」、`capabilities() 返回 {mode:{variant}}`；改为 4-API（含 `get_manifest`）、一层目录 + `source.json`、`capabilities() -> {cap: mode}`、`Novel.id = sha256(url)[:32]`。

- [ ] **Step 2: 改 `cli.md` / `overview.md` / `config.md` / `README.md`**

`cli.md`：命令表去 `--platform/--mode/--variant`，改 `--source`；删「模式与 variant」节。
`overview.md`：架构速览的 `sources/` 改一层；`source.py ← 公共 API` 补 `get_manifest`；CI 状态改「全部通过（删除 `mode/variant` 废弃用例后总数约 350–365，0 failed）」。
`config.md`：`sites/*.yaml` 改逐能力段 + 顶层 `enabled`。
`README.md`:18-19 导航表条目措辞更新。

- [ ] **Step 3: 检查 `docs/source-plugin.md`**（4685 B，可能与旧 `sources.md` 同尺寸；若含四层/`registry.resolve(name, mode, function)` 旧内容则同步）

- [ ] **Step 3b: 追加 `CHANGELOG.md` 条目 + 更新 `docs/session-prompt.md`**

`CHANGELOG.md`：**不改历史行**（如 101 行的 `_platform_from_url()`、103 行的 `POST /api/v2/download/detect`），在**文件顶部追加新版本条目**，说明本次删除 `/download/detect`、`/api/v2/engine`、全局 `mode`、`do_visit_site`，`sites/*.yaml` 与 `search_history` 不迁移。
`docs/session-prompt.md`：更新第 56 行「已知中间态」（`/download/detect`/`enabled` 无消费者/前端 URL 识别不可用等已被本次改造消除）。

- [ ] **Step 4: 全量验收**

Run: `python -m pytest tests/ -q`
Expected: **0 failed**（全绿）；`passed` 约 **350–365**、`skipped = 1`（删除 `mode/variant` 废弃用例后的合理区间，不是写死的单一数字）。

Run: `cd frontend; npx tsc --noEmit --project tsconfig.app.json`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add docs/project/sources.md docs/project/cli.md docs/project/overview.md docs/project/config.md docs/README.md CHANGELOG.md docs/session-prompt.md
git commit -F .git/COMMIT_MSG   # 内容：docs: 同步书源扁平化后的 sources/cli/overview/config
```

---

## 自审记录

### ① spec 覆盖检查表（每个 spec 章节 → 任务映射）

| spec 章节 | 任务 |
|---|---|
| §2 已拍板决策（D1 enabled 覆盖 / D2 三删 / D3 删 mode / D4 出厂默认） | T2(D1,D3,D4)、T7+T8+T11(D2) |
| §3.1 `/download/*` 契约 | T6(字段)、T7(路由/形状) |
| §3.2 `/config/*` 契约 | T8 |
| §3.3 `/history/search` 契约 | T3 |
| §3.4 Pydantic schema | T6、T8（删 engine schema） |
| §4.1 三层合并 | T2 |
| §4.2 enabled 覆盖读取 | T2 |
| §4.3 启用书源单一入口 `enabled_source_names` | T2（产出）、T7+T10+T11（消费） |
| §5.1 core 过渡符号删除 | T2 |
| §5.2 backend 删除 | T4/T5/T7/T8 |
| §5.3 CLI 删除 | T9/T10/T11 |
| §5.4 shared/user_data 删除 | T2/T3 |
| §5.5 前端删除 | T12/T13 |
| §5.6 全局 mode | T2/T8/T13 |
| §6 前端目标形态 + 书源管理界面 | T13/T14 |
| §7 数据与兼容（sites 不迁移 / search_history drop / 模板库 / 旧书引导） | T2(sites 模板)、T3(db+模板库)、T9/T11(旧书引导) |
| §8 验收口径（`0 failed` / passed 区间） | 各任务「各任务删除用例与预期 passed」表 + T15 Step 4 |
| §9 硬约束（url 不变） | Global Constraints #1；无任务改书源实现 |
| §10 未决事项 | 不写代码，spec 已列 |

### ② 占位符扫描

本计划全文**无** `TBD`/`TODO`/`待定`/`视情况`/`XXX`；`load_platform_configs/raw`、`usePlatforms/downloadPlatforms` 的处置均已定为「删除」。spec §10 现余 **2 条**「未决事项」（`bookmarks.platform` 列、URL 自动匹配），均给出**推荐**，非含糊占位。

### ③ 类型/命名一致性自查

- `source_name`（连字符）与目录名（下划线）解耦，全链一致；`_scaffold_source` 生成目录名 = `source_name.replace("-", "_")`。
- `source` 作为 HTTP Query 参数名，其值即 `source_name`（前端传 `source`，后端直接当 `source_name`）——T7/T12 两侧一致。
- `engines(mode) -> engine` 解析器签名在 `downloader`、`cli.core._make_engines`、`task_manager` 三处一致；`get_cached_engine(source_name, mode)` 二参签名在 T4 定义、T5/T7 消费，一致。
- `enabled_source_names()` 是启用集唯一入口（Global Constraints 与 spec §4.3 双重约束，禁止别处重复实现）。
- `merged_source_config(source_name) -> {cap: 完整字段}` 在 T2 定义、T4/T8/T9 消费，形状一致。
- `SearchResultData.source_name` / 前端 `SearchResult.source_name` / `SearchHistoryItem.source_name` 字段名三侧统一为 `source_name`。

### ④ 已知顺序坑与解决方式

1. **删 `schemas/engine.py` 会让 `backend/main.py` 的 engine 路由 import 崩** → 将「删 `schemas/engine.py`」与「删 `engine.py` 路由 + `main.py` 注册」**同一任务（T8）同一 commit**；T6 只改 `SearchResultData` 字段，不碰 engine schema。避免任何中间态 import 错。
2. **T7 的测试依赖 T2/T4/T5/T6 的产物**（`enabled_source_names`、`get_cached_engine(source_name, mode)`、`create_task(..., source_name)`、`SearchResultData.source_name`）→ T7 严格排在 T2>T4>T5>T6 之后。
3. **T5 依赖 T4**（`task_manager` 调 `get_cached_engine` 新签名）→ T5 排在 T4 后。
4. **T12（前端 api/hooks）依赖 T7/T8 的端点定稿**→ T12 排在 backend 批次后；T13/T14 又依赖 T12。因此前端 tsc 在 T12 结束前必然有错（调用方未改），T12 的判据是「api/hooks/cache 三文件内部自洽」，全量 tsc 绿在 T13。
5. **T3 重建模板库** 需在 `_SCHEMA_SQL` 改完之后执行（T3 Step 5 紧跟 Step 3），否则 `test_user_db_template.py` 红。
6. **T2 全量回归会中间态红**（engine_manager / task_manager / download 路由 / cli_*）——这是有意的过渡窗口，T2 只保证配置层相关子集绿，收口在 T7/T8/T9/T10/T11。
7. **`build_options` 双份实现漂移**：`shared/config.py` 与 `cli/config.py` 都有 `build_options`（recon §4.2）→ T9 让 `cli/config.build_options` 薄封装 `shared.config.build_options`，消除重复。
8. **T9 改 `cli.config.build_options` 签名 → `cli/main.py:157` 调用点崩**（`_get_engine`）→ `_get_engine`(152-175) 的改造归 T10（同文件）；T9 只保证 `cli.config`/`cli.core` 自洽与 `test_cli_variant`/`test_cli_storage` 绿。
9. **`test_cli_variant.py` 被 T9 与 T10 共同改写**（T9=cli.config 用例、T10=`cli.main._resolve_variant` 用例 104-127）→ 两任务都显式列该文件，避免遗漏/重复。
10. **`template/config/sites` 从 4 个变 10 个** → 影响 `init_config.py:83` 的 `template.rglob("*.yaml")` 计数（Global Constraints #9）；T2 改模板后需留意 `init_config` 相关测试与 `check_config()` 行为。
11. **模板库 `user_data.db` 的 DROP 重建**（T3 Step 5）必须用 `DROP TABLE search_history` + `executescript(_SCHEMA_SQL)`，不能用「重跑 `_SCHEMA_SQL`」——`CREATE TABLE IF NOT EXISTS` 对已存在表无效。
12. **T2 删 `shared.config` 旧函数 → 顶层 import 者 import 崩**：`backend/services/engine_manager.py:16`、`cli/config.py:17` 必须在 **T2 同 commit** 清理（Global Constraints #10 第二条）；否则 `backend.main`/`cli` import 崩、测试收集失败。T2 的 Step 6 用 `pytest --co` 专门验证「收集不报错」。
13. **「顶层 import 清理对照表」**（每个删符号的任务必须在其 commit 内清顶层 `from ... import <被删名>` 者；函数内延迟 import 不受影响）：

    | 任务 | 被删符号 | 顶层 from-import 者 | 处理 |
    |---|---|---|---|
    | T2 | `resolve_source_name`（novelbase.source） | `backend/routers/download.py:11` | 同 commit 清（`_pick_source` 退化直通） |
    | T2 | `get_mode_variant_config`/`mode_variants`/`find_variant_options` | `backend/services/engine_manager.py:16`、`cli/config.py:17` | 同 commit 清 |
    | T3 | `_migrate_search_history` | `tests/test_user_db_template.py:62` | 同 commit 改（测试） |
    | T4 | `get_cached_engine_for_source` | `backend/routers/download.py:8` | 同 commit 清（`_engines_for` 改用新签名） |
    | T8 | `CreateEngineRequest`/`UpdateEngineRequest`（schemas.engine） | `backend/routers/engine.py`（顶层）、`backend/schemas/__init__.py:5-8` | 同 commit 删 |
    | — | `split_source_name`（无顶层 import；`cli/main.py:46`、`cli/core.py:62`、`cli/interactive.py:25,247` 均函数内延迟 import） | 无 | — |

    其余删符号（`_pick_source`/`list_platforms`/`detect_platform`/`_scaffold_variant`/`_resolve_variant`/`do_visit_site`/cli.config 旧函数）均无外部顶层 from-import，不需额外处理。
