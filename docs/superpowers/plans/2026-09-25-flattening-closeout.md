# 书源扁平化收尾 — Implementation Plan

> **状态：✅ 已完成（2026-09-25）** —— Task 1–7 全部执行并验证。
> `python -m pytest tests -q` = **401 passed, 1 skipped, 0 failed**（计划基线 389 passed / 1 skipped）；
> `git diff --stat 1e7a1a2..HEAD -- novelbase/sources novelbase/core novelbase/models novelbase/utils` = **空**（`Novel.id` 硬约束满足）。
> 各任务的产出提交见文末「完成记录」。本文件此前 51 个 checkbox 长期未回填，正是 Task 5–7 被遗漏的根因。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理书源扁平化重构遗留的 6 项 Minor（未知书源 404、`enabled` 双向失效、CLI 单引擎、前端 ~110 行重复、脚手架与真实书源不一致、文档残留），并把两份并存的 `docs/` 归一为核心仓库一份。

**Architecture:** 不动 core（`novelbase/sources/*`、`novelbase/core/*`）与导出器；改动集中在 **HTTP 边界**（新增 `backend/services/source_guard.py` 作唯一校验点）、**前端共享组件**（`features/sources/sourceConfigForm.tsx`）、**CLI 引擎解析**（`options_hook` 依赖注入）与**文档**。

**Tech Stack:** Python 3.10+ / FastAPI / pytest / React 19 + TypeScript + Vite + @tanstack/react-query / PowerShell（Windows 本机）。

**设计依据：** `docs/superpowers/specs/2026-09-25-flattening-closeout-design.md`（commit b4df309）。

## Global Constraints

- **基线（不可后退）**：`python -m pytest tests -q` = **389 passed, 1 skipped, 0 failed**；`cd frontend; npx tsc --noEmit --project tsconfig.app.json` = **0 错**；`npm run build` = **EXIT 0**。
- **每个任务结束**：`python -m pytest tests -q` **0 failed**（`skipped` 可保留）。行为类改动（Task 1/3/4）**先写失败测试**。
- **`Novel.id` 硬约束**：`Novel.id = sha256(url)[:32]`、库内 `meta.id` 存 url 原样。**不得改任何书源返回的 url**，不得在 backend/CLI 侧做 URL 规范化；`git diff --stat -- novelbase/sources novelbase/core novelbase/models novelbase/utils` 在本计划全部任务结束后必须为**空**。
- **不改**：`novelbase/sources/*`、`novelbase/exporters/*`、`novelbase/core/*`、`android/`、`app_data/config/sites/*.yaml`、`bookmarks.platform` 列、`shared/config.py::ENGINE_DEFAULTS`。
- **Git**：中文提交消息；一个方面一条 commit；**禁止 `git add -A`**（显式列文件）；`dev` 分支提交已授权，**不推送**（`git push` 一律不执行）。
- **提交写法（必须照做，避免中文被吞）**：提交消息一律经文件传入，例如
  `$msg = Join-Path $env:TEMP 'nd-msg.txt'; [IO.File]::WriteAllText($msg, 'fix: …', (New-Object Text.UTF8Encoding($false))); git commit -F $msg; Remove-Item $msg -Force`。
  **不要**用 `git commit -m "中文…"`。各任务的提交步骤只给出 `git add` 文件清单与该条提交的消息文本。
- **前端任务无自动化测试**：spec §5 明确**不引入**前端测试框架；Task 2 的验收判据是 `npx tsc --noEmit --project tsconfig.app.json` **0 错** + `npm run build` **EXIT 0**（不做人工 UI 验证）。
- **本机环境**：全局 `python`（3.10.11，已装 pytest 9.1.1 + 项目依赖）可直接跑测试；`frontend/node_modules` 已存在；**无 `.venv`**，不要试图激活虚拟环境。
- 每个任务的验证命令都在仓库根 `D:\Linux\novel-downloader\novel-downloader` 下执行。

---

## 文件结构

| 文件 | 动作 | 职责 |
|---|---|---|
| `backend/services/source_guard.py` | 创建 | `require_known_source(source_name)`：HTTP 边界的唯一书源校验点（未知 → 404） |
| `backend/routers/download.py` | 修改 | `_require_source` 接入校验；`search` 单源分支补校验 |
| `backend/routers/config.py` | 修改 | `GET/PUT /sources/{source_name}` 接入校验 |
| `backend/services/source_guard.py` → `tests/test_backend_source_guard.py` | 创建 | 未知源 404 的 7 条用例 |
| `frontend/src/features/sources/sourceConfigForm.tsx` | 创建 | UI 原子 + `MODE_META`/`CAP_LABELS`/`ENGINE_FIELDS` + `SourceConfigEditor`（唯一来源） |
| `frontend/src/features/sources/SourcesPage.tsx` | 修改 | 删本地重复定义，改 import；移除局部 invalidate |
| `frontend/src/features/settings/SettingsPage.tsx` | 修改 | 删本地重复定义，改 import；`SourceSection` 复用 `SourceConfigEditor` |
| `frontend/src/hooks/index.ts` | 修改 | `useSaveSourceConfig` 成功时同时失效 `["source-config", source]` + `["sources"]` |
| `cli/core.py` | 修改 | `_get_engine`/`_make_engines` 增 `options_hook` 注入 |
| `cli/main.py` | 修改 | 抽 `_apply_export_options`；`cmd_download`/`cmd_info` 改用多 mode 引擎；脚手架 `common` 用 `mode_defaults()` |
| `shared/config.py` | 修改 | 新增 `mode_defaults(mode)`（api 段从 `APIOptions` 派生，**不动 `ENGINE_DEFAULTS`**） |
| `tests/test_cli_engine_modes.py` | 创建 | CLI 按 mode 建引擎 + hook 生效 |
| `tests/test_cli_config.py` | 重命名（原 `test_cli_variant.py`） | 内容不变 |
| `tests/test_cli_dev_new_source.py` | 重命名（原 `test_cli_dev_new_variant.py`） | 内容 + 脚手架 `common` 断言 |
| `docs/source-plugin.md`、`docs/project/overview.md`、`docs/README.md`、`docs/project/updates.md`、`docs/session-prompt.md`、`CHANGELOG.md` | 修改 | 残留修正与追平 |
| `D:\Linux\novel-downloader\docs\*`（外层，非 git） | 迁移后清空为指针 | 8 个独有文档先迁入核心 `docs/` |
| `.reasonix/skills/session-init/SKILL.md`（外层，非 git） | 修改 | 读取路径改指核心 `docs/` |

任务依赖：T1/T2/T3/T4 相互独立；**T6 必须在 T7 之前**（迁入提交完成才能删外层副本）；T5 独立。

---

## Task 1: 后端未知书源统一 404

**Files:**
- Create: `backend/services/source_guard.py`
- Modify: `backend/routers/download.py:17-27`（import 区 + `_require_source`）、`backend/routers/download.py:60-62`（`search` 单源分支）
- Modify: `backend/routers/config.py:3-8`（import）、`:84-96`（GET）、`:99-105`（PUT）
- Test: `tests/test_backend_source_guard.py`（新建）

**Interfaces:**
- Produces: `backend.services.source_guard.require_known_source(source_name: str) -> str`（未知 → `fastapi.HTTPException(404, f"未知书源: {source_name}")`；已知 → 原样返回）
- Consumes: `novelbase.source.list_sources() -> list[str]`

- [x] **Step 1: 写失败测试**

新建 `tests/test_backend_source_guard.py`：

```python
"""未知 source_name 的 HTTP 边界校验：所有按 source_name 取参的入口一律 404。

core 层（`capabilities()` / `merged_source_config()`）对未知源返回空值是宽容语义，
404 只在 HTTP 边界产生——本文件锁定该边界。
"""
import asyncio

import pytest
from fastapi import HTTPException

from backend.routers import config as cfg
from backend.routers import download as dl
from backend.schemas import FetchMetaRequest
from backend.services import source_guard

_KNOWN = "92xs-requests-default"


def _only_known(monkeypatch):
    """把校验用的 list_sources 收窄为单一已知源。"""
    monkeypatch.setattr(source_guard, "list_sources", lambda: [_KNOWN])


def test_known_source_passes(monkeypatch):
    _only_known(monkeypatch)
    assert source_guard.require_known_source(_KNOWN) == _KNOWN


def test_unknown_source_raises_404(monkeypatch):
    _only_known(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        source_guard.require_known_source("nope-default")
    assert ei.value.status_code == 404
    assert "nope-default" in ei.value.detail


def test_config_get_unknown_source_404(monkeypatch):
    _only_known(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(cfg.get_source_config("nope-default"))
    assert ei.value.status_code == 404


def test_config_put_unknown_source_404(monkeypatch):
    """PUT 不得凭空创建 sites/unknown.yaml。"""
    _only_known(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(cfg.save_source_config("nope-default", {"enabled": True}))
    assert ei.value.status_code == 404


def test_search_single_unknown_source_404(monkeypatch):
    _only_known(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.search_novels(query="关键字", source="nope-default"))
    assert ei.value.status_code == 404


def test_search_url_unknown_source_404(monkeypatch):
    _only_known(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.search_novels(query="https://example.com/book/1", source="nope-default"))
    assert ei.value.status_code == 404


def test_novel_unknown_source_404(monkeypatch):
    _only_known(monkeypatch)
    body = FetchMetaRequest(url="https://example.com/book/1")
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.resolve_meta_route(body, source="nope-default"))
    assert ei.value.status_code == 404
```

