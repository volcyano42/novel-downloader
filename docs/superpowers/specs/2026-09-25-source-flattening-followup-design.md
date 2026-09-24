# 书源扁平化 — 遗留改造契约定稿（backend / CLI / 前端 / 配置）

- 日期：2026-09-25
- 分支：`dev`
- 状态：**契约定稿**（本文件是 backend / CLI / 前端的实现依据；先定稿、再两侧实现）
- 前置：`docs/superpowers/specs/2026-09-24-book-source-flattening-design.md`（core 设计）、
  `.superpowers/sdd/2026-09-25-followup/recon.md`（逐文件现状盘点）
- 基线：`dev` 已扁平化 core（`python -m pytest tests/ -q` = **379 passed, 1 skipped**）。`platform` 已从 core 移除，但 backend / CLI / 前端 / 配置只做了「最小适配」，功能级改造未做。

---

## 1. 背景与范围

core 层已完成扁平化：书源 = `novelbase/sources/{dir}/`（一层目录 + `source.json`），`novelbase/source.py` 只暴露 4 个 API：

```python
list_sources() -> list[str]                       # source.py:79
get_manifest(source_name) -> dict                 # source.py:102
capabilities(source_name) -> dict[str, str]       # source.py:118   {capability: mode}
resolve(source_name, capability) -> (fn, mode)    # source.py:140
resolve_book_url(raw) -> str                      # source.py:190
```

`downloader` 新签名（`novelbase/core/downloader.py`）：`search(sources, query, engines, **kwargs)`（31）、`resolve_meta(url, source_name, engines)`（54）、`resolve_chapter_list`（68）、`resolve_chapter`（76）；`engines` 是 `engines(mode) -> engine` 解析器。

**本次要收口的 6 项遗留**（设计文档「后端改造 / CLI 改造 / 前端改造 / 配置合并 / 数据与兼容」章节的目标形态）：

| # | 遗留 | 关键症状 |
|---|---|---|
| L1 | backend 改造 | `/download/sources` 返回 `capabilities={cap→mode}`，前端却按 `{mode:{variant:[]}}` 解析 → 前端模式/变体列表**全空**（`recon.md:14`）。`_pick_source`/`get_cached_engine_for_source` 仍是 `{platform}-{mode}-{variant}` 过渡 hack；`/search?platform=all` 硬编码 fanqie 引擎（`download.py:66`，bug）。 |
| L2 | CLI 改造 | `cli/main.py`、`cli/interactive.py`、`cli/config.py`、`cli/core.py`、`cli/menus.py` 全围绕 `--platform/--mode/--variant`；`dev new-source` 生成旧四层目录、`new-variant` 是旧脚手架。 |
| L3 | 前端改造 | 两级模式/变体选择器（`SearchBar.tsx`、`DownloadDialog.tsx`）、`SettingsPage` 的「下载模式 + 平台引擎设置」、`sessionCache` 的 `nd:mode/nd:variant` 全基于已删概念。**无书源管理界面**。 |
| L4 | 配置合并 | `shared/config.py` / `cli/config.py` 按 platform+mode+variant 读配置；三层合并（系统默认 → `source.json.default_config` → 用户层）未落地；`enabled` **全库无消费者**（`recon.md:162`）。 |
| L5 | 数据与兼容 | `search_history` 仍是 `(platform, keyword, mode, variant)` 旧键（`shared/user_data.py:44-51,84-119`）；`template/config/sites/*.yaml` 是旧三段 + variant 容器；`Novel.source_name=""` 旧书无引导。 |
| L6 | docs 同步 | `docs/project/sources.md` / `cli.md` / `overview.md` / `config.md` 几乎整篇过时（四层结构、platform 状态表、`--platform`/`--mode`）。 |

**非目标**（本次不做）：不改书源实现（`novelbase/sources/*/`）、不改导出器、不改 Android（`android/`）、不改 `novelbase/exporters/*`、不迁移旧 `sites/*.yaml`、不做旧结构兼容层。

---

## 2. 已拍板决策（不可更改）

