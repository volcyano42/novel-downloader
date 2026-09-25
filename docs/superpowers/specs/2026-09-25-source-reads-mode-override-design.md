# 来源读点 + 用户可选 mode + 设置/书源整合 —— 设计

> 2026-09-25。承接《Novel.source_name 剥离》（`2026-09-25-novel-source-name-detach-design.md`），
> 让来源真正被消费，并放开书源 mode 的用户覆盖；同时把书源管理并入设置页、修掉请求头的显示/写回缺陷。

## 背景

上一轮把「来源」从 `novelbase` 的 `Novel` 移出，落到 `shared/user_data.py` 的 `novel_sources` 表，
并完成存量回填（本机 35 本全部有来源）。但来源目前**只有一个读点**（CLI 的「更新已有小说」），
界面上看不到、用不上：书架卡片与详情页都不显示来源，详情页「检查更新 / 下载选中」在本地书场景下
必须让用户手选书源。

同时，书源 `mode` 依据 2026-09-25 扁平化的决定「**由书源自己在 `source.json` 里声明，用户不再选**」，
前端只能看不能改；而书源管理页（`/sources`）与设置页的书源区各自实现了一套「选书源 → 展开编辑」，
彼此重复。

本轮把来源接上读点、放开 mode 的用户覆盖、把书源管理并入设置页。

## 现状调查（2026-09-25 实测）

| 事实 | 证据 |
|---|---|
| 列表端点不含来源 | `backend/routers/storage.py:86-99` 的 `GET /storage/novel` 手工拼 dict，无 `source_name` |
| 详情端点不含来源 | `backend/routers/storage.py:54-66` 的 `_novel_to_meta()` → `NovelMeta`（`backend/schemas/storage.py:16-26`），无 `source_name` |
| 批量查询函数**已实现但无调用方** | `shared/user_data.py:320` 的 `get_novel_sources(novel_ids)`（当初即为列表 join 预留） |
| 删除清理漏了 CLI 两条路径 | HTTP 端点已清理（`backend/routers/storage.py:138`）；`cli/main.py:264` 与 `cli/menus.py:328` 直调 `storage.delete_novel()` **未清理** → 本机已积累 1 条孤儿行（`novel_id=fanqie_1`，非 sha256 形态，为早期试跑残留） |
| 用户层 mode 被主动剔除 | `shared/config.py:220` 的 `user_cap = {k: v for k, v in user_cap.items() if k != "mode"}`，注释「mode 恒取书源声明」 |
| core 的 mode 只有声明来源 | `novelbase/source.py:116-122` 的 `capabilities()` 读 `get_manifest()`；`resolve()` 返回该声明 mode（`:138-146`） |
| 分发层按 mode 取引擎 | `novelbase/core/downloader.py:31-80`，4 个公共函数各自 `fn, mode = _resolve(...)` → `engines(mode)` |
| mode 消费点共 10 处 | `backend/routers/config.py:96`、`backend/routers/download.py:174`、`backend/services/engine_manager.py:26`、`backend/services/task_manager.py:49`、`cli/core.py:83`、`cli/interactive.py:30`、`cli/main.py:319,328`、`cli/menus.py:84`、`shared/config.py:211,279`（后两处在 shared 内部） |
| 现有 10 个书源**全部单一 mode** | 每个 `source.json` 只有顶层 `common.mode`，`default_config` 的 4 个能力段均为 `{}`（不含独立 mode）——逐能力覆盖在数据层可行，且与现有粒度一致 |
| 详情页三处操作都要外部传书源 | `DetailPage.tsx:213` `runCheckUpdate(src)`、`:235` `runDownloadLocal(src)`、`:251` `runDownload(src)`；书源来自对话框或 `location.state.source`，本地书直接进详情页时为空 |
| 前端 mode 只读 | `sourceConfigForm.tsx:137-145` 只渲染 `MODE_META[mode]` 标签，无选择控件 |
| `headers` 显示与写回双错 | `sourceConfigFields.ts:41` 声明 `headers` 为 `type: "text"`；`sourceConfigForm.tsx:116-117` 的 text 分支是 `String(val ?? "")` → dict 显示成 `"[object Object]"`，且编辑后以**字符串**写回 `sites/{source_name}.yaml`，破坏请求头 |
| 设置页与书源页重复 | 设置页 `SourceSection`（`SettingsPage.tsx:16-60`）是「横排按钮选一个 + 展开」；书源页 `SourceRow`（`SourcesPage.tsx:9-50`）是折叠条 —— 两套实现 |