- [x] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_backend_source_guard.py -q`
Expected: collection error / FAIL —— `ModuleNotFoundError: No module named 'backend.services.source_guard'`

- [x] **Step 3: 实现 `source_guard`**

新建 `backend/services/source_guard.py`：

```python
"""按 source_name 取参的 HTTP 边界校验。

core 层对未知书源是宽容语义（`novelbase.source.capabilities()` 与
`shared.config.merged_source_config()` 都返回 `{}`），但 HTTP 入口不应把
「书源名写错」当成空配置继续跑（`is_source_enabled()` 会 `KeyError` → 500）。
本模块是**唯一**校验点，避免各路由各写一份。
"""

from fastapi import HTTPException

from novelbase.source import list_sources


def require_known_source(source_name: str) -> str:
    """书源名必须存在（`list_sources()`），否则 404。"""
    if source_name not in list_sources():
        raise HTTPException(404, f"未知书源: {source_name}")
    return source_name
```

- [x] **Step 4: 接入 download 路由**

`backend/routers/download.py` import 区（`:14` 之后）加一行：

```python
from backend.services.source_guard import require_known_source
```

`_require_source`（`:23-27`）改为：

```python
def _require_source(source: str | None, url: str) -> str:
    """URL 无法自动推断书源（core 已删 platform_from_url）——需用户显式指定 source。"""
    if not source:
        raise HTTPException(400, f"无法自动识别书源 URL，请显式指定 source（书源名）: {url}")
    return require_known_source(source)
```

`search_novels` 的单源关键字分支（`:60-62`）改为：

```python
    if source:
        source_name = require_known_source(source)
        try:
            results = await search([source_name], query, _engines_for(source_name), page=page)
        except FeatureNotSupportedError as e:
        # 该书源/MODE 组合不支持搜索（如 qidian requests）→ 400 友好提示，而非 500
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(500, str(e))
```

> 注：`_require_source` 已覆盖 URL 分支、`/novel`、`/novel/{id}`、`/novel/{id}/chapters`、`/novel/{id}/chapter`；上面这处是 spec §4.1「所有按 source_name 取参的路由」里**唯一不经过 `_require_source`** 的入口。

- [x] **Step 5: 接入 config 路由**

`backend/routers/config.py` 的 `get_source_config`（`:84-96`）与 `save_source_config`（`:99-105`）各在函数体首行加校验：

```python
@router.get("/sources/{source_name}")
async def get_source_config(source_name: str):
    """三层合并后的书源配置 + 启用状态 + 能力映射。

    形状：`{source_name, enabled, capabilities: {cap: mode}, config: {cap: {…完整合并字段…}}}`。
    `config[cap]` 含 mode（恒取书源声明），`enabled` 走用户层顶层 `enabled` → 出厂值。
    """
    require_known_source(source_name)
    return {
        "source_name": source_name,
        "enabled": config_service.is_source_enabled(source_name),
        "capabilities": capabilities(source_name),
        "config": config_service.merged_source_config(source_name),
    }


@router.put("/sources/{source_name}")
async def save_source_config(source_name: str, body: dict):
    """只写用户层 `sites/{source_name}.yaml`：顶层 `enabled` + 逐能力段 `deep_merge`。

    不把三层合并后的全量写回（否则用户层被灌满出厂/系统默认值）。
    """
    require_known_source(source_name)
    path = config_service.CONFIG_DIR / "sites" / f"{source_name}.yaml"
    ...（其余不动）
```

并在 `backend/routers/config.py:6` 之后加：

```python
from backend.services.source_guard import require_known_source
```

- [x] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_backend_source_guard.py tests/test_backend_download_routes.py -q`
Expected: 全绿（新增 7 例 + 既有 download 路由用例全过）

> 既有 `test_backend_download_routes.py::test_search_single_source_binds_engine`（`:67-79`）用的 `source="92xs-requests-default"` 是**真实书源名**，`list_sources()` 能在默认环境命中，故不受 404 校验影响。若该用例因环境差异（如 `NLD_PRIVATE_SOURCES` 指向别处）失败，**在用例内** monkeypatch `source_guard.list_sources` 返回该名——**不要**放宽 `require_known_source`。

- [x] **Step 7: 全量回归**

Run: `python -m pytest tests -q`
Expected: `389 passed, 1 skipped` + 新增 7 例 = **396 passed, 1 skipped, 0 failed**

- [x] **Step 8: 提交**

```powershell
cd D:\Linux\novel-downloader\novel-downloader
git add backend/services/source_guard.py backend/routers/download.py backend/routers/config.py tests/test_backend_source_guard.py
# 提交消息（中文，用 -F 传文件避免引号吞中文）：
# fix: 未知 source_name 在 HTTP 边界统一返回 404
```

---

## Task 2: 前端共享书源配置组件 + `enabled` 双向失效

**Files:**
- Create: `frontend/src/features/sources/sourceConfigForm.tsx`
- Modify: `frontend/src/features/sources/SourcesPage.tsx`（删 `:9-117`、改 import、移除 `:195-197` local invalidate）
- Modify: `frontend/src/features/settings/SettingsPage.tsx`（删 `:15-142`、改 import、`SourceSection:145-237` 收缩）
- Modify: `frontend/src/hooks/index.ts`（`useSaveSourceConfig`）
- Test: 无前端测试框架 —— 以 `tsc --noEmit`（0 错）+ `npm run build`（EXIT 0）为判据（spec §4.2）

**Interfaces:**
- Produces（供两页 import）：
  - 组件：`Row`、`Toggle`、`Select`、`Num`、`TextField`、`Range`、`Section`、`SourceConfigEditor`
  - 常量/类型：`MODE_META`、`CAP_LABELS`、`ENGINE_FIELDS`、`EngineField`
  - `SourceConfigEditor({ name }: { name: string })` —— 自取数据（`useSourceConfig`）、自写（`useSaveSourceConfig`），渲染逐能力段表单
- Consumes: `@/hooks/index` 的 `useSourceConfig`、`useSaveSourceConfig`

- [x] **Step 1: 创建共享文件**

新建 `frontend/src/features/sources/sourceConfigForm.tsx`（内容 = `SourcesPage.tsx:9-117` 的原子与常量搬移 + `SourceConfigEditor`，`Section`/`MODE_META` 的 icon 类型统一为 `LucideIcon`，`MODE_META` 取带 `desc` 的版本）：