| 编号 | 决策 | 说明 |
|---|---|---|
| D1 | **`enabled` 用户层覆盖位置** = `app_data/config/sites/{source_name}.yaml` **顶层** `enabled:` 字段 | 读取时覆盖 `source.json` 的出厂值。 |
| D2 | **三个失去基础的能力全部删除**：`/download/detect`（URL→书源推断）、`/api/v2/engine`（explicit engine API，含 `CreateEngineRequest.platform`）、CLI `do_visit_site`（「访问平台」） | 均因 `hosts`/`platform` 消失而失去基础。 |
| D3 | **删除全局 `mode`**：`config.yaml` 的 `mode` 字段 + `GLOBAL_DEFAULTS["mode"]` + 前端 SettingsPage 的「下载模式」设置项 | `mode` 完全由书源声明。 |
| D4 | 出厂 `enabled` 默认：**api 类 `false`，requests/browser 类 `true`** | 见 design:284 建议。当前实测 `fanqie_api_rain/source.json` 为 `false`，其余 requests/browser 为 `true`，符合。 |

---

## 3. API 契约表（定稿）

所有端点前缀 `/api/v2`。响应经 `backend/main.py:38` 的 `V2ResponseMiddleware` 包成 `{ok, message, data}`（前端 `client.ts` 解包 `data`）。下表「返回形状」指 `data` 内层。

### 3.1 `/api/v2/download`（`backend/routers/download.py`）

| Method | 路径 | 参数 | 返回 | 说明 |
|---|---|---|---|---|
| GET | `/download/sources` | 无 | `{source_name: {capabilities: {capability: mode}, enabled: bool}}` | **契约重定**。`capabilities` 是扁平 `{cap→mode}`（`capabilities(name)` 直出），`enabled` = 三层读取结果（见 §4.2）。列**全部**书源（含未启用）。**不含**用户层配置明细（配置走 `/config/sources/{name}`）。 |
| GET | `/download/search` | Query `query`（必）、`source`（可选，默认 `""`）、`page`（int，默认 1） | `SearchResultData[]`（字段见 §3.4） | **语义**：`source` 非空 → 单书源；`source` 空 → **并发全部启用书源**（`enabled_source_names()`，见 §4.3），结果合并、每条带 `source_name`。`query` 为 `http(s)://` 时**必须**有 `source`（core 无 URL→书源推断），否则 400。删除 `platform=="all"` 特例。 |
| POST | `/download/novel` | body `{url}`，Query `source`（必） | meta 对象（同现状：`title/url/id/serial/author/description/tags/count/cover/extra`） | `source` 即 `source_name`；缺 → 400（`_require_source` 语义保留）。 |
| GET | `/download/novel/{novel_id}` | Query `url`、`source`（必） | 同上 | |
| GET | `/download/novel/{novel_id}/chapters` | Query `url`、`source`（必） | `ChapterBrief[]` | |
| POST | `/download/novel/{novel_id}/chapter` | body `DownloadChapterRequest[]`，Query `title`、`source`（必）、`novel_url` | `{task_id, total}` | 委托 `task_manager.create_task(novel_id, chapters, title, source_name, novel_url)`。 |
| GET | `/download/tasks` | 无 | `TaskInfo[]` | 不变。 |
| POST | `/download/task/{id}/pause` `.../resume` | 无 | `{status}` | 不变。 |
| DELETE | `/download/task/{id}` | 无 | `{status}` | 不变。 |

**删除**：`GET /download/platform`（`download.py:171-174`，语义等同 `/download/sources` 的子集）、`POST /download/detect`（`download.py:194-206`）。删除模块内 `_pick_source`(16)、`get_cached_engine_for_source` 导入(8)、`resolve_source_name` 导入(11)。其中 `download.py:8`/`:11` 的**顶层 import** 分别在 **T4/T2 同 commit 提前清理**（见 §5.2），T7 再整体定型。

### 3.2 `/api/v2/config`（`backend/routers/config.py`）

