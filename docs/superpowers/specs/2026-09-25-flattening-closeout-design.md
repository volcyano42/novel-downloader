# 书源扁平化 — 收尾设计（遗留清理 + 文档位置归一）

- 日期：2026-09-25
- 分支：`dev`
- 状态：**设计定稿**（用户已确认 §1–§7 分节设计）
- 前置：`docs/superpowers/specs/2026-09-25-source-flattening-followup-design.md`（契约收口）、
  `.superpowers/sdd/2026-09-25-followup/progress.md`（10 项 Minor 遗留清单）
- 基线（本机实测 2026-09-25）：`python -m pytest tests -q` = **389 passed, 1 skipped**；
  `npx tsc --noEmit --project tsconfig.app.json` = 0 错；`npm run build` = EXIT 0

---

## 1. 背景

书源扁平化（四层 `platform/mode/variant` → 一层目录 + `source.json`）的 core 层与 followup 阶段
（backend / CLI / 前端 / 配置 / docs，15 任务）**均已落地**：`platform` / `SHOW_NAME` /
`register_source()` / `platform_from_url()` / `canonical_book_url()` / `ID_PATTERN` 在代码中只剩
注释性提及，且 `tests/test_source_api.py:57` 有「这些符号必须已删除」的保护断言。

因此「收尾」不是重做重构，而是清理 **followup 阶段明确留档的 Minor 遗留**，以及一个结构性问题：

| 来源 | 内容 |
|---|---|
| `progress.md`「本阶段后续待办」1–10 | 10 项 Minor |
| 两份 `docs/` 并存 | 外层容器 `D:\Linux\novel-downloader\docs\`（非 git、被 .gitignore）与核心仓库 `novel-downloader/docs/`（入库）内容不同：外层独有 8 个文档、核心独有 28 个、7 个同名文件内容不同（外层为旧版） |

**实测复核**（本次逐项验证，非照抄留档）：

| # | 结论 | 证据 |
|---|---|---|
| 1 | 仍存在：未知 `source_name` → 500 | `backend/routers/download.py:23`（`_require_source` 只判非空）；`backend/routers/config.py:84-96`（直接 `capabilities()` / `merged_source_config()`，无校验）；`capabilities()` 对未知源返回 `{}`（`novelbase/source.py:118-124`），`merged_source_config()` 亦返回 `{}`，但 `is_source_enabled()` 会 `get_manifest()` 抛 `KeyError`（`shared/config.py:171-177`）→ 500 |
| 2 | 仍存在：`enabled` 双向不同步 | `SettingsPage.tsx:212` 切 `enabled` 只失效 `["source-config", src]`；`SourcesPage.tsx:196` 自带 `invalidateQueries(["sources"])` 但不失效 `["source-config", src]`。两页 `staleTime: Infinity`（`hooks/index.ts`）→ 互相滞后。**修正**：`progress.md` 记「跨页列表显示滞后」据此为**双向**缺一半，非单侧 |
| 3 | 仍存在：CLI 单引擎 | `cli/main.py:180`（`cmd_download`）、`:235`（`cmd_info`）传 `lambda m: engine`；`cli/main.py:99` 的 `_get_engine(source_name, mode=None)` 缺省只取 `capabilities(source_name)` 的**首个** mode → 跨能力 mode 不同的书源错用引擎 |
| 4 | 仍存在：~110 行逐字重复 | `SettingsPage.tsx:15-143`（`Row/Toggle/Select/Num/TextField/Range/Section/MODE_META/CAP_LABELS/ENGINE_FIELDS`）↔ `SourcesPage.tsx:9-117`（同名前 9 项） |
| 5 | 仍存在：文档残留 | `docs/source-plugin.md:70,107`（DrissionPage，实际已换 Playwright）、`docs/project/overview.md:23` 与 `docs/README.md:3`（称 docs/ 在外层容器不入库，实际核心仓库 docs/ 已入库）、`overview.md:64`（`novels.db`，实际每本一库） |
| 6 | 仍存在：脚手架与真实书源不一致 | `cli/main.py:385` 的 `common` 只有 `{"mode": mode}`；真实 `source.json` 的 `common` 含 `timeout/retry_times/delay/backoff_factor` + mode 专属字段（requests: `headers/cookies/proxies`；api: `key/params`；browser: `browser_type/headless/user_data_dir/viewport/extra_args/auto_reconnect`） |
| 7 | 仍存在：测试文件名残留 | `tests/test_cli_dev_new_variant.py`（内容已是 `dev new-source`）、`tests/test_cli_variant.py`（内容已是 `build_options(source_name, mode)`）——仅文件名带 variant |
| 8 | 仍存在：`updates.md` 未追平 | `docs/project/updates.md` 止于 2026-08-25；2026-09-24/25 两阶段（novel-id-url / 书源扁平化 core + followup）未记录 |

---

## 2. 范围

**做**：

1. `source_name` 未知 → 404（§4.1）
2. `enabled` 开关双向失效修复 + 前端书源配置表单去重（§4.2）
3. CLI 引擎按 mode 解析 + 脚手架 `common` 与出厂默认同源 + 测试文件改名（§4.3）
4. 文档残留修正、`updates.md` / `session-prompt.md` / `CHANGELOG.md` 追平（§4.4）
5. 两份 docs 位置归一：外层 8 个独有文档迁入核心并入库，外层指针化（§4.5）

**不做**：见 §5。

---

## 3. 已拍板决策（用户，2026-09-25）

| 编号 | 决策 | 理由 |
|---|---|---|
| D1 | 前端**抽共享组件、保留 SettingsPage 与 SourcesPage 两个入口** | 合并为单一入口会改导航信息架构、超出「收尾」；改动面最小 |
| D2 | 未知 `source_name` 在**所有按 `source_name` 取参的路由**统一 404 | 同类问题的单一口径；`download` 与 `config` 两侧同形 |
| D3 | 外层容器 8 个独有文档**迁入核心 `docs/` 并入库**，随后外层只留 `README.md` 指针 | 8 个文件在核心仓库内无同内容副本（逐文件 hash 实测 `UNIQ`），直接指针化会丢文档 |
| D4 | **保持本地不推送** | 与前两阶段整合决定一致；`dev` 仍领先 `origin/dev` 53 提交 |
| D5 | 收尾范围 = **全覆盖**（行为类 + 组件去重 + 文档 + 位置归一） | 用户明确选择 |

---

## 4. 目标形态

### 4.1 后端：未知书源统一 404（D2）

新增 `backend/services/source_guard.py`，作为**唯一校验点**：

```python
def require_known_source(source_name: str) -> str:
    """书源名必须已知（`list_sources()`），否则 404。"""
    # 未知 → raise HTTPException(404, f"未知书源: {source_name}")