```tsx
/** 书源配置表单的共享实现：UI 原子 + 能力字段元数据 + 逐能力段编辑器。
 *
 * 唯一来源——`SourcesPage`（书源管理页）与 `SettingsPage`（设置页书源段）都从这里 import，
 * 避免两份逐字重复的实现漂移。
 */
import {useEffect, useState} from "react";
import type {LucideIcon} from "lucide-react";
import {Globe, Monitor, Zap} from "lucide-react";
import {useSaveSourceConfig, useSourceConfig} from "@/hooks/index";

export function Row({ label, desc, children }: { label: string; desc?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <div className="flex flex-col gap-0.5 min-w-0">
        <span className="text-xs font-medium text-slate-700 dark:text-slate-300">{label}</span>
        {desc && <span className="text-[11px] text-slate-400 dark:text-slate-500">{desc}</span>}
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

export function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!checked)}
      className={`relative h-5 w-9 rounded-full transition-colors duration-200 ${checked ? "bg-indigo-500" : "bg-slate-300 dark:bg-slate-600"}`}>
      <span className={`absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-all duration-200 ${checked ? "translate-x-4" : "translate-x-0"}`} />
    </button>
  );
}

export function Select({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <select value={value} onChange={e => onChange(e.target.value)}
      className="rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2.5 py-1.5 text-xs text-slate-700 outline-none appearance-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30">
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

export function Num({ value, onChange, min, max, step = 1, unit }: { value: number; onChange: (v: number) => void; min?: number; max?: number; step?: number; unit?: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <input type="number" value={value} onChange={e => onChange(Number(e.target.value))} min={min} max={max} step={step}
        className="w-16 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
      {unit && <span className="text-[11px] text-slate-400">{unit}</span>}
    </div>
  );
}

export function TextField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [local, setLocal] = useState(value);
  useEffect(() => { setLocal(value); }, [value]);
  return (
    <input type="text" value={local} onChange={e => setLocal(e.target.value)}
      onBlur={() => { if (local !== value) onChange(local); }}
      onKeyDown={e => { if (e.key === "Enter") { if (local !== value) onChange(local); (e.target as HTMLInputElement).blur(); } }}
      className="w-40 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2.5 py-1.5 text-xs text-slate-700 outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
  );
}

export function Range({ value, onChange, min, max, left, right }: { value: number; onChange: (v: number) => void; min: number; max: number; left: string; right: string }) {
  const pct = ((value - min) / (max - min)) * 100;
  return (
    <div className="flex flex-col gap-0.5 w-full max-w-[200px] group">
      <div className="relative h-4">
        <span className="absolute text-[11px] font-semibold text-indigo-500 tabular-nums -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity" style={{ left: `${pct}%` }}>{value}</span>
      </div>
      <input type="range" min={min} max={max} value={value} onChange={e => onChange(Number(e.target.value))}
        className="w-full h-8 appearance-none bg-transparent cursor-pointer
          [&::-webkit-slider-runnable-track]:h-1.5 [&::-webkit-slider-runnable-track]:rounded-full [&::-webkit-slider-runnable-track]:bg-slate-200 dark:[&::-webkit-slider-runnable-track]:bg-slate-700
          [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-indigo-500 [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:-mt-[5px]" />
      <div className="flex justify-between text-[10px] text-slate-400">
        <span>{left}</span>
        <span>{right}</span>
      </div>
    </div>
  );
}

export function Section({ icon: Icon, title, children }: { icon: LucideIcon; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-white/20 bg-white/80 backdrop-blur-xl shadow-card overflow-hidden dark:bg-slate-900/80 dark:border-slate-700/30">
      <div className="flex items-center gap-2.5 border-b border-white/10 px-5 py-3 dark:border-slate-700/30">
        <Icon className="h-4 w-4 text-indigo-500" strokeWidth={1.5} />
        <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">{title}</h3>
      </div>
      <div className="px-5 py-2 divide-y divide-slate-100 dark:divide-slate-800/50">{children}</div>
    </section>
  );
}

export const MODE_META: Record<string, { label: string; icon: LucideIcon; desc: string }> = {
  browser: { label: "Browser", icon: Monitor, desc: "模拟浏览器，最稳定" },
  requests: { label: "Requests", icon: Globe, desc: "直接 HTTP，最快" },
  api: { label: "API", icon: Zap, desc: "第三方接口" },
};

export const CAP_LABELS: Record<string, string> = {
  search: "搜索",
  novel_info: "书籍信息",
  chapter_list: "章节列表",
  chapter_content: "章节内容",
};

export type EngineField = {
  label: string; desc?: string;
  type: "toggle" | "num" | "select" | "range-delay" | "text";
  key: string;
  opts?: { value: string; label: string }[];
  min?: number; max?: number; unit?: string;
};

export const ENGINE_FIELDS: Record<string, EngineField[]> = {
  browser: [
    { key: "headless", label: "无头模式", desc: "后台静默运行，不弹窗口", type: "toggle" },
    { key: "browser_type", label: "浏览器类型", type: "select", opts: [{ value: "chromium", label: "Chromium" }, { value: "firefox", label: "Firefox" }, { value: "webkit", label: "WebKit" }] },
    { key: "user_data_dir", label: "用户数据目录", desc: "保存登录态和缓存", type: "text" },
    { key: "delay", label: "请求延迟", desc: "两章之间随机等待", type: "range-delay", min: 0, max: 30, unit: "秒" },
    { key: "timeout", label: "超时", desc: "单次请求最长等待", type: "num", min: 5, max: 120, unit: "秒" },
    { key: "retry_times", label: "重试次数", type: "num", min: 0, max: 10 },
    { key: "backoff_factor", label: "退避因子", desc: "重试间隔倍增系数", type: "num", min: 1, max: 10 },
  ],
  requests: [
    { key: "headers", label: "请求头", desc: "JSON 格式，如 {\"Cookie\": \"…\"}", type: "text" },
    { key: "delay", label: "请求延迟", desc: "两章之间随机等待", type: "range-delay", min: 0, max: 30, unit: "秒" },
    { key: "timeout", label: "超时", desc: "单次请求最长等待", type: "num", min: 5, max: 120, unit: "秒" },
    { key: "retry_times", label: "重试次数", type: "num", min: 0, max: 10 },
    { key: "backoff_factor", label: "退避因子", desc: "重试间隔倍增系数", type: "num", min: 1, max: 10 },
  ],
  api: [
    { key: "key", label: "API Key", type: "text" },
    { key: "delay", label: "请求延迟", desc: "两章之间随机等待", type: "range-delay", min: 0, max: 30, unit: "秒" },
    { key: "timeout", label: "超时", desc: "单次请求最长等待", type: "num", min: 5, max: 120, unit: "秒" },
    { key: "retry_times", label: "重试次数", type: "num", min: 0, max: 10 },
    { key: "backoff_factor", label: "退避因子", desc: "重试间隔倍增系数", type: "num", min: 1, max: 10 },
  ],
};

/** 单个书源的逐能力段配置编辑器（数据走 useSourceConfig，写走 useSaveSourceConfig）。 */
export function SourceConfigEditor({ name }: { name: string }) {
  const { data: cfg } = useSourceConfig(name);
  const saveSource = useSaveSourceConfig(name);

  const caps = cfg?.capabilities ?? {};
  const merged = cfg?.config ?? {};

  const updateField = (cap: string, key: string, value: unknown) => {
    saveSource.mutate({ config: { [cap]: { [key]: value } } });
  };

  const renderField = (cap: string, f: EngineField) => {
    const val = (merged[cap] as unknown as Record<string, unknown> | undefined)?.[f.key];
    const set = (value: unknown) => updateField(cap, f.key, value);
    switch (f.type) {
      case "toggle":
        return <Toggle checked={!!val} onChange={v => set(v)} />;
      case "select":
        return <Select value={String(val ?? f.opts![0].value)} onChange={v => set(v)} options={f.opts!} />;
      case "num":
        return <Num value={Number(val) || 0} onChange={v => set(v)} min={f.min} max={f.max} unit={f.unit} />;
      case "text":
        return <TextField value={String(val ?? "")} onChange={v => set(v)} />;
      case "range-delay":
        return (
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <input type="number" value={(val as number[])?.[0] ?? 3} onChange={e => set([Number(e.target.value), (val as number[])?.[1] ?? 5])} min={f.min} max={f.max}
              className="w-14 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
            <span>~</span>
            <input type="number" value={(val as number[])?.[1] ?? 5} onChange={e => set([(val as number[])?.[0] ?? 3, Number(e.target.value)])} min={f.min} max={f.max}
              className="w-14 rounded-lg border border-white/20 bg-white/50 backdrop-blur-sm px-2 py-1.5 text-xs text-slate-700 text-right outline-none dark:bg-slate-800/50 dark:text-slate-300 dark:border-slate-600/30" />
            <span className="text-[11px] text-slate-400">{f.unit}</span>
          </div>
        );
    }
  };

  if (!cfg) return <div className="py-2 text-xs text-slate-400">加载中…</div>;

  return (
    <div className="border-t border-slate-100 pt-2 pb-1 dark:border-slate-800/50">
      {Object.entries(caps).length === 0 && <p className="py-1 text-[11px] text-slate-400">该书源未声明能力</p>}
      {Object.entries(caps).map(([cap, mode]) => {
        const fields = ENGINE_FIELDS[mode] ?? [];
        const meta = MODE_META[mode];
        return (
          <div key={cap} className="border-t border-slate-100 first:border-t-0 dark:border-slate-800/50">
            <div className="flex items-center gap-2 py-1">
              <span className="text-xs font-medium text-slate-600 dark:text-slate-300">{CAP_LABELS[cap] ?? cap}</span>
              {meta && <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">{meta.label}</span>}
            </div>
            {fields.length === 0
              ? <p className="py-1 text-[11px] text-slate-400">该能力无可配置项</p>
              : fields.map(f => <Row key={f.key} label={f.label} desc={f.desc}>{renderField(cap, f)}</Row>)}
          </div>
        );
      })}
    </div>
  );
}
```

- [x] **Step 2: `SourcesPage.tsx` 改 import 并删重复**

`SourcesPage.tsx` 的 import 区改为：