| Method | 路径 | 参数 | 返回 | 说明 |
|---|---|---|---|---|
| GET | `/config` | 无 | `{max_workers, notify}` | **删除 `mode` 字段**（`config.py:18,30-32`）。 |
| PUT | `/config` | body `{max_workers?, notify?}` | `{status}` | 不再接受 `mode`。 |
| GET | `/config/sources/{source_name}` | 无 | `{source_name, enabled, capabilities: {cap: mode}, config: {cap: {…完整合并字段…}}}` | `config[cap]` = 三层合并（§4.1）后的该能力段完整字段（含 `mode`）。`enabled` = 三层读取结果（§4.2）。 |
| PUT | `/config/sources/{source_name}` | body `{enabled?: bool, config?: {cap: {…部分字段…}}}` | `{status}` | **只写用户层** `sites/{source_name}.yaml`：顶层写 `enabled`，`config` 逐能力段 `deep_merge` 进 `sites/{name}.yaml[cap]`。 |
| GET/PUT | `/config/groups`、`/config/favorites*`、`/config/formats/{format}` | — | — | 不变。 |

**删除**：旧 `GET/PUT /config/sites/{website}`（`config.py:87-126`）。命名统一为 `sources`（与书源概念一致）。

### 3.3 `/api/v2/history`（`backend/routers/history.py`）

| Method | 路径 | 参数 | 返回 |
|---|---|---|---|
| GET | `/history/search` | `limit`（默认 50） | `{history: [{date_label, items: [{id, source_name, keyword, searched_at}]}]}` |
| POST | `/history/search` | body `{source_name: str, keyword: str}` | `{status}` |
| DELETE | `/history/search/{history_id}` | — | `{status}` |

**改动**：`SearchHistoryAddRequest{platform,keyword,mode,variant}`（`history.py:11-15`）→ `{source_name, keyword}`；输出字段 `platform/mode/variant`（46-53）→ `source_name`；`_add(body.source_name, keyword)`（64）。唯一键 `(source_name, keyword)`。

### 3.4 Pydantic schema 字段（`backend/schemas/`）

- `SearchResultData`（`schemas/download.py:5-12`）：字段 `platform: str = ""`（10）→ `source_name: str = ""`。其余不变。
- **删除整个 `backend/schemas/engine.py`**（`APIOptionsData/RequestsOptionsData/BrowserOptionsData/CreateEngineRequest/UpdateEngineRequest`）与 `schemas/__init__.py` 的对应导入（5-8），随 `/api/v2/engine` 删除。
- `backend/routers/engine.py`（全文件）与 `backend/main.py:83` 的 `app.include_router(engine.router)` 删除。

### 3.5 删除的三个端点（复述，见 §2 D2）

- `POST /api/v2/download/detect`（`download.py:194-206`）
- `/api/v2/engine*`（`backend/routers/engine.py` 全部 6 条，`main.py:83`）
- CLI `do_visit_site`（`cli/interactive.py:244-271`，非 HTTP）

**核实结论（重要）**：`grep -n "detect\|/engine" frontend/src` **无任何调用点**——前端 URL 平台探测是**本地硬编码域名映射**（`SearchBar.tsx:135-142` + `DetailPage.tsx:26-33`），不调 `/detect`；`EngineInfo` 类型（`endpoints.ts:88`）无使用。故 D2 的三处删除对前端**零调用点波及**，前端只需删掉那两处本地域名映射（改为手选书源，见 §6）。

---

## 4. 配置三层合并（定稿）

### 4.1 三层合并定义

对某书源 `source_name` 的某能力 `cap`（`mode = capabilities(source_name)[cap]`，取自 `source.json`）：

```
merged[cap] = deep_merge(
    deep_merge(ENGINE_DEFAULTS[mode], source.json.default_config[cap]),   # 第 1、2 层
    sites/{source_name}.yaml[cap] or {}                                    # 第 3 层
)
```

