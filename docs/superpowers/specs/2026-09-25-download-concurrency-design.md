# 下载并发模型重做 —— 设计

> 2026-09-25。把 `max_workers` 的语义改为「最大下载任务数」，并发改按**书源**分配（书源级 `concurrency`，默认 1、可配），并把 `delay` 的出厂默认改为 `[0, 0]`（不设置 = 不限速）。

## 背景

现在的并发与限速是两套不相干的东西：

- `max_workers`（`app_data/config/config.yaml` 的 `download.max_workers`，默认 3）= **任务内**章节并发（`asyncio.Semaphore`）。
- `delay`（书源逐能力配置，出厂默认 `[3, 5]`）= 每个请求前的 `asyncio.sleep(random.uniform(delay))`。

由此带来两个问题：

1. **慢**：出厂 `delay=[3,5]` 让每个请求前强制等 3–5 秒（即使目标站不限速），叠加并发 3 → 约 **1.33 s/章**。作对照，legado 的并发单位是章节、线程池默认 12、**默认不限速**（书源的 `concurrentRate` 不填即不限流，配了 `"3/2000"`／`"1500"` 才限）。
2. **任务之间无任何并发限制**：`create_task` 直接 `loop.create_task`，同时下 5 本书就是 5×3 = 15 个并发请求，谁都不管；而"限速"的最小单位本该是**书源**（同一个站该被一起限）。

用户诉求：`max_workers` 语义改为「最大下载任务数」，并发按书源分配（每源一个并发数），`delay` 语义不变、默认改为 `[0, 0]`。

## 现状调查（2026-09-25 实测）

| 事实 | 证据 |
|---|---|
| `max_workers` 是**任务内**章节并发 | `backend/services/task_manager.py:170` `sem = asyncio.Semaphore(max(1, max_workers))`；CLI 同形（`cli/core.py:161`、`cli/interactive.py:193`） |
| 任务之间无限制 | `task_manager.py:246` `loop.create_task(_run_download(task, source_name))`，无全局额度 |
| `delay` 在引擎里是「每请求前等待」 | `novelbase/core/engine.py:142-143`（同步）/`:173-174`（异步）`await asyncio.sleep(random.uniform(*self.options.delay))` |
| `delay` 出厂默认 3–5 秒 | 10 个 `novelbase/sources/*/source.json` 的 `common.delay = [3, 5]`；代码兜底 `cfg.get("delay", [3, 5])` 共 6 处（`shared/config.py:330/340/362`、`backend/services/engine_manager.py:126/143/155`） |
| `skip_delay=True` 可完全跳过 | 搜索/CLI 更新路径在用（`cli/interactive.py:69/94`、`cli/core.py:112/122`） |
| 引擎层已支持并发 | `BrowserEngine` 自带 page 池（`_idle_pages` + `_acquire_page`/`_release_page`，`engine.py:339-351`，注释：并发数由上层 Semaphore 控制）；`APIEngine`/`requests` 走 httpx client |
| `source.json` 顶层**不校验未知字段** | `novelbase/sources/manifest.py:44-58` 只校验必填 `source_name`/`enabled` 与 `default_config`/`common` 的类型；未知顶层键不报错。`common` 的字段会被并入能力段并受 `MODE_FIELDS` 校验 → **新字段不能放 `common`** |
| 用户层顶层字段的既有读法 | `shared/config.py:225-233` `is_source_enabled()` 读 `_user_site_cfg(source).get("enabled")` —— `concurrency` 可照此读顶层 |
| 任务状态取值 | `task_manager.py`：`queued`（新增）/`downloading`/`paused`/`completed`/`failed`/`partial`/`cancelled`；前端 `DownloadTask.tsx:7` 的 `TaskStatus` 需同步 |

## 目标

1. `max_workers` = **最多同时运行的下载任务数**（超出则排队，任务状态 `queued`）
2. 新增**书源级** `concurrency`（默认 1，可配，**跨任务共享**）：同一书源同时最多几个请求在飞
3. `delay` 语义不变（每请求前随机等待），**出厂默认改为 `[0, 0]`**（不设置 = 不限速）
4. 去掉"任务内章节并发 = max_workers"的旧语义（章节并发改由书源额度决定）
5. 界面可见：排队中状态、书源并发数输入、「下载线程数」改名