```tsx
import {useEffect, useState} from "react";
import {ChevronDown, Layers} from "lucide-react";
import {cn} from "@/lib/utils";
import {useSaveSourceConfig, useSources} from "@/hooks/index";
import {CAP_LABELS, Section, SourceConfigEditor, Toggle} from "./sourceConfigForm";
```

删除 `:7-179` 的全部本地定义（注释行「展示小组件」+ `Row`/`Toggle`/`Select`/`Num`/`TextField`/`Section`/`MODE_META`/`CAP_LABELS`/`EngineField`/`ENGINE_FIELDS`/`SourceConfigEditor`），保留 `SourceRow`（现 `:182`）起的内容。

`SourceRow` 的 `toggleEnabled`（现 `:193-198`）去掉局部 invalidate（由 hook 统一）：

```tsx
  const toggleEnabled = (v: boolean) => {
    setEnabled(v); // 乐观更新，避免受控开关因 refetch 滞后回弹
    saveSource.mutate({ enabled: v });
  };
```

随之删除 `const qc = useQueryClient();`（现 `:183`）与 `useQueryClient` import（现 `:2`）。

- [x] **Step 3: `SettingsPage.tsx` 改 import 并复用编辑器**

`SettingsPage.tsx` import 区改为（删除 `:15-142` 的本地原子/常量定义）：

```tsx
import {useCallback, useEffect, useMemo, useState} from "react";
import {Bell, ChevronDown, Gauge, Layers, Package, Settings} from "lucide-react";
import {cn} from "@/lib/utils";
import {
    useFormatConfig,
    useSaveFormatConfig,
    useSaveGlobalConfig,
    useSourceConfig,
    useSources
} from "@/hooks/index";
import {useToast} from "@/components/toast-context";
import type {GlobalConfig} from "@/api/endpoints";
import {Num, Row, Section, Select, SourceConfigEditor, Toggle} from "@/features/sources/sourceConfigForm";
```

`SourceSection`（现 `:145-237`）收缩为：保留「书源选择器 + `enabled` 开关 + 折叠按钮」，能力段整块换成共享编辑器：

```tsx
/** 按书源编辑配置：选书源 → 启用开关 → 展开逐能力段表单（表单体复用共享 SourceConfigEditor）。 */
function SourceSection() {
  const { data: sources } = useSources();
  const sourceNames = useMemo(() => (sources ? Object.keys(sources) : []), [sources]);
  const [source, setSource] = useState("");
  const [open, setOpen] = useState(true);

  // 数据变化后保证有合法选中：无选择或已失效时回退到第一项
  useEffect(() => {
    if (!source && sourceNames.length > 0) setSource(sourceNames[0]);
    else if (source && !sourceNames.includes(source)) setSource(sourceNames[0] ?? "");
  }, [sourceNames, source]);

  const { data: cfg } = useSourceConfig(source || undefined);
  const saveSource = useSaveSourceConfig(source);

  return (
    <Section icon={Layers} title="书源配置">
      <div className="flex flex-wrap gap-1.5 py-2.5">
        {sourceNames.map(name => (
          <button key={name} onClick={() => setSource(name)}
            className={cn(
              "rounded-lg border px-3 py-1.5 text-xs font-medium transition-all",
              source === name
                ? "border-indigo-300 bg-indigo-50 text-indigo-600 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-400"
                : "border-white/20 bg-white/50 text-slate-500 hover:border-slate-200 dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-400",
            )}>
            {name}
          </button>
        ))}
        {sourceNames.length === 0 && <span className="py-2 text-xs text-slate-400">暂无书源</span>}
      </div>
      {cfg && source && (
        <div>
          <Row label="启用" desc="关闭后不参与并发搜索">
            <Toggle checked={cfg.enabled} onChange={v => saveSource.mutate({ enabled: v })} />
          </Row>
          <button onClick={() => setOpen(!open)} className="flex items-center gap-1.5 w-full py-2 text-xs font-medium text-slate-500 hover:text-slate-700 transition-colors dark:text-slate-400 dark:hover:text-slate-300">
            <ChevronDown className={`h-3.5 w-3.5 transition-transform duration-200 ${open ? "" : "-rotate-90"}`} strokeWidth={1.5} />
            {source} · 能力配置
          </button>
          {open && <SourceConfigEditor name={source} />}
        </div>
      )}
    </Section>
  );
}
```

> `useSaveSourceConfig` 仍在 `SettingsPage.tsx` 使用（`enabled` 开关），故 import 保留；`useSourceConfig` 同理（`cfg.enabled`）。`FormatsSection`（现 `:245-287`）继续用共享的 `Row`/`Select`/`Num`/`Toggle`/`Section`，无需改动（仅改由 import 提供）。

- [x] **Step 4: 修复 `useSaveSourceConfig` 双向失效**

`frontend/src/hooks/index.ts` 的 `useSaveSourceConfig` 改为：

```tsx
export function useSaveSourceConfig(source: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: { enabled?: boolean; config?: Record<string, Partial<EngineOptions>> }) =>
      saveSourceConfig(source, data),
    onSuccess: () => {
      // 两侧都要失效：设置页读 ["source-config", src]，书源管理页读 ["sources"]
      qc.invalidateQueries({ queryKey: ["source-config", source] });
      qc.invalidateQueries({ queryKey: ["sources"] });
    },
  });
}
```

- [x] **Step 5: 类型检查**

Run: `cd frontend; npx tsc --noEmit --project tsconfig.app.json`
Expected: **0 错**（若报 `Layers`/`Settings` 未使用或缺失 import，按报错调整 import 列表——`SourcesPage` 仍需要 `Layers`（`Section` icon 与列表用），`SettingsPage` 仍需要 `Settings`/`Layers`）

- [x] **Step 6: 构建**

Run: `cd frontend; npm run build`
Expected: `EXIT 0`

- [x] **Step 7: 人工核对重复已消除**

Run: `git diff --stat -- frontend/src/features/settings/SettingsPage.tsx frontend/src/features/sources/SourcesPage.tsx`
Expected: 两文件各减约 110 行；`ENGINE_FIELDS` 全仓只剩 `sourceConfigForm.tsx` 一处定义（`grep -rn "ENGINE_FIELDS" frontend/src` 只应命中共享文件 + 消费方 import）

- [x] **Step 8: 提交**

```powershell
git add frontend/src/features/sources/sourceConfigForm.tsx frontend/src/features/sources/SourcesPage.tsx frontend/src/features/settings/SettingsPage.tsx frontend/src/hooks/index.ts
# refactor(frontend): 抽出共享书源配置表单并修复 enabled 开关跨页失效
```

---

## Task 3: CLI 引擎按 mode 解析

**Files:**
- Modify: `cli/core.py:56-82`
- Modify: `cli/main.py:99-126`（`_get_engine` → 抽 `_apply_export_options`）、`:174-182`（`cmd_download`）、`:230-248`（`cmd_info`）
- Test: `tests/test_cli_engine_modes.py`（新建）
- Rename: `tests/test_cli_variant.py` → `tests/test_cli_config.py`（内容不变）

**Interfaces:**
- Produces:
  - `cli.core._get_engine(source_name: str, mode: str | None = None, options_hook=None)`（`options_hook: Callable[[Options], None] | None`）
  - `cli.core._make_engines(source_name: str, options_hook=None)` → `engines(mode)`，带 `engines.cache: dict[str, engine]`
  - `cli.main._apply_export_options(options) -> dict`（返回 `format_configs`，便于调用方复用）
- Consumes: `cli.config.build_options(source_name, mode)`、`novelbase.create_engine`

- [x] **Step 1: 写失败测试**

新建 `tests/test_cli_engine_modes.py`：

```python
"""CLI 引擎解析：按 mode 懒建并缓存，且 options_hook 对每个 mode 都生效。

背景：`cmd_download`/`cmd_info` 曾传 `lambda m: engine`（单引擎、忽略 mode），
跨能力 mode 不同的书源会错用首个 mode 的引擎。
"""
import cli.core


class _FakeOptions:
    def __init__(self, mode):
        self.mode = mode


def test_make_engines_builds_per_mode_and_applies_hook(monkeypatch):
    built: list[str] = []
    hooked: list[str] = []

    monkeypatch.setattr(cli.core, "build_options", lambda name, mode: _FakeOptions(mode))

    def fake_create(options):
        built.append(options.mode)
        return {"engine_for": options.mode}

    monkeypatch.setattr(cli.core, "create_engine", fake_create)

    engines = cli.core._make_engines("x-requests-default", options_hook=lambda o: hooked.append(o.mode))

    assert engines("requests") is engines("requests")   # 同 mode 复用缓存
    engines("browser")

    assert built == ["requests", "browser"]
    assert hooked == ["requests", "browser"]
    assert set(engines.cache) == {"requests", "browser"}


def test_get_engine_defaults_to_first_capability_mode(monkeypatch):
    monkeypatch.setattr(cli.core, "capabilities", lambda name: {"search": "browser", "chapter_content": "requests"})
    seen: list[str] = []

    class _Opt(_FakeOptions):
        pass

    monkeypatch.setattr(cli.core, "build_options", lambda name, mode: _Opt(mode))
    monkeypatch.setattr(cli.core, "create_engine", lambda options: seen.append(options.mode) or object())

    cli.core._get_engine("x-browser-default", None)
    assert seen == ["browser"]
```