- 第 1 层「系统默认」= `shared/config.py` 的 `ENGINE_DEFAULTS[mode]`（`config.py:61-65`；`api` 默认为 `{}`）。`GLOBAL_DEFAULTS` 保留作基底的顶层默认，但**删除其 `mode` 键**（D3）。
- 第 2 层「书源出厂默认」= `get_manifest(source_name)["default_config"][cap]`。注意 `load_manifest()` 已把顶层 `common` 并入每个能力段（`manifest.py:88-101`），下游只见完整字段。
- 第 3 层「用户层」= `load_site_config(source_name)[cap]`（`sites/{source_name}.yaml` 的逐能力段）。
- 用户层**不写 `mode`**；合并时 `mode` 恒取书源声明（`capabilities`），即使用户层段里出现 `mode` 也忽略（实现上：合并前从用户层段剔除 `mode` 键）。
- 下游（引擎构建 / CLI `build_options` / 前端配置编辑）只消费合并后的完整字段。

### 4.2 `enabled` 覆盖读取规则（D1）

```
enabled(source_name) =
    sites/{source_name}.yaml 顶层 "enabled"    若存在且为 bool
    else  get_manifest(source_name)["enabled"]  # source.json 出厂值
```

- 用户层槽位：`sites/{source_name}.yaml` **顶层** `enabled:`（与逐能力段 `search:/novel_info:/…` 平级）。
- 出厂值：`source.json.enabled`（D4：api 类 `false`，requests/browser 类 `true`）。

### 4.3 「启用书源」集合的单一入口

**唯一入口**：`shared/config.py::enabled_source_names() -> list[str]`

```python
def enabled_source_names() -> list[str]:
    """返回用户层 enabled 覆盖后仍启用的书源 source_name（排序）。"""
```

- 实现：对 `list_sources()` 逐个求 `enabled(name)`（§4.2），过滤为 `True`。
- 消费者：backend `/download/search`（空 `source` → 并发全部启用书源）、CLI `search` 默认并发、任何需要「启用集」的地方。**禁止**在别处重复实现该过滤。
- 前端不做后端过滤：`/download/sources` 返回全部书源 + `enabled` 标志，前端自行过滤展示。

---

## 5. 删除清单（定稿）

### 5.1 core 过渡符号（design 的 4-API 不含）

| 符号 | 位置 | 处理 |
|---|---|---|
| `split_source_name` | `novelbase/source.py:198` | 删除 |
| `resolve_source_name` | `novelbase/source.py:214` | 删除 |
| `__all__` 两项 | `novelbase/source.py:30` | 同步删除 |

### 5.2 backend