## 非目标（YAGNI）

- **不引入 legado 式时间窗并发率**（`"3/2000"`）——本轮只做「间隔 + 书源并发数」
- 不改 `skip_delay` 语义（搜索/更新仍可跳过等待）
- 不改图片并发（`async_fetch_images(max_workers=5)` 原样）
- **不动用户层配置**：`sites/{name}.yaml` 照常参与三层合并，用户显式值优先（合并语义不变）
- 不做并发数的自动调优、不做站点风控探测
- 不引入"每任务独立额度"（额度就是书源级的）

## 设计

### 1. 三层语义

| 层 | 参数 | 存储 | 默认 | 语义 |
|---|---|---|---|---|
| 全局 | `max_workers` | `config.yaml` 的 `download` | 3 | **最多同时运行的下载任务数**（超额排队） |
| 书源 | `concurrency`（新增） | `source.json` **顶层**（可选）+ 用户层 `sites/{name}.yaml` 顶层覆盖 | 1 | 该源同时最多几个请求在飞，**跨任务共享** |
| 书源·逐能力 | `delay` | `common` → 各能力段（现状）+ 用户层覆盖 | **`[0, 0]`** | 每个请求前的随机等待（语义不变） |

### 2. 出厂默认的改动（只改出厂与代码兜底）

- `novelbase/sources/*/source.json`（10 个）：`common.delay` 由 `[3, 5]` → `[0, 0]`
- 代码兜底默认：`cfg.get("delay", [3, 5])` → `[0, 0]`（`shared/config.py` 3 处、`backend/services/engine_manager.py` 3 处）
- `novelbase/core/options.py` 的 `Options.set_*_options(delay: Sequence[float] = (3, 5))` 默认值同步为 `(0, 0)`
- 用户层一律不动（三层合并照旧；显式配置优先）

### 3. 书源级 `concurrency`

**存储**：`source.json` 顶层（与 `source_name` / `enabled` 同级，**可选**，缺省 1）；用户层 `sites/{source_name}.yaml` 顶层可覆盖。

**读取**（`shared/config.py`，与 `is_source_enabled()` 同形）：

```python
SOURCE_CONCURRENCY_DEFAULT = 1

def source_concurrency(source_name: str) -> int:
    """该书源的并发额度：用户层顶层 `concurrency` 覆盖出厂顶层，缺省 1。

    非法值（非正整数）忽略并回退默认；未知书源同样返回默认。
    """
    from novelbase.source import get_manifest
    user = _user_site_cfg(source_name)
    if _is_positive_int(user.get("concurrency")):
        return user["concurrency"]
    try:
        declared = get_manifest(source_name).get("concurrency")
    except (KeyError, ManifestError):
        return SOURCE_CONCURRENCY_DEFAULT
    return declared if _is_positive_int(declared) else SOURCE_CONCURRENCY_DEFAULT
```

**API**：`GET /api/v2/config/sources/{name}` 返回值加 `concurrency`（有效值）；`PUT` 支持顶层 `concurrency`（与 `enabled` 同级处理：正整数写入用户层顶层，否则忽略）。

### 4. 后端并发结构

```python
_tasks_sem = asyncio.Semaphore(max(1, max_workers))          # 任务级（进程内单例）
_source_sems: dict[str, asyncio.Semaphore] = {}              # 书源级，跨任务共享
_source_sems_lock = threading.Lock()                          # 与 _tasks_lock 同风格

def _source_sem(source_name: str) -> asyncio.Semaphore:
    """按书源取（或建）并发额度；额度取自 shared.config.source_concurrency()。"""
```