> 若 `cli/core.py` 当前没有模块级 `capabilities` 名字（它在函数体内 `from novelbase.source import capabilities` 局部导入），则把 `test_get_engine_defaults_to_first_capability_mode` 写成 monkeypatch `cli.core.capabilities` **并**在实现里把局部导入提为模块级导入（Step 3 说明）。

- [x] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_cli_engine_modes.py -q`
Expected: FAIL —— `TypeError: _make_engines() got an unexpected keyword argument 'options_hook'`

- [x] **Step 3: 实现 `cli/core.py`**

`cli/core.py` 的 `_make_engines` / `_get_engine`（`:56-82`）改为：

```python
def _make_engines(source_name: str, options_hook=None):
    """构造 engines(mode)->engine（按书源名懒建并缓存）。

    `options_hook(options)` 在 `create_engine` 之前调用——供 cli.main 注入导出配置装配
    （`cli.core` 不能反向 import `cli.main`，故用依赖注入）。

    缓存暴露为 `_engines.cache`，便于调用方在结束时 close 所有引擎。
    """
    cache: dict[str, object] = {}

    def _engines(mode: str):
        if mode not in cache:
            cache[mode] = _get_engine(source_name, mode, options_hook)
        return cache[mode]

    _engines.cache = cache  # type: ignore[attr-defined]
    return _engines


def _get_engine(source_name: str, mode: str | None = None, options_hook=None):
    """按书源名创建引擎；mode 缺省取书源首个能力声明的 mode。

    与 `cli.main._get_engine` 统一：配置来自 `shared.config` 的三层合并。
    """
    if mode is None:
        caps = capabilities(source_name)
        mode = next(iter(caps.values()), "browser")
    options = build_options(source_name, mode)
    if options_hook is not None:
        options_hook(options)
    return create_engine(options)
```

并在 `cli/core.py` 的 import 区（`:14` 后）加模块级导入，使 `capabilities` 可被 monkeypatch：

```python
from novelbase.source import capabilities
```

- [x] **Step 4: 实现 `cli/main.py`**

`cli/main.py` 的 `_get_engine`（`:99-126`）拆为两个函数：

```python
def _apply_export_options(options) -> dict:
    """把当前生效的导出格式配置装配到 Options（单格式模式），返回 format_configs 供复用。"""
    format_configs = load_format_configs()
    from novelbase.exporter import register_export_options
    _opt_cls_map = register_export_options()
    group = load_main_config().get("group", "default")
    active_format = next(iter(format_configs), None)  # 取第一个配置的格式
    fmt_cfg = format_configs.get(active_format, {}) if active_format else {}
    opt_cls = _opt_cls_map.get(active_format) if active_format else None
    if opt_cls and fmt_cfg:
        raw_path = fmt_cfg.get("output_path", "").replace("{group}", group)
        extra = {k: fmt_cfg[k] for k in (
            "encoding", "file_name_template", "css_style", "include_toc",
        ) if k in fmt_cfg}
        opt = opt_cls(output_path=raw_path, **extra)
        options.set_export(opt)
    return format_configs


def _get_engine(source_name: str, mode: str | None = None):
    """按书源名创建 engine；mode 缺省取书源首个能力声明的 mode（含导出配置装配）。

    与 `cli.core._get_engine` 统一：配置来自 `cli.config.build_options(source_name, mode)`
    （shared.config 三层合并）。
    """
    if mode is None:
        from novelbase.source import capabilities
        mode = next(iter(capabilities(source_name).values()), "browser")
    options = build_options(source_name, mode)
    format_configs = _apply_export_options(options)
    return create_engine(options), format_configs
```

`cmd_download`（`:174-182`）改为：

```python
def cmd_download(args):
    source_name = args.source
    from cli.core import _do_download_inner, _make_engines

    format_configs = load_format_configs()
    engines = _make_engines(source_name, options_hook=_apply_export_options)
    try:
        asyncio.run(_do_download_inner(source_name, args.url, args.group, format_configs,
                                       max_workers=args.workers, engines=engines))
    finally:
        for eng in engines.cache.values():
            try:
                eng.close()
            except Exception:
                pass
```

`cmd_info`（`:230-248`）改为：

```python
def cmd_info(args):
    source_name = args.source
    from cli.core import _make_engines

    engines = _make_engines(source_name, options_hook=_apply_export_options)
    try:
        print(f"正在获取: {args.url}")
        novel = asyncio.run(resolve_meta(args.url, source_name, engines))
        print(f"\n  书名：{novel.title}")
        print(f"  作者：{novel.author}")
        print(f"  URL： {novel.url}")
        print(f"  ID：  {novel.id}")
        print(f"  章节：{len(novel.chapters)}/{novel.serial} 章")
        print(f"  字数：{novel.count or '未知'}")
        tags_str = "、".join(novel.tags) if novel.tags else ""
        print(f"  标签：{tags_str}")
        print(f"  简介：{novel.description}")
        if novel.cover and novel.cover.image_format:
            print(f"  封面：{novel.cover.image_format} ({len(novel.cover.raw_data)} bytes)")
    finally:
        for eng in engines.cache.values():
            try:
                eng.close()
            except Exception:
                pass
```

- [x] **Step 5: 运行测试**

Run: `python -m pytest tests/test_cli_engine_modes.py tests/test_interactive_cli.py tests/test_cli_storage.py -q`
Expected: 全绿

- [x] **Step 6: CLI 冒烟（真实配置路径）**

Run: `python cli.py sources list`
Expected: 正常输出书源列表（不抛异常）

- [x] **Step 7: 重命名测试文件**

```powershell
git mv tests/test_cli_variant.py tests/test_cli_config.py
```

- [x] **Step 8: 全量回归**

Run: `python -m pytest tests -q`
Expected: `0 failed`

- [x] **Step 9: 提交**

```powershell
git add cli/core.py cli/main.py tests/test_cli_engine_modes.py tests/test_cli_config.py
# fix(cli): 引擎按 mode 懒建（options_hook 注入导出装配），info/download 不再共用单引擎
```

---

## Task 4: 脚手架 `source.json` 与出厂默认同源

**Files:**
- Modify: `shared/config.py`（新增 `mode_defaults`）
- Modify: `cli/main.py:365-389`（`_scaffold_source`）
- Test: `tests/test_cli_dev_new_source.py`（由 `tests/test_cli_dev_new_variant.py` 重命名 + 补断言）

**Interfaces:**
- Produces: `shared.config.mode_defaults(mode: str) -> dict`（该 mode 的出厂默认字段；api 段由 `APIOptions` dataclass 默认派生）
- Consumes: `shared.config.ENGINE_DEFAULTS`、`novelbase.core.options.APIOptions`

- [x] **Step 1: 重命名测试文件并补失败断言**

```powershell
git mv tests/test_cli_dev_new_variant.py tests/test_cli_dev_new_source.py
```

在 `tests/test_cli_dev_new_source.py` 的 `test_new_source_manifest_valid` 之后新增（沿用该文件既有 helper `_setup(monkeypatch, tmp_path) -> (root, cfg_dir)`）：

```python
def test_new_source_common_includes_factory_defaults(monkeypatch, tmp_path):
    """脚手架 common 必须与真实书源一致：除 mode 外带上该 mode 的出厂默认字段。"""
    root, _ = _setup(monkeypatch, tmp_path)
    cli.main._scaffold_source("demo-requests-default", ["requests"])
    common = json.loads(
        (root / "demo_requests_default" / "source.json").read_text(encoding="utf-8")
    )["common"]
    assert common["mode"] == "requests"
    for key in ("timeout", "retry_times", "backoff_factor", "delay",
                "headers", "cookies", "proxies"):
        assert key in common, key
    # 空值须与真实书源字面同构（None → {}/""）
    assert common["cookies"] == {}
    assert common["proxies"] == {}
    assert isinstance(common["headers"], dict) and common["headers"]