| 符号 | 位置 | 处理 |
|---|---|---|
| `_pick_source` | `backend/routers/download.py:16-25` | 删除（`source` Query 直接即 `source_name`） |
| `get_cached_engine_for_source` | `backend/services/engine_manager.py:88-97` | 删除（改为按书源缓存，见下） |
| `_fingerprint(platform, mode, variant)` | `engine_manager.py:25-48` | 改 `_fingerprint(source_name, mode)` |
| `create_engine_for_request(platform, mode, variant)` | `engine_manager.py:123-189` | 改 `create_engine_for_request(source_name, mode)`；删 api-variant 自动发现(136-143)、`find_variant_options`(146) |
| `get_cached_engine(platform, mode, variant)` | `engine_manager.py:51-72` | 改 `get_cached_engine(source_name, mode)` |
| `invalidate_engine(platform, mode, variant)` | `engine_manager.py:75-85` | 改 `invalidate_engine(source_name, mode)` |
| explicit engine 段：`_explicit_engines`(110)、`_build_options`(196-216)、`_build_sub_options`(219-238)、`list_explicit_engines`(241-245)、`create_explicit_engine`(248-254)、`get_explicit_engine`(257-261)、`update_explicit_engine`(264-274)、`delete_explicit_engine`(277-286) | `engine_manager.py` | 删除（仅被 `/api/v2/engine` 消费）。**`_linux_default_browser_args`(117-121) 是保留代码、`create_engine_for_request`(123-189) 按书源改造后保留——二者都不在删除范围内** |
| `get_cached_engine_for_source` 导入（**顶层**） | `backend/routers/download.py:8` | **T4 同 commit 清理**（改用 `get_cached_engine(source_name, mode)`；否则 import 崩） |
| `resolve_source_name` 导入（**顶层**） | `backend/routers/download.py:11` | **T2 同 commit 清理**（`_pick_source` 退化为直通 `source`；否则 import 崩；T7 全面定型） |
| `backend/routers/engine.py`（全文件）+ `main.py:83` 注册 | — | 删除 |
| `detect_platform` | `download.py:194-206` | 删除 |
| `list_platforms`（`/download/platform`） | `download.py:171-174` | 删除 |
| `_engines_for` | `download.py:35-37` | 改：`lambda mode: get_cached_engine(source_name, mode)` |
| `_run_download(task, mode, variant, platform)` | `backend/services/task_manager.py:26` | 改 `_run_download(task, source_name)` |
| `split_source_name` 调用 | `task_manager.py:32-37` | 删除 |
| 任务字段 `_mode/_variant/_platform` | `task_manager.py:226` | 改单 `_source` |
| `create_task(..., mode, variant, novel_url, platform)` | `task_manager.py:209-235` | 改 `create_task(novel_id, chapters, title, source_name, novel_url)` |
| `resume_task` 重放 `_mode/_variant/_platform` | `task_manager.py:299-302` | 改 `_source` |
| `schemas/engine.py`（全文件）+ `schemas/__init__.py:5-8` | — | 删除 |
| `SearchResultData.platform` | `schemas/download.py:10` | 改 `source_name` |
| `engine_manager.py:16` 顶层 `from shared.config import ... find_variant_options, get_mode_variant_config` | `backend/services/engine_manager.py` | **T2 同 commit 清理**（否则删 shared.config 函数后 `backend.main` import 崩） |
| `GLOBAL_DEFAULTS["mode"]` | `shared/config.py:68` | 删除（D3） |

### 5.3 CLI

| 符号 | 位置 | 处理 |
|---|---|---|
| `_resolve_platform` | `cli/main.py:31-41` | 删除 |
| `_source_name` | `cli/main.py:44-51` | 删除 |
| `_resolve_variant` | `cli/main.py:136-149` | 删除 |
| `_scaffold_variant` + `dev new-variant` 子命令 | `cli/main.py:426-488, 125-128` | 删除 |
| `_scaffold_source` | `cli/main.py:400-423` | **重写**为「一层目录 + 空 `__init__.py` + `source.json` + 4 能力文件 + 默认用户配置」 |
| `split_source_name` import 与调用 | `cli/main.py:46`、`cli/core.py:62`、`cli/interactive.py:25,28,247,256`（25/247 为 import 行、28/256 为调用行） | 删除 |
| `cli/config.py:17` 顶层 `from shared.config import get_mode_variant_config` | `cli/config.py` | **T2 同 commit 清理**（否则 `cli` import 崩）；`cli/config.py:199` 体内 `from shared.config import mode_variants` 随 `mode_variants` 函数删除 |
| `mode_variants` | `cli/config.py:197-200` | 删除 |
| `resolve_variant` | `cli/config.py:203-218` | 删除 |
| `build_options(cfg, site_cfg, variant)` | `cli/config.py:221-305` | 改 `build_options(source_name, mode)`（走 `shared.config` 三层合并） |
| explicit engine 相关 `_build_options/_build_sub_options` | `engine_manager.py`（同上） | 删除 |
| `do_visit_site` | `cli/interactive.py:244-271` | 删除（D2） |
| 菜单 7「访问平台」 | `cli/interactive.py:310,343-344` | 删除 |
| `novel.extra.get("platform")` 兜底 | `cli/interactive.py:145`、`cli/core.py:266` | 改 `novel.source_name`（空则跳过并提示） |
| `_get_engine(platform, mode, variant)` 调旧 `build_options(cfg, site_cfg, variant)`（157 行） | `cli/main.py:152-175` | 改按书源：`_get_engine(source_name, mode)`，内部调 `cli.config.build_options(source_name, mode)`（与 `cli/core._get_engine` 统一） |
| `mode_variants`/`find_variant_options` 调用 | `cli/config.py:199`、`shared/config.py` | 随定义删除 |