- **实现采用轮询式计数（已批准偏差）**：`_running_tasks: set[str]` + `_source_active: dict[str, int]`（配 `_tasks_lock` 保护），而不是固定容量的 `asyncio.Semaphore`。理由：`max_workers` 与书源 `concurrency` 都是运行时可改的配置，轮询式改完立即生效（固定容量 Semaphore 需要重建且会丢失在等者）；粒度 0.05–0.2s，无竞争时零等待 —— 与项目既有的 `_wait_if_paused` 轮询风格一致。
- `create_task`：任务以 `status="queued"` 入表（不再直接进 downloading）
- `_run_download` 开头：

```python
    async with _tasks_sem:                 # 排到任务额度
        with _tasks_lock:
            if task["_cancel"].is_set():
                return
            task["status"] = "downloading"
        ...原有流程...
```

- **书源额度覆盖该任务发出的所有请求**（不只章节内容）：`resolve_meta` / `resolve_chapter_list` / `resolve_chapter` 调用前都要 acquire（`resolve_meta`、`resolve_chapter_list` 每个任务各一次，`resolve_chapter` 每章一次），否则「同一书源同时最多 N 个请求」不成立（搜索/目录请求会绕过额度）
- 章节请求前拿书源额度（`_download_one` 内，包住 `resolve_chapter`）：

```python
        async with _source_sem(source_name):
            downloaded = await resolve_chapter(ch, source_name, engines, mode_overrides=_caps)
```

- **删除**任务内的 `sem = asyncio.Semaphore(max(1, max_workers))` 与 `_run_one` 的信号量包装（章节并发 = 书源额度）

**状态与边界**：

| 场景 | 语义 |
|---|---|
| 超额任务 | `status="queued"`，前端显示「排队中」；拿到额度后转 `downloading` |
| 排队中删除 | 直接 `cancelled`（`delete_task` 已通用，需保证协程在拿到额度后立即退出） |
| 排队中暂停 | 允许：置 `_pause` 后**不抢任务槽**（保持 `queued`，不阻塞队列）；`resume` 后才去抢额度并转 `downloading` |
| `max_workers` 缩小 | 只影响新排队的任务（已持额度的继续跑完） |

### 5. CLI 侧

CLI 是「单任务」场景，不引入任务排队，但**书源额度同样生效**：

- `cli/core.py` / `cli/interactive.py` 的章节并发上限改为 `min(max_workers, source_concurrency(source_name))`（默认即 1，与 backend 一致）
- `cli/main.py --workers` / `cli/menus.py` 的文案由「下载线程数」改为「并行章节数（受书源并发额度约束）」

### 6. 前端

- `DownloadTask.tsx`：`TaskStatus` 加 `"queued"`，`statusConfig` 加「排队中」（浅灰 `bg-slate-100 text-slate-500`），图标用 `Loader2`（不转）或 `Clock`
- `SourceConfig` / `SourceConfigEditor`：书源折叠条在「启用」旁加「并发数」数字输入（`min=1`），提交 `{ concurrency: n }`（顶层，与 `enabled` 同级）
- 设置页「下载线程数」→「**最大下载任务数**」（`SettingsPage.tsx` 的下载区标签与说明）
- `endpoints.ts`：`SourceConfig` 类型加 `concurrency: number`；`saveSourceConfig` 的 body 类型允许顶层 `concurrency`
- 下载管理页：`queued` 的任务也显示（进度条不显示，显示「等待中…」）

### 7. 文档

- `docs/project/config.md`：`max_workers` 新语义（最大任务数）、`delay` 默认 `[0,0]`
- `docs/project/sources.md`：书源级 `concurrency`（顶层字段 + 用户层覆盖 + API）
- `docs/session-prompt.md`：关键约定补一条「并发模型：任务数上限 + 书源级并发额度 + 逐能力 delay」
- `docs/project/updates.md`：本轮变更摘要

## 数据流

```
create_task → task(status="queued") → _run_download
   → async with _tasks_sem            # 任务级排队（max_workers）
   → status="downloading"
   → 每章：async with _source_sem(source)   # 书源级额度（concurrency，跨任务共享）
        → engine.async_fetch_text(..., delay=该能力段 delay)   # 逐能力等待，默认 [0,0]=不等
```

## 错误处理