## 目标

1. 来源可读：`GET /storage/novel` 与 `GET /storage/novel/{id}/meta` 返回 `source_name`；书架卡片与详情页显示
2. 详情页「检查更新 / 下载选中」默认使用**该书来源**，不再强制手选
3. 用户可**逐能力覆盖 mode**（`source.json` 声明降级为默认值），backend 与 CLI 行为一致
4. 书源管理并入设置页：每个书源一个折叠条，展开即编辑（逐能力字段 + mode 下拉 + 恢复默认）
5. 修掉 `headers` 的 `[object Object]`（显示与写回都修）
6. 补齐 CLI 两条删书路径的来源清理

## 非目标（YAGNI）

- **不把 mode 覆盖下沉到 core**：`novelbase/source.py` 的 `capabilities()` / `resolve()` 语义不变，
  core 依旧不感知用户态；覆盖发生在调用方（`shared` + `backend` / `cli`）
- **不保证跨 mode 真能跑**：同一份能力实现换个引擎未必可用（见「风险」）；本轮只保证覆盖值被正确解析、传递、落库、回显
- **不把 `cookies` / `proxies` 加进表单**（本轮只修 `headers`；`cookies` / `proxies` 仍是 `source.json` 层字段）
- 不改 `SearchResult.source_name`、搜索历史、`bookmarks.platform`
- 不做来源筛选 / 分组
- 不动公开库 `novel-crawler`

## 设计

### 1. 来源读点

**后端**

- `backend/schemas/storage.py`：`NovelMeta` 加 `source_name: str | None = None`（可选字段，`fetchMeta` 等复用同一模型处不填即 `None`）
- `backend/routers/storage.py`：
  - `_novel_to_meta(novel)` 填 `source_name=get_novel_source(novel.id)`
  - `list_novels()` 先物化 `novels = list(store.iter_metas(include_images=True))`，再用
    `get_novel_sources([n.id for n in novels])` **一次批量查**（避免 N+1），逐项写入 `"source_name": sources.get(novel.id)`
  - `PUT /storage/novel/{id}/meta`（`save_meta`）**不写来源**：来源不由前端写

**前端**

- `frontend/src/api/endpoints.ts`：`NovelMeta` 接口加 `source_name?: string | null`
- 书架卡片（`BookCard.tsx:225`）：该行现显示 `novelId`（sha256 前 32 位，对用户价值低），**改为显示 `source_name`**；
  无来源时**不渲染该行**。新增可选 prop `sourceName?: string | null`，`BookshelfPage.tsx:208` 传入
- 详情页（`DetailPage.tsx:314-318` 区域）：本地书显示 `localMeta.source_name`，远端模式显示 `location.state.source`（`st?.source`）；
  无来源不渲染

### 2. 详情页默认使用该书来源

`runCheckUpdate` / `runDownloadLocal` / `runDownload` 的书源入参默认值改为：

| 场景 | 默认来源 |
|---|---|
| 本地书（有 `localMeta`） | `localMeta.source_name` |
| 远端书 | `location.state.source` |

对话框仍可改（保留逃生口）；两者皆空时维持现状（要求用户选择）。

### 3. 用户逐能力覆盖 mode

**读取层（`shared/config.py`，新增唯一入口）**

```python
def effective_capabilities(source_name: str) -> dict[str, str]:
    """有效 mode 映射：用户层 `sites/{source_name}.yaml` 的 `{cap}.mode` 覆盖 `source.json` 声明。"""
```

- `merged_source_config()`（`:202-222`）：改用 `effective_capabilities()` 选 `ENGINE_DEFAULTS[mode]`，
  并**不再剔除**用户层的 `mode` 键（表单要回显）；其余字段语义不变
- `build_options()`（`:269-290`）：用 `effective_capabilities()` 反查能力段（原先用 `capabilities()`）