```

- `backend/routers/download.py`：`_require_source(source, url)` 由「仅判非空」扩展为「非空 → `require_known_source()`」。
  该函数是 `search`（URL 分支）、`novel`、`chapters`、`chapter` 的公共入口，一处改全覆盖；
  空 `source` 的并发全启用分支（`search` 非 URL 分支）不受影响。
- `backend/routers/config.py`：`GET /config/sources/{source_name}`（`:84`）与 `PUT`（`:99`）入口先调
  `require_known_source()` → 未知 404，`PUT` 不再能凭空创建 `sites/{name}.yaml`。
- 语义边界：`capabilities()` / `merged_source_config()` 对未知源仍返回 `{}`（core 层宽容语义**不变**），
  404 只在 **HTTP 边界**产生。

测试：`tests/test_backend_config_routes.py`（或同名既有文件）+ `tests/test_backend_download_routes.py`
各补未知源 404 用例（GET / PUT / search URL 分支 / novel）。

### 4.2 前端：共享表单组件 + `enabled` 失效修复（D1）

**新增** `frontend/src/features/sources/sourceConfigForm.tsx`，从 `SourcesPage.tsx` 迁出并作为单一来源：

- UI 原子：`Row` / `Toggle` / `Select` / `Num` / `TextField` / `Range` / `Section`
- 常量：`MODE_META`（取 `SettingsPage` 带 `desc` 的版本）、`CAP_LABELS`、`ENGINE_FIELDS`
- 类型与表单：`EngineField`、`SourceConfigEditor({ name })`（含逐能力段渲染 + `renderField`）

**消费方**：

- `SourcesPage.tsx`：删 `:9-117` 的重复定义，改 import；`SourceRow` / `SourceConfigEditor` 逻辑不变。
- `SettingsPage.tsx`：删 `:15-143` 的重复定义；`SourceSection`（`:145`）**保留**「书源选择器 + 启用开关 + 折叠」
  三块自身逻辑（`enabled` 开关仍读 `useSourceConfig` 的 `cfg.enabled`，与 `SourceConfigEditor` 共用同一
  query key，不产生重复请求），并把自有的 `caps` / `merged` / `renderField` / 能力段渲染整块**替换**为
  `<SourceConfigEditor name={source} />`（与 `SourcesPage` 完全一致）。`FormatsSection` 不动。

**失效修复**：`hooks/index.ts` 的 `useSaveSourceConfig.onSuccess` 改为同时
`invalidateQueries({ queryKey: ["source-config", source] })` 与
`invalidateQueries({ queryKey: ["sources"] })`。
`staleTime: Infinity` 保留（`invalidateQueries` 会无视它强制刷新）。
`SourcesPage.tsx:196` 的局部 `onSuccess` invalidate **移除**（已由 hook 统一，避免两处各失效一半）。

**验证**：`tsc --noEmit` 0 错 + `npm run build` EXIT 0（前端无测试框架，不新增）。

### 4.3 CLI：引擎按 mode 解析 + 脚手架同源 + 测试改名

**(a) 引擎解析**

- `cli/core.py`：`_get_engine(source_name, mode=None, options_hook=None)`、
  `_make_engines(source_name, options_hook=None)` —— 建 Options 后、`create_engine` 前调用 `options_hook(options)`（依赖注入，避免 `cli.core` → `cli.main` 反向 import）。
- `cli/main.py`：把 `_get_engine`（`:99`）里的导出配置装配抽为
  `_apply_export_options(options) -> None`（`:110-124` 段）。
- `cmd_download`（`:174-182`）与 `cmd_info`（`:230-248`）改传
  `core._make_engines(source_name, options_hook=_apply_export_options)`，结束时按 `cache` 关闭全部引擎（不再 `engine.close()` 单个）；删除 `lambda m: engine` 写法。

**(b) 脚手架 `common` 与出厂默认同源**

`_scaffold_source`（`cli/main.py:365-389`）的 `common` 由 `{"mode": mode}` 改为：

```
common = {"mode": mode} | <该 mode 的出厂默认字段>
```

- `requests` / `browser`：`shared.config.ENGINE_DEFAULTS[mode]`（由 `RequestsOptions` / `BrowserOptions` dataclass 派生，`shared/config.py:61-65`）。
- `api`：`ENGINE_DEFAULTS["api"]` 现为空 dict → 改为从 `APIOptions` 的 dataclass 默认派生
  （使 `key` / `params` 进入脚手架与真实书源一致）。若 `ENGINE_DEFAULTS["api"]` 被补齐，须确认
  `merged_source_config` 合并结果不变（api 的 `Options` 由 `set_api_options` 消费，见 §7）。

**(c) 测试文件改名（零代码残留，仅文件名）**

- `tests/test_cli_dev_new_variant.py` → `tests/test_cli_dev_new_source.py`
- `tests/test_cli_variant.py` → `tests/test_cli_config.py`

**(d) 补测试**：`cmd_info` / `cmd_download` 按 mode 取引擎（monkeypatch `create_engine` 记录收到的
`options.mode`，断言两次不同能力 mode 各建一次、且 `options_hook` 被应用）。

### 4.4 文档残留修正与追平

| 文件 | 改动 |
|---|---|
| `docs/source-plugin.md:70,107` | `DrissionPage` → `Playwright`；文件顶部标注**本文为未实现的设想方案**（当前无插件进程实现） |
| `docs/project/overview.md:23` | 「docs/ 在外层容器，被 .gitignore 忽略，不入版本库」→「docs/ 随核心仓库入库（`novel-downloader/docs/`）」 |
| `docs/README.md:3` | 同上 |
| `docs/project/overview.md:64` | `novels.db（SQLite，每本小说一个独立 .db 文件）` → 删除 `novels.db` 措辞，改为「每本小说一个独立 `<id>.db`」 |
| `docs/project/updates.md` | 追加 **2026-09-24（Novel.id → sha256(url) / 书源扁平化 core）** 与 **2026-09-25（followup 15 任务 + 本次收尾）** 两段摘要 |
| `docs/session-prompt.md` | 「仍待收口」四项改写：①未知源 500 → 已修（统一 404）；②URL 自动匹配书源仍缺（保留为后续增强）；③重复 `source_name` 无检测（保留）；④`novel.extra["platform"]` 键名保留（值=`source_name`，数据兼容），并补本次收尾结果 |
| `CHANGELOG.md` | `## Unreleased` 段追加本次收尾条目（不新开版本段，不发版） |