- `concurrency` 非法（0/负/非整数/字符串）→ 回退 1（读取侧过滤；写入侧拒绝非正整数）
- `max_workers` 非法（0/负）→ 回退 1（`max(1, ...)`，现状已如此）
- **配置读取不得进热路径**：`source_concurrency()` 会读 `sites/*.yaml` 与 `source.json`（无缓存），因此只在任务开始时取一次并缓存进闭包；不得在每章（`_update_eta` 等）重复调用，尤其不得在持锁段内做这类同步 IO
- **额度必须成对释放**：任务槽与书源槽的 acquire/release 全部包在 `try/finally`；异常、取消、重试分支都要覆盖（配额泄漏会让该源永久卡死）
- 排队任务取消：协程拿到额度后立即检查 `_cancel` 并退出，不留 `downloading` 残影
- 书源 Semaphore 池的并发创建：单事件循环内 `dict` 读写在同步段完成（与既有 `_tasks` 同风格），必要时用 `threading.Lock`

## 测试

- `tests/test_source_concurrency.py`（新增）：缺省 1 / 出厂顶层声明生效 / 用户层顶层覆盖 / 非法值回退 1 / 未知书源返回 1
- `tests/test_task_queue.py`（新增）：`max_workers=1` 时第二个任务停在 `queued`、第一个完成后转 `downloading`；排队中删除 → `cancelled` 且不进入下载
- `tests/test_source_concurrency_shared.py`（新增）：同一书源两个任务不会同时进入请求（用 spy 记录 enter/exit 计数，断言不并发）；不同书源可并行
- 释放路径必须被测：**异常路径**（书源抛错）与**取消路径**（下载中/排队中取消）之后，任务槽与书源额度都要回到零（额度泄漏是最致命的失败模式）
- `tests/test_delay_default.py`（新增）：未配置 delay 时 `build_options(...)` 的 `options.requests/browser/api.delay == (0, 0)`；用户层显式 `delay` 仍生效
- 既有测试同步：凡断言 `delay == (3, 5)` 的用例改为 `(0, 0)`（全仓 grep `3, 5` 复核）
- 前端：`npx tsc -b` 0 错、`npm run lint` 无新增告警；手测清单见下
- 全量：`python -m pytest tests -q` 基线 **449 passed, 1 skipped** → 目标 0 failed

## 风险

| 风险 | 说明 | 缓解 |
|---|---|---|
| 默认不限速触发风控 | `delay=[0,0]` + 书源并发 1 已比现状温和（现状 3 并发），但仍比"每请求等 3–5 秒"激进 | 书源级 `delay` / `concurrency` 可随时收紧；文档写明 |
| `max_workers` 语义变更 | 老用户以为它是"章节并发"，实际变成"任务数" | 前端标签改「最大下载任务数」+ 文档 + `updates.md` 明写 |
| 排队任务的状态流转 | `queued` 与 pause/resume/delete 的交互 | 见 §4 状态表；单测覆盖 |
| browser 模式并发 | 额度 >1 会多开 page（内存↑），且多 page 共用同一 Chromium | 默认 1；文档提示调高需自担资源 |
| 任务级额度泄漏 | 协程异常退出未释放额度 | `async with` 保证释放；取消路径在 `async with` 内 return |

## 验收（手工）

1. 同时下 5 本书（`max_workers=3`）→ 下载管理显示 3 个「下载中」＋2 个「排队中」，前 3 个完成后排队者自动开始
2. 默认配置下（未配 delay）→ 请求之间不再有 3–5 秒的固定等待
3. 设置页把某书源并发数改为 3 → 该源下载明显加速；同一书源的两个任务仍共享这 3 个额度
4. 设置页全局标签显示「最大下载任务数」
5. 排队中删除任务 → 该任务直接消失，不出现"幽灵下载"

## 已知影响（如实说明）

本机 `app_data/config/sites/*.yaml` 里已有历史写入的 `delay: [3, 5]`，按三层合并语义它会继续覆盖新的出厂默认 —— 所以**改完默认值后，本机默认仍是 3–5 秒**，需要在设置页把相应书源的 delay 调下来（或清掉该键）。这不是要清理的数据，而是合并语义的正常结果。