### 5.4 shared / user_data

| 符号 | 位置 | 处理 |
|---|---|---|
| `mode_variants` | `shared/config.py:194-199` | 删除 |
| `find_variant_options` | `shared/config.py:201-211` | 删除 |
| `get_mode_variant_config` | `shared/config.py:167-185` | 删除（variant 体系取消） |
| `load_mode_config` | `shared/config.py:188-191` | 删除 |
| `load_site_config(platform)` / `save_site_config` | `shared/config.py:132,139` | 保留签名，语义=按 `source_name`（仅文档措辞） |
| `load_platform_configs` | `shared/config.py:144-162` | **删除**（全库无调用点，grep 仅命中定义；其实现依赖已删的 `get_mode_variant_config`/`mode_variants`） |
| `load_platform_raw` | `shared/config.py:164-165` | **删除**（全库无调用点） |
| `build_options(cfg, site_cfg)` | `shared/config.py:243-308` | **重写为新签名 `build_options(source_name, mode)`，供 cli 复用**（T2 已实施：从三层合并配置组 Options；旧 `(cfg, site_cfg)` 死代码实现作废。原「删除」表述更正——spec §5.4 T1 补记与 plan/brief 的「重写供 cli 复用」冲突，以 plan/brief 为准） |
| `_migrate_search_history` 旧迁移 + `platform='fanqie'` 硬编码 | `shared/user_data.py:84-119` | 删除；`search_history` drop 重建新 schema（§7） |
| `add_search_history(platform, keyword, mode, variant)` | `shared/user_data.py:246-255` | 改 `add_search_history(source_name, keyword)` |
| `search_history` 表定义 | `shared/user_data.py:44-51` | 改：`source_name TEXT NOT NULL` + `keyword TEXT NOT NULL`，唯一键 `(source_name, keyword)` |

### 5.5 前端（见 §6）

| 符号 | 位置 | 处理 |
|---|---|---|
| `SessionCache` 的 `nd:mode`(3)/`nd:variant`(4)/`nd:search:mode`(7)/`nd:search:variant`(8)/`nd:search:platform`(6) | `sessionCache.ts` | 全改 `nd:search:source`；删 `getMode`/`setMode`/`getVariant`/`setVariant`/`getSearchMode`/`getSearchVariant`/`getSearchPlatform`(35-37)；`saveSearch`/`getSearchParams` 去掉 `platform/mode/variant` 改 `source` |
| `SearchBar` 的 `ModeSelect` / `mode` / `variant` / `modeVariants` / `platformModes` | `SearchBar.tsx:27-42,48-49,53-58,65-71,73-90,101-107,132-158,224-247,297-319` | 整块删除 |
| `SearchBar` URL 平台探测硬编码域名 | `SearchBar.tsx:135-142` | 删除，改手选书源下拉 |
| `DetailPage` 的 `platformFromUrl`(26-33,55,271,289)、`searchMode/searchVariant`(44,46-47,65)、`platModes/platVariantsByMode`(56-64,489)、`sessionStorage nd:mode/nd:variant`(297-306)、`globalConfig.mode`(297,302,305,308)、`SessionCache.setMode/setVariant`(313-314) | `DetailPage.tsx` | 删 mode/variant 的直读与写入，改只带 `source_name`（含 271/289 的 `platform:` 传参与 489 的 `DownloadDialog` props） |
| `DownloadDialog` 的 `availableModes/variantsByMode/initialMode/initialVariant` | `DownloadDialog.tsx:9-12,25-65,76-117` | 删除 mode/variant 询问 |
| `SettingsPage` 的 `EngineSection`/`ApiVariantsSection`/`modeOptions`/「下载模式」 | `SettingsPage.tsx:139-291,353-390` | 改为按书源编辑该书配置 |
| `BookshelfPage` 的 `modeVariants/platformModes/allEngineModes`(52-81)、`SessionCache.getMode/getVariant/getSearchParams`(88-89,105-108)、`searchParams.platform`(316,321,323) | `BookshelfPage.tsx` | 删 mode/variant 与 `platform` 分组，改按 `r.source_name` |
| `SearchHistoryPanel` 的 `platform/mode/variant` 徽标 | `SearchHistoryPanel.tsx:8,44,48-50` | 改 `source_name` |
| `usePlatforms`(109-115) + `downloadPlatforms`(222-224) | `hooks/index.ts`、`endpoints.ts` | **删除**（`/download/platform` 端点已删）；消费方 `BookshelfPage.tsx:45`、`SettingsPage.tsx:140` 改用 `useSources()`（`/download/sources`） |
| `useSiteConfig`(91-98) / `useSaveSiteConfig`(230-236) / `getSiteConfig`(24) / `saveSiteConfig`(34) | `hooks/index.ts`、`endpoints.ts` | 改名为 `useSourceConfig`/`useSaveSourceConfig`/`getSourceConfig`/`saveSourceConfig`，指向 `/config/sources/{name}` |
| `GlobalConfig.mode` | `endpoints.ts:72` | 删除（D3） |