def test_new_source_api_common_includes_key_and_params(monkeypatch, tmp_path):
    """api 的出厂默认不在 ENGINE_DEFAULTS（空 dict），须由 APIOptions 派生。"""
    root, _ = _setup(monkeypatch, tmp_path)
    cli.main._scaffold_source("demo-api-rain", ["api"])
    common = json.loads(
        (root / "demo_api_rain" / "source.json").read_text(encoding="utf-8")
    )["common"]
    assert common["mode"] == "api"
    for key in ("timeout", "retry_times", "backoff_factor", "delay", "key", "params"):
        assert key in common, key
    assert common["key"] == ""
    assert common["params"] == {}


def test_new_source_browser_common_blank_values_match_real_sources(monkeypatch, tmp_path):
    """dataclass 的 None 默认须规范化为真实书源用的 ""/{}/[]（用户裁决：spec §4.3(b) 优先）。"""
    root, _ = _setup(monkeypatch, tmp_path)
    cli.main._scaffold_source("demo-browser-default", ["browser"])
    common = json.loads(
        (root / "demo_browser_default" / "source.json").read_text(encoding="utf-8")
    )["common"]
    assert common["user_data_dir"] == ""
    assert common["viewport"] == {}
    assert common["extra_args"] == []
    assert common["browser_type"] == "chromium"
```

> 字段白名单已由 `novelbase/sources/manifest.py:16-22` 的 `MODE_FIELDS` 锁定，且它与三个 Options dataclass 字段一一对应——因此 `mode_defaults()` 产出的 `common` 必然通过 `load_manifest()` 校验（`test_new_source_manifest_valid` 保持绿）。

- [x] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_cli_dev_new_source.py -q`
Expected: 新增 2 例 FAIL（`KeyError: 'timeout'` / `'key'`）

- [x] **Step 3: 实现 `mode_defaults`**

`shared/config.py` 在 `ENGINE_DEFAULTS` 定义之后新增：

```python
# dataclass 默认用 None 表示「空」，而真实书源的 source.json 用 ""/{}/[]。
# 脚手架产物必须与真实书源字面同构（spec §4.3(b)），故按字段给出对应空值。
_BLANK_BY_FIELD: dict[str, object] = {
    "user_data_dir": "",
    "key": "",
    "viewport": {},
    "cookies": {},
    "proxies": {},
    "params": {},
    "extra_args": [],
}


def _normalize_blank(key: str, value):
    """dataclass 的 None 默认 → 真实 source.json 使用的空值（可变容器浅拷贝，避免共享）。"""
    if value is not None:
        return value
    blank = _BLANK_BY_FIELD.get(key)
    if isinstance(blank, dict):
        return dict(blank)
    if isinstance(blank, list):
        return list(blank)
    return blank


def mode_defaults(mode: str) -> dict:
    """该 mode 的出厂默认字段（系统默认层），供脚手架生成 `source.json.common`。

    `ENGINE_DEFAULTS["api"]` 是空 dict（api 的 Options 由 `set_api_options` 单独消费），
    脚手架需要 key/params——这里从 `APIOptions` 的 dataclass 默认派生，**不改
    `ENGINE_DEFAULTS`**（避免影响 `merged_source_config` 的三层合并结果）。
    """
    if mode == "api":
        from novelbase.core.options import APIOptions
        defaults: dict = _dataclass_defaults(APIOptions)
    else:
        defaults = dict(ENGINE_DEFAULTS.get(mode, {}))
    return {k: _normalize_blank(k, v) for k, v in defaults.items()}
```

- [x] **Step 4: 实现脚手架改动**

`cli/main.py` 的 `_scaffold_source`（`:382-387`）改为：

```python
    enabled = mode != "api"
    from shared.config import mode_defaults
    manifest = {
        "source_name": name,
        "enabled": enabled,
        "common": {"mode": mode, **mode_defaults(mode)},
        "default_config": {fn: {} for fn in _SCAFFOLD_FUNCTIONS},
    }
```

> `mode_defaults` 已把 dataclass 的 `None` 默认规范化为真实 `source.json` 使用的空值（`""`/`{}`/`[]`），`delay` 的 tuple 经 `json.dumps` 写成 `[3.0, 5.0]`——产物与现有 10 个书源 `source.json` 逐字同构（用户裁决：以 spec §4.3(b)「与真实书源一致」为准，而非保留 `null`）。
> 字段白名单由 `novelbase/sources/manifest.py:16-22` 的 `MODE_FIELDS` 锁定，且与三个 Options dataclass 字段一一对应，故 `load_manifest()` 校验必然通过。

- [x] **Step 5: 运行测试**

Run: `python -m pytest tests/test_cli_dev_new_source.py tests/test_source_manifest.py tests/test_site_config.py -q`
Expected: 全绿

- [x] **Step 6: 全量回归 + 硬约束检查**

Run: `python -m pytest tests -q`
Run: `git diff --stat -- novelbase/sources novelbase/core novelbase/models novelbase/utils`
Expected: `0 failed`；diff 为**空**

- [x] **Step 7: 提交**

```powershell
git add shared/config.py cli/main.py tests/test_cli_dev_new_source.py
# feat(cli): dev new-source 脚手架 common 与出厂默认同源（含 api 的 key/params）
```

---

## Task 5: 文档残留修正与追平

**Files:**
- Modify: `docs/source-plugin.md:1,70,107`
- Modify: `docs/project/overview.md:23,64`
- Modify: `docs/README.md:3`
- Modify: `docs/project/updates.md`（追加两段）
- Modify: `docs/session-prompt.md:56`
- Modify: `CHANGELOG.md`（`## Unreleased` 追加）
- 无测试（文档任务）；验证 = `Select-String` 断言残留词为 0 + `git status` 干净

- [x] **Step 1: 修 `docs/source-plugin.md`**

- 文件首行加标题与状态标注（若已有标题则在标题下方补一行）：

```markdown
> **状态：未实现的设想方案**（当前仓库无插件进程实现；`resolve()` 只从内置/私有源目录加载）。
> 文中 `browser` 模式引擎为 **Playwright**（2026-08-16 已替换 DrissionPage）。
```

- `:70` 的 `browser 模式引擎（DrissionPage Chromium 实例）` → `browser 模式引擎（Playwright Chromium 实例）`
- `:107` 的 `不含 DrissionPage/浏览器` → `不含 Playwright/浏览器`

- [x] **Step 2: 修 `docs/project/overview.md`**

- `:23` 的 `> **docs/ 在外层容器**（\`D:\Linux\novel-downloader\docs\`），被 .gitignore 忽略，不入版本库。` → `> **docs/ 随核心仓库入库**（\`novel-downloader/docs/\`）。外层容器 \`D:\Linux\novel-downloader\docs\` 仅存一份指向本目录的指针。`
- `:64` 的 `storage/            novels.db（SQLite，每本小说一个独立 .db 文件）` → `storage/novels/       SQLite，每本小说一个独立 <id>.db 文件（id = sha256(url)[:32]）`

- [x] **Step 3: 修 `docs/README.md:3`**

`外层容器 \`D:\Linux\novel-downloader\docs\`(非 git 仓库,被 .gitignore 忽略,不入版本库)。核心仓库在 \`D:\Linux\novel-downloader\novel-downloader\`。` →

`本文档目录随核心仓库入库（\`novel-downloader/docs/\`）。外层容器 \`D:\Linux\novel-downloader\docs\` 仅存一份指向本目录的指针。核心仓库根：\`D:\Linux\novel-downloader\novel-downloader\`。`

- [x] **Step 4: 追平 `docs/project/updates.md`**

文件末尾追加：

```markdown
---

## 2026-09-24 变更（Novel.id 改 sha256(url) + 书源扁平化 core）

- `Novel.id` 由各书源手工拼接平台前缀改为中心化生成 `sha256(url)[:32]`；库内 `meta.id` 存书源返回的 url 原样
- 书源目录扁平化：四层 `{platform}/{mode}/{variant}/` → 一层目录 + `source.json`（`source_name` / `enabled` / `common` / `default_config`）
- 退役 `platform` / `SHOW_NAME` / `HOSTS` / `NAME` / `variant` / `register_source()` / `platform_from_url()` / `canonical_book_url()` / `ID_PATTERN` 等符号；`novelbase/source.py` 只暴露 `list_sources` / `get_manifest` / `capabilities` / `resolve` / `resolve_book_url`
- 设计：`docs/superpowers/specs/2026-09-24-book-source-flattening-design.md`；计划：`docs/superpowers/plans/2026-09-24-source-flattening-core.md`

## 2026-09-25 变更（扁平化遗留改造 + 收尾）

- 契约收口 15 任务：backend / CLI / 前端 / 配置全部改到 `source_name` 维度（`--source` Query；`/download/sources` 新形状；`/config/sources/{name}` 三层合并；前端去 mode/variant 选择器 + 新增书源管理页 `/sources`）
- 删除失去基础的三个端点/入口：`POST /download/detect`、`/api/v2/engine*`、CLI `do_visit_site`
- 搜索历史改 `(source_name, keyword)` 唯一键；`enabled` 用户层覆盖落地为 `sites/{source_name}.yaml` 顶层
- 收尾：未知 `source_name` 统一 404、前端书源配置表单去重 + `enabled` 双向失效修复、CLI 引擎按 mode 解析、脚手架 `common` 与出厂默认同源、docs 位置归一
- 设计：`docs/superpowers/specs/2026-09-25-source-flattening-followup-design.md`、`docs/superpowers/specs/2026-09-25-flattening-closeout-design.md`
```