**core（`novelbase/core/downloader.py`，纯加法、向后兼容）**

4 个公共分发函数加可选 kwarg `mode_overrides: dict[str, str] | None = None`（能力名 → mode）：

```python
fn, mode = _resolve(source_name, "chapter_content")
mode = (mode_overrides or {}).get("chapter_content") or mode
... await fn(chapter=chapter, engine=engines(mode), **kwargs)
```

`resolve()` 与 `engines(mode)` 签名**都不改**；未传 `mode_overrides` 时行为与现在完全一致。

**调用方（构造 `mode_overrides` 与引擎缓存键时统一用有效 mode）**

| 位置 | 改法 |
|---|---|
| `backend/routers/config.py:96` | `GET sources/{name}` 的 `capabilities` 返回**有效 mode**，另加 `declared_capabilities`（声明值，供「恢复默认」显示） |
| `backend/routers/download.py:174` | `/download/sources` 的 `capabilities` 返回有效 mode |
| `backend/services/engine_manager.py:26` | `_capability_for_mode()` 用有效 caps 反查（缓存键 `(source_name, mode)` 自然按有效 mode 区分，改 mode 后新键生效，无需显式失效） |
| `backend/services/task_manager.py:49` | 主 mode 预热用有效 caps，并把 `mode_overrides` 透传给 4 个分发函数 |
| `cli/core.py:83`、`cli/interactive.py:30`、`cli/main.py:319,328`、`cli/menus.py:84` | 换用 `effective_capabilities()`；引擎按有效 mode 建，调用分发时透传 `mode_overrides` |

**写入层（`backend/routers/config.py::save_source_config`）**

- `config[cap].mode` 为字符串 → 写入用户层该能力段的 `mode`（覆盖）
- `config[cap].mode` 为 `null` → **删除**该键（恢复书源声明；现有 `deep_merge` 不支持删键，需特判）
- 其余字段沿用现有 `deep_merge` 语义

**前端（`SourceConfigEditor`）**

- 每个能力段标题行加 mode 下拉（`browser` / `requests` / `api`，标签取 `MODE_META`），初值 = 有效 mode
- 未覆盖时显示占位「默认：{declared}」；选自定义值后出现「恢复默认」（提交 `mode: null`）
- 字段列表按**有效 mode** 取 `ENGINE_FIELDS[mode]`（切换 mode 后字段集随之变化）

### 4. 设置页 × 书源页整合

- 抽共享组件 `SourceAccordion`（折叠条）：收起显示 `source_name` + enabled 开关 + 能力 badge，
  展开渲染 `SourceConfigEditor`（含 mode 下拉）
- 设置页 `SourceSection`（`SettingsPage.tsx:16-60`）由「横排按钮选一个」改为**每源一个折叠条**
- 删除 `SourcesPage.tsx`；路由 `/sources` 改为 `<Navigate to="/settings" replace />`（保留旧深链）
- 侧边栏移除「书源」项（`App.tsx` 的 `DESKTOP_ITEMS` / `TO_PATH` / `NavItem` 同步收窄）

### 5. `headers` 显示与写回修复

- `sourceConfigFields.ts`：`headers` 的 `type` 由 `"text"` 改为新增类型 `"json"`
- `sourceConfigForm.tsx`：
  - 新增 `JsonField` 组件：值以 `JSON.stringify(val, null, 2)` 初始化到本地文本 state，`onBlur` 时 `JSON.parse`
  - 解析成功 → 以**对象**写回；解析失败 → 不写回并就地提示（不破坏既有配置）
  - 空文本 → 写回 `{}`

### 6. CLI 删书清理

- `cli/main.py::cmd_delete`（`:264` 附近）与 `cli/menus.py::do_delete`（`:328` 附近）在 `storage.delete_novel()` 后补
  `delete_novel_source(novel_id)`；沿用 `cli/core.py:138` 的**函数内懒 import** 风格
- 附带清理本机孤儿行 `fanqie_1`（如用户同意）

## 数据流