### 4.5 两份 docs 位置归一（D3）

1. **迁入**（先做，进 git）：外层独有 8 个文件 → 核心 `docs/superpowers/{plans,specs}/` 同路径，
   单独一条 docs 提交：
   - `plans/2026-08-22-browser-auto-reconnect.md`、`plans/2026-08-22-novel-id-hash.md`、
     `plans/2026-08-25-restore-interactive-cli.md`、`plans/2026-08-25-site-config-variant-nesting.md`
   - `specs/2026-08-22-browser-auto-reconnect-design.md`、`specs/2026-08-22-novel-id-hash-design.md`、
     `specs/2026-08-25-restore-interactive-cli-design.md`、`specs/2026-08-25-site-config-variant-nesting-design.md`
2. **指针化**（迁入提交完成后再执行）：外层 `D:\Linux\novel-downloader\docs\` 仅保留 `README.md`，
   内容为「本目录已废弃，文档事实来源 = `novel-downloader/docs/`」+ 导航指向；外层其余文件删除
   （同名 7 个旧版由核心版取代，核心独有 28 个已在核心）。
3. **会话入口改指**：`.reasonix/skills/session-init/SKILL.md` 的「步骤 1」读取路径由外层 `docs/`
   改为核心 `novel-downloader/docs/`（同步说明「外层仅存指针」）。
4. 迁入文件中的旧引用（如 core 仓库内已不存在的同名 `-design.md`）**不逐字改写**——它们是历史计划/设计
   留档，遵循项目「已归档 spec 不追改历史超链接」的既有做法。

---

## 5. 非目标

- 不改 `novelbase/sources/*`（书源实现）、`novelbase/exporters/*`、`novelbase/core/*`；不改 `android/`。
- 不实现 URL → 书源自动匹配（需要书源声明 URL 模式，属后续增强）。
- 不迁移旧 `sites/{platform}.yaml` 与旧 `search_history`。
- 不删 `bookmarks.platform` 残留列（无消费者，按 `novel_id` 索引）。
- `storage` 死配置仅维持文档标注，不删字段。
- 不做前端测试框架引入。

---

## 6. 验收口径

- 每个任务结束：`python -m pytest tests -q` **0 failed**（`skipped` 可保留）。
- `cd frontend; npx tsc --noEmit --project tsconfig.app.json` **0 错**；涉及前端构建的任务加
  `npm run build` **EXIT 0**。
- 最终：全量一次复核 + `git status` 干净（无残留 scratch 文件）+ docs 位置归一完成
  （外层仅 `README.md`）。
- 行为类改动（§4.1–§4.3）按 **TDD**：先写失败测试再实现。

---

## 7. 风险与硬约束

1. **`Novel.id` 硬约束**：`Novel.id = sha256(url)[:32]`、库内 `meta.id` 存 url 原样。本次不得改任何书源
   返回的 url，也不得在 backend/CLI 侧做 URL 规范化。违反 = 已有书籍 id 漂移（书架/收藏/分组/阅读进度/下载目录全部对不上）。
   本次改动**不触及** `novelbase/sources/*` 与 URL 归一逻辑。
2. **`ENGINE_DEFAULTS["api"]` 补值的影响面**：`merged_source_config()` 用 `ENGINE_DEFAULTS.get(mode, {})` 做
   第 1 层合并；补齐 api 后，api 类书源的合并结果会新增默认字段（`key=""` / `params={}`）。
   实现时须确认 `shared/config.build_options(..., "api")` 与 `engine_manager.create_engine_for_request` 的
   行为不因多出这些默认键而改变（api 段由 `set_api_options` 消费）；否则改为只在**脚手架生成**时补齐，
   不动 `ENGINE_DEFAULTS`。
3. **前端去重不得改变行为**：两侧 `MODE_META` 字段数不同（`SettingsPage` 带 `desc`，`SourcesPage` 不带），
   统一取带 `desc` 版本；`Section` 的 `icon` 参数保持可传入（两页 icon 不同：`Settings` / `Layers`）。
4. **外层文件删除不可逆**（非 git 目录）：必须**先完成迁入提交**，再删外层副本（§4.5 顺序不可颠倒）。

---

## 8. 参考

- 契约收口 spec：`docs/superpowers/specs/2026-09-25-source-flattening-followup-design.md`
- 收口实施计划：`docs/superpowers/plans/2026-09-25-source-flattening-followup.md`
- 阶段台账（10 项 Minor 来源）：`.superpowers/sdd/2026-09-25-followup/progress.md`
- core 设计：`docs/superpowers/specs/2026-09-24-book-source-flattening-design.md`
- 用户决策：D1/D2/D3（dec-b41f20ad14ef8dfd）、范围与推送（dec-0ec9a5b4bda92529）