- [x] **Step 5: 更新 `docs/session-prompt.md` 的「仍待收口」段（`:56`）**

该段「**仍待收口**：① … ② … ③ … ④ …」改为：

```markdown
- **中间态收口状态**（2026-09-25 扁平化 followup + 收尾完成）：core 层遗留中间态**已全部收口**——`/api/v2/download/platform`、`/api/v2/download/detect`、`/api/v2/engine` 路由**已删除**；`source.json` 的 `enabled` **已有消费者**（`shared.config.enabled_source_names()`）；前端 mode/variant 两级选择器**已删除**（搜索改「已启用书源并发」，URL 解析改「手选书源」，书源管理页 `/sources`）。收尾阶段补齐：① 未知 `source_name` 在 **HTTP 边界统一 404**（`backend/services/source_guard.py` 唯一校验点，覆盖 `download` 与 `config/sources` 全部入口）；② 书源配置表单抽为 `frontend/src/features/sources/sourceConfigForm.tsx` 共享实现（`SettingsPage` / `SourcesPage` 复用），`useSaveSourceConfig` 同时失效 `["source-config", src]` 与 `["sources"]`；③ CLI `cmd_info` / `cmd_download` 引擎按 mode 懒建（不再共用单引擎）；④ `dev new-source` 脚手架 `source.json.common` 与出厂默认同源（`shared.config.mode_defaults()`）。**仍缺**（后续增强，非缺陷）：前端 URL **自动**匹配书源（core 无 `platform_from_url`，`source` 由用户手选）；重复 `source_name` 无实现层检测；`novel.extra["platform"]` 键名保留（值为 `source_name`，数据兼容）
```

- [x] **Step 6: 追加 `CHANGELOG.md` 的 `## Unreleased` 段**

在 `## Unreleased（书源扁平化收口）` 段的「### 变更」列表末尾追加一条编号项：

```markdown
8. **收尾补齐** — 未知 `source_name` 统一 404（`backend/services/source_guard.py`）；书源配置表单抽为前端共享组件并修复 `enabled` 开关跨页失效；CLI `info` / `download` 引擎按 mode 懒建；`dev new-source` 脚手架 `source.json.common` 与出厂默认同源；docs 归一（外层容器 `docs/` 仅存指针）
```

- [x] **Step 7: 验证残留清零**

Run（在仓库根）：
```powershell
Select-String -Path docs\source-plugin.md -Pattern 'DrissionPage'
```
Expected: 无输出（0 命中）

Run：
```powershell
Select-String -Path docs\README.md,docs\project\overview.md -Pattern '不入版本库'
```
Expected: 无输出

- [x] **Step 8: 提交**

```powershell
git add docs/source-plugin.md docs/project/overview.md docs/README.md docs/project/updates.md docs/session-prompt.md CHANGELOG.md
# docs: 修正扁平化后的残留描述并追平 updates/session-prompt/CHANGELOG
```

---

## Task 6: 外层 8 个独有文档迁入核心 `docs/`

**Files:**
- Create（迁移）: 核心 `docs/superpowers/plans/2026-08-22-browser-auto-reconnect.md`、`docs/superpowers/plans/2026-08-22-novel-id-hash.md`、`docs/superpowers/plans/2026-08-25-restore-interactive-cli.md`、`docs/superpowers/plans/2026-08-25-site-config-variant-nesting.md`、`docs/superpowers/specs/2026-08-22-browser-auto-reconnect-design.md`、`docs/superpowers/specs/2026-08-22-novel-id-hash-design.md`、`docs/superpowers/specs/2026-08-25-restore-interactive-cli-design.md`、`docs/superpowers/specs/2026-08-25-site-config-variant-nesting-design.md`
- 来源（只读，不删）: 外层 `D:\Linux\novel-downloader\docs\superpowers\...` 同路径

**Interfaces:**
- Produces: 核心 `docs/` 含上述 8 个文件（`git status` 可见 8 个 new file）
- 顺序约束：**本任务必须先于 Task 7 完成并提交**

- [x] **Step 1: 复制 8 个文件（外层 → 核心）**

```powershell
$outer = 'D:\Linux\novel-downloader\docs'
$core  = 'D:\Linux\novel-downloader\novel-downloader\docs'
$files = @(
  'superpowers\plans\2026-08-22-browser-auto-reconnect.md',
  'superpowers\plans\2026-08-22-novel-id-hash.md',
  'superpowers\plans\2026-08-25-restore-interactive-cli.md',
  'superpowers\plans\2026-08-25-site-config-variant-nesting.md',
  'superpowers\specs\2026-08-22-browser-auto-reconnect-design.md',
  'superpowers\specs\2026-08-22-novel-id-hash-design.md',
  'superpowers\specs\2026-08-25-restore-interactive-cli-design.md',
  'superpowers\specs\2026-08-25-site-config-variant-nesting-design.md'
)
foreach ($f in $files) {
  $src = Join-Path $outer $f
  $dst = Join-Path $core  $f
  New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
  Copy-Item -LiteralPath $src -Destination $dst -Force
}
```

- [x] **Step 2: 逐文件校验内容一致（8/8 相同 hash）**

```powershell
foreach ($f in $files) {
  $a = (Get-FileHash (Join-Path $outer $f)).Hash
  $b = (Get-FileHash (Join-Path $core  $f)).Hash
  if ($a -ne $b) { "MISMATCH $f" } else { "OK $f" }
}
```
Expected: 8 行 `OK`，无 `MISMATCH`

- [x] **Step 3: 提交（显式列 8 个文件，禁止 `git add -A`）**

```powershell
cd D:\Linux\novel-downloader\novel-downloader
git add docs/superpowers/plans/2026-08-22-browser-auto-reconnect.md `
        docs/superpowers/plans/2026-08-22-novel-id-hash.md `
        docs/superpowers/plans/2026-08-25-restore-interactive-cli.md `
        docs/superpowers/plans/2026-08-25-site-config-variant-nesting.md `
        docs/superpowers/specs/2026-08-22-browser-auto-reconnect-design.md `
        docs/superpowers/specs/2026-08-22-novel-id-hash-design.md `
        docs/superpowers/specs/2026-08-25-restore-interactive-cli-design.md `
        docs/superpowers/specs/2026-08-25-site-config-variant-nesting-design.md
# docs: 迁入外层容器独有的 8 个设计与计划留档
```

- [x] **Step 4: 确认入库**

Run: `git log -1 --stat`
Expected: 8 个文件全部为 `create mode`

---

## Task 7: 外层 `docs/` 指针化 + 会话入口改指 + 最终验收

**Files:**
- Modify: 外层 `D:\Linux\novel-downloader\docs\README.md`（重写为指针）
- Delete: 外层 `docs/` 下其余全部文件与空目录（非 git，操作**不可逆**）
- Modify: 外层 `.reasonix\skills\session-init\SKILL.md`（读取路径改指核心 `docs/`）

**Interfaces:**
- Consumes: Task 6 已提交的 8 个文件（确保核心 `docs/` 是超集）
- Produces: 外层 `docs/` 只剩 `README.md` 指针

- [x] **Step 1: 前置校验 —— 外层文件数 ⊂ 核心文件数（除下列 7 个已知过期同名文件）**

```powershell
$outer = 'D:\Linux\novel-downloader\docs'
$core  = 'D:\Linux\novel-downloader\novel-downloader\docs'
$o = Get-ChildItem $outer -Recurse -File | ForEach-Object { $_.FullName.Substring($outer.Length+1) }
$c = Get-ChildItem $core  -Recurse -File | ForEach-Object { $_.FullName.Substring($core.Length+1) }
$missing = $o | Where-Object { $_ -notin $c -and $_ -ne 'README.md' }
if ($missing) { "未迁移: "; $missing } else { "OK: 外层全部文件已在核心 docs/ 中" }
```
Expected: `OK: 外层全部文件已在核心 docs/ 中`（`project\*.md`、`session-prompt.md` 等 7 个同名文件用核心版；若此处报 `未迁移`，**停止**并回到 Task 6 迁移缺失文件）

- [x] **Step 2: 重写外层 `README.md` 为指针**

```markdown
# 本目录已废弃 —— 文档事实来源在核心仓库