```
显示：storage 读 Novel（纯小说数据） + user_data.get_novel_source(s) → API 返回 source_name → 书架卡片 / 详情页

更新/补章：详情页默认 source = 该书来源 → fetchChapterList(url, source) → downloadChapters(..., source)
          → backend task_manager → resolve_*(url, source, engines, mode_overrides=effective_caps(source))
          → fn(engine=engines(effective_mode), …)

改 mode：设置页 mode 下拉 → PUT /config/sources/{name} {config:{cap:{mode}}}（null=删键）
        → sites/{name}.yaml → effective_capabilities() 立即可见 → 引擎按新 mode 建（缓存键含 mode）
```

## 错误处理

- 未知 `source_name`：沿用 `backend/services/source_guard.py` 的 404 边界
- 书源无声明能力（`capabilities()` 为空）：`effective_capabilities()` 返回 `{}`，端点与 UI 显示「无能力」
- 用户层写了非法 mode（手改 yaml）：`effective_capabilities()` **忽略非法值**回退声明值（合法集 = `MODE_META` 的 3 个 key），不抛异常
- `headers` JSON 解析失败：不写回、就地提示
- 来源缺失（老书未回填 / 未知域名被跳过）：UI 不显示该行；详情页默认来源为空 → 维持现状（要求用户选）

## 测试

- `tests/test_storage_source_reads.py`（新增）：`list_novels` 批量返回来源、`get_meta` 返回来源、无记录为 `None`（FakeStore + 现有 `isolated_user_db` 手法）
- `tests/test_config_effective_mode.py`（新增）：`effective_capabilities()` 覆盖/回退/非法值忽略；`merged_source_config()` 按有效 mode 取默认字段且保留 `mode`；`build_options()` 用有效 mode 反查
- `tests/test_downloader_mode_overrides.py`（新增）：`mode_overrides` 生效（`engines` 收到覆盖后的 mode）、缺省时行为不变
- `tests/test_novel_source_writes.py`（扩展）：CLI 两条删书路径清理来源
- `tests/test_backend_config_routes.py`（新增或扩展）：`GET sources/{name}` 同时返回有效与声明 mode；`PUT` 的 `mode: null` 删除键
- 前端：`npx tsc --noEmit`；`headers` 的 JSON 字段与 mode 下拉人工自测（表单类改动无前端测试框架）
- 全量：`python -m pytest tests -q` 基线 **416 passed, 1 skipped** → 目标 0 failed

## 风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| 跨 mode 覆盖不可用 | 同一能力实现换引擎未必能跑：`api` 依赖 Rain.ink key，`requests`/`browser` 直连语义不同 | 本轮只保证覆盖值全链路正确；UI 提示风险不阻止；不做「三 mode 全通」的承诺 |
| 覆盖把源改坏后无法工作 | 用户选了不兼容 mode，下载/搜索失败 | 前端「恢复默认」（`mode: null`）一键回退；失败信息沿用既有书源错误路径 |
| 引擎缓存残留旧 mode 实例 | 缓存键 `(source_name, mode)`，改 mode 后旧键仍驻留内存 | 键不同即不串用；进程内多留一个引擎可接受（既有 `invalidate_engine` 已可清理） |
| backend / CLI 行为分叉 | 10 处消费点若漏改，UI 选的 mode 在 CLI 不生效 | 统一走 `shared.config.effective_capabilities()`；测试覆盖 CLI 与 backend 两侧 |
| `headers` 写回仍可能被误存为字符串 | 旧数据里若已存在字符串形态的 headers | `JsonField` 对非字符串值走 JSON 渲染；字符串值原样展示，用户确认后按 JSON 解析写回 |

## 文档与约定修订

- **约定反转**：`docs/session-prompt.md:37` 的「mode 由书源自己在 `source.json` 里声明，用户不再选 mode（2026-09-25）」
  改为「**书源声明为默认，用户可逐能力覆盖**（2026-09-25 二次修订）」
- `docs/project/sources.md`、`docs/project/config.md` 同步说明 `effective_capabilities()` 与用户层 `mode` 语义
- 本轮完成后更新 `docs/project/updates.md`

## 后续（不在本轮）

- 若用户确需 `cookies` / `proxies` 可视化编辑，再评估表单扩展
- 详情页「检查更新」批量更新的并发策略（多本同时检查）未涉及