### 5.6 全局 `mode`（D3）

`template/config/config.yaml` 的 `mode: api`（`config.yaml:5`）、`shared/config.py:68` 的 `GLOBAL_DEFAULTS["mode"]`、`backend/routers/config.py:18,30-32`、前端 `GlobalConfig.mode`（`endpoints.ts:72`）与「下载模式」UI（`SettingsPage.tsx:377-390`）全部删除。

---

## 6. 前端目标形态（定稿）

去 mode/variant 选择器后各页面如何表达：

- **标题搜索**（`SearchBar.tsx` 标题 tab）：不再有平台/模式/变体选择器。搜索请求 `GET /download/search?query=...`（不带 `source`）→ 后端**并发全部启用书源**；结果按 `result.source_name` 分组 tab（复用现 `BookshelfPage.tsx:315-350` 的 tab 逻辑，把 `r.platform` 改为 `r.source_name`）。
- **URL 直达**（`SearchBar.tsx` URL tab）：删除硬编码域名推断（`135-142`）。粘贴 URL 后**由用户从下拉选择一个书源**（`/download/sources` 全量列表），请求 `GET /download/search?query=<url>&source=<name>`。
- **下载对话框**（`DownloadDialog.tsx`）：删除 mode/variant 询问，直接以 `source_name` 启动下载（`onStart(source_name)`）。
- **详情页**（`DetailPage.tsx`）：只带 `source_name`；无 `platformFromUrl`，`source_name` 来自搜索结果的 `r.source_name` 或用户选择。
- **设置页**（`SettingsPage.tsx`）：删除「下载模式」设置项与 `EngineSection` 的平台维度。改为「书源配置」：选一个书源 → 逐能力段（`search`/`novel_info`/`chapter_list`/`chapter_content`）渲染表单，落 `/config/sources/{name}`。
- **搜索历史**（`SearchHistoryPanel.tsx`）：条目显示 `source_name` 徽标；点击回填 keyword + 书源。

**新增书源管理界面**（design:247）：新文件 `frontend/src/features/sources/SourcesPage.tsx`：

- 列表：每个 `source_name` 一行，含 `capabilities`（cap→mode）摘要、`enabled` 开关（写 `/config/sources/{name}` 的顶层 `enabled`）、「编辑配置」入口。
- 路由/侧栏：`App.tsx` 的 `DESKTOP_ITEMS`(13-18)/`TO_PATH`(20-23) 加「书源」项，`<Routes>`(86-95) 加 `/sources`。
- hooks：`hooks/index.ts` 增 `useSourceConfig(source_name)`、`useSaveSourceConfig(source_name)`；`api/endpoints.ts` 增 `/config/sources*`。

---

## 7. 数据与兼容（定稿）