**全部项目文档位于**：`D:\Linux\novel-downloader\novel-downloader\docs\`

- 会话入口：`novel-downloader/docs/session-prompt.md`（项目概述 + 关键约定）
- 文档导航：`novel-downloader/docs/README.md`

## 为什么只剩这一个文件

2026-09-25 收尾前，外层容器 `docs/`（非 git、被 .gitignore 忽略）与核心仓库 `docs/`（入库）
长期并存：外层是旧快照，会话从这里读到的契约已经过时（例如已删除的 `mode`/`variant` 体系、
`source.resolve(name, mode, function, variant?)` 旧签名），而真实契约早已在核心仓库更新。

现在文档全部归入核心仓库并纳入版本控制，外层独有留档也已迁入，本目录只保留这份指针。
`.reasonix/skills/session-init/SKILL.md` 已改为读取核心 `docs/`。

**不要再在此目录新增文档。**
```

- [x] **Step 3: 删除外层其余文件与空目录**

```powershell
$outer = 'D:\Linux\novel-downloader\docs'
Get-ChildItem $outer -Recurse -File | Where-Object { $_.FullName -ne (Join-Path $outer 'README.md') } | Remove-Item -Force
Get-ChildItem $outer -Recurse -Directory | Where-Object { -not (Get-ChildItem $_.FullName -Recurse -File) } | Sort-Object { $_.FullName.Length } -Descending | Remove-Item -Force
Get-ChildItem $outer -Recurse | Select-Object -ExpandProperty FullName
```
Expected: 只输出 `D:\Linux\novel-downloader\docs\README.md`

- [x] **Step 4: 改 `session-init` skill 的读取路径**

修改 `D:\Linux\novel-downloader\.reasonix\skills\session-init\SKILL.md`：

- 「### 步骤 1：读取项目文档」下的引言 `按以下顺序读取 \`docs/\` 目录下的文档（2026-08-02 已按主题分类编排）：` 改为
  `按以下顺序读取**核心仓库** \`novel-downloader/docs/\` 目录下的文档（2026-08-02 已按主题分类编排；外层容器 \`docs/\` 仅存指针，不再读取）：`
- 「### 注意事项」再加一条：`- 文档事实来源是核心仓库 \`novel-downloader/docs/\`，外层容器 \`docs/\` 只有指针文件`

- [x] **Step 5: 验证会话入口可读**

Run:
```powershell
Get-Content 'D:\Linux\novel-downloader\novel-downloader\docs\session-prompt.md' -TotalCount 8
```
Expected: 正常输出（核心仓库 `session-prompt.md` 可读，且含 2026-09-25 的约定）

- [x] **Step 6: 最终全量验收**

```powershell
cd D:\Linux\novel-downloader\novel-downloader
python -m pytest tests -q
git diff --stat -- novelbase/sources novelbase/core novelbase/models novelbase/utils
git status --short
```
Expected:
- pytest: **0 failed**（passed ≥ 396，1 skipped）
- 硬约束 diff：**空**（书源/核心/模型/工具零改动，`Novel.id` 的 url 逐字不变）
- `git status --short`：干净（无未提交残留）

Run:
```powershell
cd D:\Linux\novel-downloader\novel-downloader\frontend
npx tsc --noEmit --project tsconfig.app.json
npm run build
```
Expected: tsc 0 错；`npm run build` EXIT 0

- [x] **Step 7: 确认未推送（遵守决策 D4）**

Run: `git log --oneline origin/dev..dev | Measure-Object -Line`
Expected: 计数 ≥ 54（原有 53 + 本计划新增提交）；**不执行** `git push`

---

## 自审记录

### ① spec 覆盖检查表

| spec 章节 | 任务 | 覆盖 |
|---|---|---|
| §4.1 后端统一 404 | Task 1 | ✅（含 `search` 单源分支——spec 文字未列，按「所有按 source_name 取参的路由」补入） |
| §4.2 前端共享组件 + 失效修复 | Task 2 | ✅（含 `SourcesPage:196` 局部 invalidate 移除，按 spec 明文「移除」） |
| §4.3(a) CLI 引擎按 mode | Task 3 | ✅ |
| §4.3(b) 脚手架 common 同源 | Task 4 | ✅（选择 spec §7.2 允许的「只在脚手架补齐、不动 `ENGINE_DEFAULTS`」分支，理由写在该任务 Step 3 注释） |
| §4.3(c) 测试改名 | Task 3（`test_cli_config.py`）、Task 4（`test_cli_dev_new_source.py`） | ✅ |
| §4.3(d) 补测试 | Task 3 Step 1、Task 4 Step 1 | ✅ |
| §4.4 文档残留与追平 | Task 5 | ✅（含 `README.md` / `overview.md` / `source-plugin.md` / `updates.md` / `session-prompt.md` / `CHANGELOG.md` 六处） |
| §4.5 位置归一 | Task 6（迁入）+ Task 7（指针化 + skill 改指） | ✅（顺序约束已写进任务依赖） |
| §6 验收口径 | 每任务末 + Task 7 Step 6 | ✅ |
| §7 风险与硬约束 | Global Constraints + Task 3/4 Step 的硬约束 diff 检查 | ✅ |

### ② 占位符扫描

无 `TBD` / `TODO` / 「稍后补」；Task 4 Step 1 的 helper 名 `_scaffold` / `_source_dir` 标注了「先读该文件再落笔，保持同风格」，执行时须与既有用例一致（该文件已存在且内容已是 `dev new-source` 契约）。

### ③ 类型/命名一致性

- `require_known_source`（Task 1）在 `download.py` / `config.py` 两处同名同签名。
- 共享组件导出名 `SourceConfigEditor` / `MODE_META` / `CAP_LABELS` / `ENGINE_FIELDS` / `EngineField` 在 Task 2 两个消费方引用一致。
- `options_hook` 在 `cli/core.py`（`_get_engine` / `_make_engines`）与 `cli/main.py`（`_apply_export_options` 传入）签名一致；`_apply_export_options` 返回 `format_configs` 以替代原 `_get_engine` 的第二返回值。
- `mode_defaults(mode) -> dict`（Task 4）在 `shared/config.py` 定义、`cli/main.py` 消费，名字一致。

### ④ 已知顺序坑

- **T6 必须先于 T7**：迁入未提交就删外层副本 = 永久丢失 8 个留档（外层非 git）。
- **T1 与既有测试（已核实，非隐患）**：`test_backend_download_routes.py` 只有 5 个用例，其中唯一走单源分支的是 `test_search_single_source_binds_engine`，用的是**真实书源名** `"92xs-requests-default"`（`list_sources()` 能命中），其余用例走空 `source` 或 patch `enabled_source_names`/`get_cached_engine`，均不经过 `require_known_source` → Task 1 后既有用例保持绿。兜底修法已写在该任务 Step 6 的注里。
- **T2 的 tsc 增量**：删除本地球 `MODE_META` 后，`SourcesPage` 若仍引用 `Monitor`/`Globe`/`Zap` 会 `noUnusedLocals` 报错 → 按 Step 5 的提示调整 import。
- **T4 与 `test_site_config.py`**：`mode_defaults` 不改 `ENGINE_DEFAULTS`，故三层合并用例不受影响；若 Step 5 出现 `test_merged_source_config_*` 失败，说明误改了 `ENGINE_DEFAULTS`，须回退。

---

## 完成记录（2026-09-25）

| Task | 产出提交 |
|---|---|
| T1 后端未知书源统一 404 | `b9e2124` |
| T2 前端共享书源配置组件 + `enabled` 双向失效 | `cdeb592` |
| T3 CLI 引擎按 mode 解析 | `79f16c3`、`cdc7047` |
| T4 脚手架 `source.json` 与出厂默认同源 | `f9fda06`、`1e7a1a2` |
| T5 文档残留修正与追平 | `b6ca8a5`、`c8283f8`、`f830a91`、`3dbeb33`、`f770fe0` |
| T6 外层 8 个独有文档迁入核心 `docs/` | `27226b6` |
| T7 外层 `docs/` 指针化 + 会话入口改指 + 最终验收 | `d6cb69a`（外层 `README.md` 指针为非 git 文件） |
| 补做（计划外）：`build/` 误伤 `docs/build/`，4 个构建文档首次入库 | `2c93bef` |

> T5 与 T7 的部分收尾由子 Agent 三轮只读复核后补全（详见 `docs/project/updates.md` 与各提交消息）。
> 外层容器旧 `docs/` 副本（39 文件）已并入核心仓库并删除，仅留 `README.md` 指针。