| 数据 | 处理 |
|---|---|
| `app_data/config/sites/*.yaml` | **直接丢、用户重配**（含 api key/headers/cookies）。文件名从 `fanqie.yaml` 变为按 `source_name`（`fanqie-api-rain.yaml` 等）。 |
| `search_history` 表 | **drop 重建**：新 schema `search_history(id, source_name TEXT NOT NULL, keyword TEXT NOT NULL, searched_at, UNIQUE(source_name, keyword))`。删除 `_migrate_search_history` 与 `platform='fanqie'` 硬编码。 |
| `template/storage/users/default/user_data.db` | **重建模板库**：`CREATE TABLE IF NOT EXISTS` 对已存在表无效，必须 `DROP TABLE search_history` 后按新 schema 重建（或删整库重生成），否则旧表结构残留、`test_user_db_template.py::test_template_schema_matches_runtime` 红。 |
| `template/config/sites/*.yaml` | 改为与新逐能力段结构一致，**按 `source_name` 命名**（10 个文件：`fanqie-api-rain.yaml` 等），内容由对应 `source.json.default_config` 展开（含顶层 `enabled`）。同时删除 `template/config/config.yaml` 的 `mode`。 |
| 收藏 / 分组 / 书签 / 已下载书籍 | **不受影响**：全部按 `novel_id` 索引，`novel_id` 只依赖书源返回的 url（见 §9 硬约束）。 |
| `bookmarks` 表 | 保留不动（无路由消费其 `platform` 列，见 §10）。 |
| 旧书 `Novel.source_name == ""` | `update`/前端**跳过并提示用户手选书源**（不清空、不猜测）。`Novel` 的空值语义=「旧数据或来源未知」。 |

---

## 8. 验收口径

- **每个任务结束后** `python -m pytest tests/ -q` 必须 **0 failed**（`skipped` 可保留）。**passed 总数可因合理删除废弃用例而低于 379**（基线 `379 passed, 1 skipped`），计划逐任务给出删除用例与预期 passed 区间，T15 给最终区间（不写死单一数字）。
- **中间态窗口说明**：Task 2–11 是有意的过渡窗口，过渡期的任务只保证**本任务相关测试子集 0 failed**；全量 `0 failed` 在 T15 收敛。但**任何任务都不得让 `backend.main`/`cli` import 崩**（否则测试收集全崩）——T2 删除 `shared.config` 旧函数时必须同 commit 清理其顶层 import 者（§5.2/§5.3）。
- `cd frontend; npx tsc --noEmit --project tsconfig.app.json` 通过。
- 涉及构建时 `npm run build` 通过。

---

## 9. 硬约束（影响 `novel_id` 稳定性）

`Novel.id = make_novel_id(书源返回的 url) = sha256(url)[:32]`，库内 `meta.id` 存该 url 原样。**本次改造不得改变任何书源返回的 url**（不改书源实现，也不要在 backend/CLI 侧做 URL「规范化」）。违反 = 已有书籍 id 漂移 = 书架/收藏/分组/阅读进度/下载目录/已导出文件全部对不上。

---

> 注：原「`/download/platform` 去留」已**定论删除**（职责并入 `/download/sources`，前端 `usePlatforms`/`downloadPlatforms` 一并删除、消费方改用 `useSources()`），不再列为未决。

## 10. 未决事项

1. **`bookmarks.platform` 列**：`shared/user_data.py:55-64,284-308` 的表仍带 `platform`；无后端路由消费（grep 无匹配）。**推荐：保留不动**（非本次范围，且按 `novel_id` 索引，`platform` 列不参与业务）。若要求彻底清除 platform 概念，需另立任务重建 bookmarks 表。
3. **URL 解析自动匹配**（design:278 未决 1）：`hosts` 消失后 core 无 URL→书源推断。本次采用「用户手选书源」。若日后要自动匹配，需书源在 `source.json` 声明 URL 模式，属后续增强。

---

## 11. 参考

- 现状盘点（逐文件行号）：`.superpowers/sdd/2026-09-25-followup/recon.md`
- core 设计：`docs/superpowers/specs/2026-09-24-book-source-flattening-design.md`
- 实施计划：`docs/superpowers/plans/2026-09-25-source-flattening-followup.md`
