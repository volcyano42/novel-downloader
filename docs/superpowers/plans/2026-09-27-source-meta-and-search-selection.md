# 书源元信息（分组/别名）与按选择搜索 —— 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让书源以「别名 + 分组」呈现并可编辑，彻底移除 `enabled` 概念，搜索时由用户勾选参与的书源（默认全选）。

**Architecture:** 元信息（`source_group` / `source_alias`）只存**用户层** `sites/{source_name}.yaml` 顶层，出厂 `source.json` 可提供默认值，读取统一走 `shared/config.py` 的新入口（`source_group()` / `source_alias()` / `display_name()`）。`enabled` 从 core 契约、配置、模板、脚手架、后端、CLI、前端、测试中完整删除；「默认参与集」由 `enabled ∩ available` 变为 `default_source_names()` = 全部**可用**源。搜索新增 `sources=a,b,c` 查询参数，前端标题 tab 用它传勾选集合。

**Tech Stack:** Python 3.10（core/`shared`/FastAPI/CLI）、React 19 + TypeScript + TanStack Query + Tailwind + shadcn/ui、pytest、oxlint。

**Spec:** `docs/superpowers/specs/2026-09-27-source-meta-and-search-selection-design.md`

## Global Constraints

- **不重命名 `source_name`**：它是全书源体系的唯一键（`source.json` / 公共 API / API 键 / `sites/{source_name}.yaml` 文件名 / `SearchResult.source_name`）。新字段一律带 `source_` 前缀。
- **`enabled` 彻底删除**：`source.json` 与用户层都不再有；旧配置里的残留键**不读**、PUT 时清理；旧自定义 `source.json` 里的 `enabled` 因 manifest 对未知顶层字段宽容而被忽略，不得报错。
- **可用性过滤不得倒退**：`default_source_names()` 与前端选源列表都必须排除 `is_source_available()` 为假的源（Android 下 browser 源）。
- **搜索选择不持久化**：每次进入搜索页默认全选（spec D6）。
- **提交纪律**（仓库约定）：中文 commit 消息；一个方面一条 commit；**禁止 `git add -A`**（显式指定文件）；dev 分支可自动提交/推送。
- **测试基线**（2026-09-27，dev `e820704`）：`python -m pytest tests -q` = **499 passed, 0 failed**；前端 `cd frontend && npx tsc -b` = 0 错、`npm run lint` = 0 告警。每个任务结束时这两条都必须保持。
- **前端验证命令**：`npx tsc -b`（`tsconfig.json` 是 solution 风格，`tsc --noEmit` 会空转）。

## File Structure

**core / 配置层**
- `shared/config.py` — 元信息读取入口（`source_group` / `source_alias` / `display_name` / `default_source_names`）；删除 `is_source_enabled` / `enabled_source_names`
- `novelbase/sources/manifest.py` — `IDENTITY_FIELDS` 去掉 `enabled`；新增可选顶层字段类型校验
- `novelbase/sources/*/source.json`（10 个）— 删 `enabled`、加 `source_alias` / `source_group`
- `template/config/sites/*.yaml`（10 个）— 删 `enabled`

**后端**
- `backend/routers/download.py` — `/sources` 形状、搜索 `sources` 参数、默认集切换
- `backend/routers/config.py` — `/config/sources/{name}` 的 GET/PUT 元信息
- `backend/services/source_guard.py` — 仅 docstring 措辞

**CLI**
- `cli/main.py` — `cmd_search` 默认集、`cmd_source` 显示别名/分组、`dev new-source` 不写 `enabled`
- `cli/interactive.py` — 默认集、结果来源显示 `display_name`
- `cli/menus.py` — 删除启用开关菜单项

**前端**
- `frontend/src/api/endpoints.ts` — `SourceInfo` / `SourceOption` / `toSourceOptions` / `searchDownload`
- `frontend/src/hooks/index.ts` — `useSearch` 参数
- `frontend/src/features/sources/SourceAccordion.tsx` — 折叠条（别名/分组/去开关/并发数移走）
- `frontend/src/features/sources/sourceConfigForm.tsx` — 展开区（分组/别名/并发数输入）
- `frontend/src/features/bookshelf/SearchBar.tsx` — 标题 tab 双框、URL tab 分组单选
- `frontend/src/features/bookshelf/BookshelfPage.tsx` — 搜索参数、结果 tab 显示别名
- `frontend/src/features/detail/SourcePickerDialog.tsx` — 去掉「未启用」标注、显示别名

**测试**
- 新增 `tests/test_source_metadata.py`；改写 `tests/test_source_availability.py`、`tests/test_source_enabled.py`、`tests/test_backend_download_routes.py`、`tests/test_backend_config_routes.py`、`tests/test_cli_effective_mode.py`、`tests/test_interactive_cli.py`

**文档**
- `docs/session-prompt.md`、`docs/project/{sources,config,cli,updates}.md`、`CHANGELOG.md`

---

### Task 1: `shared` 层元信息读取与默认参与集

新增读取入口，**不动**旧函数（`is_source_enabled` / `enabled_source_names` 保留到 Task 6 删除），保证每一步都可独立验证。

**Files:**
- Modify: `shared/config.py`（在 `is_source_enabled()` 之后、`SOURCE_CONCURRENCY_DEFAULT` 之前插入新函数）
- Test: `tests/test_source_metadata.py`（新建）

**Interfaces:**
- Consumes: 现有 `_user_site_cfg(source_name)`、`is_source_available(source_name)`
- Produces: `source_group(source_name) -> str`、`source_alias(source_name) -> str`、`display_name(source_name) -> str`、`default_source_names() -> list[str]`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_source_metadata.py`：

```python
# -*- coding: utf-8 -*-
"""书源元信息（分组/别名）与默认参与集。"""
from shared import config as sc

BROWSER_CAPS = {"search": "browser", "novel_info": "browser",
                "chapter_list": "browser", "chapter_content": "browser"}
REQUESTS_CAPS = {"search": "requests", "novel_info": "requests",
                 "chapter_list": "requests", "chapter_content": "requests"}


def _patch_sources(monkeypatch, capabilities_map, manifest_extra=None):
    """钉住书源清单 / 声明能力 / 出厂 manifest（manifest_extra: {name: {顶层字段}}）。"""
    extra = manifest_extra or {}
    monkeypatch.setattr("novelbase.source.list_sources", lambda: sorted(capabilities_map))
    monkeypatch.setattr("novelbase.source.capabilities", lambda n: dict(capabilities_map.get(n, {})))
    monkeypatch.setattr("novelbase.source.get_manifest",
                        lambda n: {"source_name": n, "default_config": {}, **extra.get(n, {})})


def test_meta_defaults_when_nothing_set(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    _patch_sources(monkeypatch, {"demo-requests-default": REQUESTS_CAPS})
    assert sc.source_alias("demo-requests-default") == ""
    assert sc.source_group("demo-requests-default") == ""
    assert sc.display_name("demo-requests-default") == "demo-requests-default"


def test_meta_declared_then_user_override(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    _patch_sources(monkeypatch, {"demo-requests-default": REQUESTS_CAPS},
                   {"demo-requests-default": {"source_alias": "出厂别名", "source_group": "出厂组"}})
    assert sc.display_name("demo-requests-default") == "出厂别名"
    assert sc.source_group("demo-requests-default") == "出厂组"

    sc.save_site_config("demo-requests-default", {"source_alias": "用户别名", "source_group": "用户组"})
    assert sc.display_name("demo-requests-default") == "用户别名"
    assert sc.source_group("demo-requests-default") == "用户组"


def test_meta_blank_user_value_falls_back(tmp_path, monkeypatch):
    """用户层键被删除（空串即清除）后回落到出厂值。"""
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    _patch_sources(monkeypatch, {"demo-requests-default": REQUESTS_CAPS},
                   {"demo-requests-default": {"source_alias": "出厂别名"}})
    sc.save_site_config("demo-requests-default", {"source_alias": "用户别名"})
    assert sc.display_name("demo-requests-default") == "用户别名"
    sc.save_site_config("demo-requests-default", {"source_alias": ""})
    assert sc.display_name("demo-requests-default") == "出厂别名"


def test_meta_unknown_source_is_tolerant(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    _patch_sources(monkeypatch, {})
    assert sc.source_alias("nope-default") == ""
    assert sc.source_group("nope-default") == ""
    assert sc.display_name("nope-default") == "nope-default"


def test_default_source_names_desktop_is_everything(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.delenv("NLD_PLATFORM", raising=False)
    _patch_sources(monkeypatch, {"a-browser-default": BROWSER_CAPS,
                                 "b-requests-default": REQUESTS_CAPS})
    assert sc.default_source_names() == ["a-browser-default", "b-requests-default"]


def test_default_source_names_android_excludes_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.setenv("NLD_PLATFORM", "android")
    _patch_sources(monkeypatch, {"a-browser-default": BROWSER_CAPS,
                                 "b-requests-default": REQUESTS_CAPS})
    assert sc.default_source_names() == ["b-requests-default"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_source_metadata.py -q`
Expected: FAIL —— `AttributeError: module 'shared.config' has no attribute 'source_alias'`

- [ ] **Step 3: 实现**

在 `shared/config.py` 的 `is_source_enabled()` 之后插入：

```python
def _user_top(source_name: str, key: str) -> str:
    """用户层顶层字符串字段（strip 后）；非字符串 / 缺失 → ""。"""
    value = _user_site_cfg(source_name).get(key)
    return value.strip() if isinstance(value, str) else ""


def _declared_top(source_name: str, key: str) -> str:
    """出厂 `source.json` 顶层字符串字段；缺失 / manifest 异常 / 非字符串 → ""。"""
    from novelbase.source import get_manifest
    from novelbase.sources.manifest import ManifestError
    try:
        value = get_manifest(source_name).get(key)
    except (KeyError, ManifestError):
        return ""
    return value.strip() if isinstance(value, str) else ""


def source_group(source_name: str) -> str:
    """书源分组名：用户层顶层 `source_group` → 出厂 `source.json` 顶层 → `""`（未分组）。

    空串视为「未设」（PUT 用空串表达「清除覆盖」），故 `or` 短路即可。
    """
    return _user_top(source_name, "source_group") or _declared_top(source_name, "source_group")


def source_alias(source_name: str) -> str:
    """书源别名：用户层顶层 `source_alias` → 出厂 `source.json` 顶层 → `""`（未设）。"""
    return _user_top(source_name, "source_alias") or _declared_top(source_name, "source_alias")


def display_name(source_name: str) -> str:
    """显示名（CLI / 日志的唯一入口）：别名优先，未设则回落 `source_name`。"""
    return source_alias(source_name) or source_name


def default_source_names() -> list[str]:
    """默认参与集：本环境**可用**的全部书源（桌面 = 全部；Android = 排除不可用引擎的源）。

    取代旧的 `enabled_source_names()`（enabled ∩ available）——`enabled` 已废弃（见 spec D1/D2）。
    """
    from novelbase.source import list_sources
    return sorted(n for n in list_sources() if is_source_available(n))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_source_metadata.py -q`
Expected: `6 passed`

- [ ] **Step 5: 跑全量确认没破坏别处**

Run: `python -m pytest tests -q`
Expected: `499 passed`（旧函数仍在，无调用点变化）

- [ ] **Step 6: 提交**

```bash
git add shared/config.py tests/test_source_metadata.py
git commit -m "feat(config): 书源元信息读取入口与默认参与集"
```

---

### Task 2: 后端 —— 元信息出口 + 搜索多源

**Files:**
- Modify: `backend/routers/download.py`（`:19` import、`:67-87` 搜索分支、`:177-184` `/sources`）
- Modify: `backend/routers/config.py`（`:86-104` GET、`:106-141` PUT）
- Test: `tests/test_backend_download_routes.py`、`tests/test_backend_config_routes.py`
- Modify: `docs/superpowers/specs/2026-09-27-source-meta-and-search-selection-design.md`（把「同时出现以 `sources` 为准」改成 `source` 优先，与实现对齐）

**Interfaces:**
- Consumes: Task 1 的 `default_source_names()` / `source_alias()` / `source_group()`
- Produces:
  - `GET /api/v2/download/sources` → `{name: {capabilities, enabled, available, source_group, source_alias}}`（`enabled` 在 Task 6 删除）
  - `GET /api/v2/config/sources/{name}` → 增 `source_group` / `source_alias`
  - `PUT /api/v2/config/sources/{name}` → 接受顶层 `source_group` / `source_alias`（空串 = 删除键）
  - `GET /api/v2/download/search?query=&sources=a,b,c`（缺省/空 → `default_source_names()`；筛完为空 → 400）
  - 模块内 `_selected_sources(sources: str) -> list[str]`

- [ ] **Step 1: 先改 spec 那一句**

把 `docs/superpowers/specs/2026-09-27-source-meta-and-search-selection-design.md` 6.3 表格里 search 行的
「两者**同时出现时以 `sources` 为准**（`source` 只服务 URL 直达路径）」
改为
「两者同时出现时 **`source`（单源）优先**（`if source:` 分支在前，保持既有控制流）」。

- [ ] **Step 2: 写失败测试（后端下载路由）**

在 `tests/test_backend_download_routes.py` 追加：

```python
def test_sources_include_group_and_alias(monkeypatch):
    """`/sources` 每源带 source_group / source_alias（Task 6 后再去掉 enabled）。"""
    monkeypatch.setattr(dl, "list_sources", lambda: ["a-requests-default"])
    monkeypatch.setattr(dl, "effective_capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr(dl, "is_source_enabled", lambda n: True)
    monkeypatch.setattr(dl, "is_source_available", lambda n: True)
    monkeypatch.setattr(dl, "source_group", lambda n: "番茄")
    monkeypatch.setattr(dl, "source_alias", lambda n: "番茄·直连")
    out = asyncio.run(dl.list_all_sources())
    assert out["a-requests-default"]["source_group"] == "番茄"
    assert out["a-requests-default"]["source_alias"] == "番茄·直连"


def test_search_uses_selected_sources(monkeypatch):
    """`sources=a,b` → 只对 a、b 各发一次 search。"""
    monkeypatch.setattr(dl, "list_sources", lambda: ["a-r-default", "b-r-default", "c-r-default"])
    monkeypatch.setattr(dl, "is_source_available", lambda n: True)
    called = []

    async def fake_search(sources, query, engines, **kw):
        called.append(list(sources))
        return ()

    monkeypatch.setattr(dl, "search", fake_search)
    monkeypatch.setattr(dl, "get_cached_engine", lambda name, mode: object())
    monkeypatch.setattr(dl, "effective_capabilities", lambda n: {"search": "requests"})
    asyncio.run(dl.search_novels(query="关键词", source="", sources="a-r-default,b-r-default"))
    assert sorted(called) == [["a-r-default"], ["b-r-default"]]


def test_search_skips_unknown_and_unavailable(monkeypatch):
    """未知 / 不可用源静默跳过；全部无效 → 400。"""
    monkeypatch.setattr(dl, "list_sources", lambda: ["a-r-default"])
    monkeypatch.setattr(dl, "is_source_available", lambda n: n == "a-r-default")
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.search_novels(query="关键词", source="", sources="nope,browser-x"))
    assert ei.value.status_code == 400


def test_search_default_sources_when_param_absent(monkeypatch):
    """`sources` 缺省 → 走 default_source_names()。"""
    monkeypatch.setattr(dl, "default_source_names", lambda: ["a-r-default", "b-r-default"])
    called = []

    async def fake_search(sources, query, engines, **kw):
        called.append(list(sources))
        return ()

    monkeypatch.setattr(dl, "search", fake_search)
    monkeypatch.setattr(dl, "get_cached_engine", lambda name, mode: object())
    monkeypatch.setattr(dl, "effective_capabilities", lambda n: {"search": "requests"})
    asyncio.run(dl.search_novels(query="关键词", source=""))
    assert sorted(called) == [["a-r-default"], ["b-r-default"]]
```

在 `tests/test_backend_config_routes.py` 追加：

```python
def test_put_source_meta_group_and_alias(isolated_sites):
    """顶层 source_group / source_alias 写入用户层；空串删除该键。"""
    asyncio.run(cfg.save_source_config(KNOWN, {"source_group": " 番茄 ", "source_alias": "番茄·直连"}))
    saved = config_service.load_yaml(isolated_sites / f"{KNOWN}.yaml")
    assert saved["source_group"] == "番茄"       # 已 strip
    assert saved["source_alias"] == "番茄·直连"

    asyncio.run(cfg.save_source_config(KNOWN, {"source_group": ""}))
    saved = config_service.load_yaml(isolated_sites / f"{KNOWN}.yaml")
    assert "source_group" not in saved
    assert saved["source_alias"] == "番茄·直连"


def test_get_source_config_includes_meta(isolated_sites):
    asyncio.run(cfg.save_source_config(KNOWN, {"source_group": "番茄", "source_alias": "番茄·直连"}))
    data = asyncio.run(cfg.get_source_config(KNOWN))
    assert data["source_group"] == "番茄"
    assert data["source_alias"] == "番茄·直连"
```

- [ ] **Step 3: 跑测试确认失败**

Run: `python -m pytest tests/test_backend_download_routes.py tests/test_backend_config_routes.py -q`
Expected: FAIL（`sources` 参数不被接受 / 返回缺少 `source_group`）

- [ ] **Step 4: 实现 `backend/routers/download.py`**

import 行改为：

```python
from shared.config import (default_source_names, is_source_available, is_source_enabled,
                           effective_capabilities, source_alias, source_group)
```

（`enabled_source_names` 先留在 import 里到 Task 6 再删——Task 6 会把它从两处一并移除。）

在 `_resolve_url()` 之后新增：

```python
def _selected_sources(sources: str) -> list[str]:
    """解析 `sources=a,b,c`：按序去重，过滤未知与不可用源（静默跳过）。

    缺省 / 空 → `default_source_names()`（本环境全部可用源）。
    """
    if not sources.strip():
        return default_source_names()
    known = set(list_sources())
    picked: list[str] = []
    for raw in sources.split(","):
        name = raw.strip()
        if name and name in known and is_source_available(name) and name not in picked:
            picked.append(name)
    return picked
```

`search_novels` 签名加参数（放在 `source` 之后）：

```python
async def search_novels(query: str = Query(...), source: str = Query(""),
                        sources: str = Query(""), page: int = Query(1)):
```

`else:`（并发）分支改为：

```python
    else:
        names = _selected_sources(sources)
        if not names:
            raise HTTPException(400, "未指定有效书源" if sources.strip() else "本环境没有可用的书源")

        async def _search_one(name: str):
            # 每个源用自己的 _engines_for(name)，杜绝「同 mode 源共用首个源引擎」。
            try:
                return await search([name], query, _engines_for(name), page=page,
                                    mode_overrides=_mode_overrides(name))
            except Exception:
                # 复刻 core.search 的「单源失败静默跳过」：某源出错不影响其它源。
                return ()
        groups = await asyncio.gather(*(_search_one(n) for n in names))
        results = [r for group in groups for r in group]
```

`list_all_sources()` 改为：

```python
@router.get("/sources")
async def list_all_sources():
    """全部书源（含不可用）的扁平能力矩阵 + 元信息（mode 为有效值）。

    `available=False`（如 Android 上的 browser 书源）不从列表剔除：前端要列出并置灰。
    """
    return {
        name: {"capabilities": effective_capabilities(name),
               "enabled": is_source_enabled(name),
               "available": is_source_available(name),
               "source_group": source_group(name),
               "source_alias": source_alias(name)}
        for name in list_sources()
    }
```

- [ ] **Step 5: 实现 `backend/routers/config.py`**

`get_source_config` 返回体加两行（放在 `available` 附近）：

```python
        "available": is_source_available(source_name),
        "source_group": config_service.source_group(source_name),
        "source_alias": config_service.source_alias(source_name),
```

`save_source_config` 在 `concurrency` 处理之后、`cfg_body = body.get("config")` 之前插入：

```python
    # 顶层元信息：字符串写入用户层（strip 后非空），空串 = 删除该键（回落出厂 / source_name）
    for key in ("source_group", "source_alias"):
        if key in body:
            raw = body[key]
            text = raw.strip() if isinstance(raw, str) else ""
            if text:
                existing[key] = text
            else:
                existing.pop(key, None)
```

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/test_backend_download_routes.py tests/test_backend_config_routes.py -q`
Expected: 全部通过

- [ ] **Step 7: 跑全量**

Run: `python -m pytest tests -q`
Expected: `499 passed`（既有 `test_sources_shape_is_flat` 会在 Task 6 才改；本步不破坏它）

- [ ] **Step 8: 提交**

```bash
git add backend/routers/download.py backend/routers/config.py tests/test_backend_download_routes.py tests/test_backend_config_routes.py docs/superpowers/specs/2026-09-27-source-meta-and-search-selection-design.md
git commit -m "feat(backend): 书源元信息出口与搜索多源参数"
```

---

### Task 3: 前端设置页（别名/分组显示与编辑、去开关、并发数移位）

**Files:**
- Modify: `frontend/src/api/endpoints.ts`（`SourceInfo` 加两个字段）
- Modify: `frontend/src/features/sources/SourceAccordion.tsx`（顶部信息行；删开关与并发数）
- Modify: `frontend/src/features/sources/sourceConfigForm.tsx`（展开区加分组/别名/并发数）
- Test: 无单测基建 → 验证靠 `npx tsc -b` + `npm run lint` + 手工验收

**Interfaces:**
- Consumes: Task 2 的 `GET /config/sources/{name}`（新增 `source_group` / `source_alias`）、`PUT`（接受顶层两字段）、`GET /download/sources`（新增两字段）
- Produces: `SourceInfo` 含 `source_group: string` / `source_alias: string`（Task 4 复用）

- [ ] **Step 1: `endpoints.ts` 的 `SourceInfo` 加字段**

```ts
export interface SourceInfo {
  capabilities: Record<string, string>;
  enabled: boolean;
  /** 本环境是否支持该书源（Android 不支持 browser 源 → false）。 */
  available: boolean;
  /** 分组名（"" = 未分组；出厂预置 + 用户层覆盖）。 */
  source_group: string;
  /** 显示别名（"" = 未设，显示 source_name）。 */
  source_alias: string;
}
```

- [ ] **Step 2: 改写 `SourceAccordion.tsx`（顶部信息行；删除开关与并发数）**

整文件替换为：

```tsx
import {useState} from "react";
import {ChevronDown} from "lucide-react";
import {cn} from "@/lib/utils";
import type {SourceInfo} from "@/api/endpoints";
import {SourceConfigEditor} from "./sourceConfigForm";
import {CAP_LABELS} from "./sourceConfigFields";

/** 单个书源的折叠条：顶部显示「别名（未设则 source_name）+ 分组 + 能力」；展开即编辑。
 *
 * `available=false`（本环境不支持，如 Android 上的 browser 源）时置灰 + 标注 —— 书源仍**列出**
 * （让用户知道它存在、为什么用不了），但不可选。启用开关已随 `enabled` 废弃删除。 */
export function SourceAccordion({ name, info, available }: { name: string; info: SourceInfo; available: boolean }) {
  const [open, setOpen] = useState(false);
  const unavailable = !available;
  const display = info.source_alias || name;
  const caps = info.capabilities ?? {};

  return (
    <div className="border-b border-slate-100 last:border-b-0 dark:border-slate-800/50">
      <div className="flex items-center justify-between gap-4 py-2.5">
        <button onClick={() => setOpen(o => !o)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
          <ChevronDown className={cn("h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform duration-200", open && "rotate-180")} strokeWidth={1.5} />
          <span className={cn("shrink-0 text-sm font-medium", unavailable ? "text-slate-400 dark:text-slate-500" : "text-slate-700 dark:text-slate-200")}>{display}</span>
          {info.source_alias && <span className="shrink-0 font-mono text-[10px] text-slate-400">{name}</span>}
          {info.source_group && (
            <span className="shrink-0 rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-500 dark:bg-indigo-500/15 dark:text-indigo-400">{info.source_group}</span>
          )}
          <span className="flex flex-wrap gap-1">
            {unavailable && (
              // 目前唯一会「本环境不可用」的引擎就是 browser（APK 构建时排除了 playwright）
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-600 dark:bg-amber-500/15 dark:text-amber-400">
                本环境不支持 browser
              </span>
            )}
            {Object.keys(caps).length === 0 && <span className="text-[11px] text-slate-400">无能力</span>}
            {Object.entries(caps).map(([cap, mode]) => (
              <span key={cap} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                {CAP_LABELS[cap] ?? cap}·{mode}
              </span>
            ))}
          </span>
        </button>
      </div>
      {open && <SourceConfigEditor name={name} />}
    </div>
  );
}
```

（相对旧版删掉了：`useSaveSourceConfig` 引入、`enabled`/`concurrency` state、两个 `useEffect`、`toggleEnabled`/`commitConcurrency`、`<Toggle>` 与并发数输入框。）

- [ ] **Step 3: `sourceConfigForm.tsx` 的 `SourceConfigEditor` 加三行**

在 `const merged = cfg?.config ?? {};` 之后加：

```tsx
  // 并发数：与折叠条旧实现同样的「字符串 + 失焦校验提交」策略（非法不写）
  const [concurrency, setConcurrency] = useState("1");
  useEffect(() => { setConcurrency(String(cfg?.concurrency ?? 1)); }, [cfg?.concurrency]);
  const commitConcurrency = () => {
    const n = Number(concurrency);
    if (!Number.isInteger(n) || n < 1) {
      setConcurrency(String(cfg?.concurrency ?? 1));
      return;
    }
    if (n !== (cfg?.concurrency ?? 1)) saveSource.mutate({ concurrency: n });
  };
```

在 `{Object.entries(caps).length === 0 && ...}` 之前插入三行 Row（`TextField`/`Row` 已在本文件定义）：

```tsx
      <Row label="分组" desc="搜索页可按分组批量勾选">
        <TextField value={String(cfg?.source_group ?? "")} onChange={v => saveSource.mutate({ source_group: v })} />
      </Row>
      <Row label="别名" desc="界面显示名；留空则显示 source_name">
        <TextField value={String(cfg?.source_alias ?? "")} onChange={v => saveSource.mutate({ source_alias: v })} />
      </Row>
      <Row label="并发数" desc="该书源同时最多几个请求在飞（跨任务共享，默认 1）">
        <input
          type="number" min={1} step={1}
          value={concurrency}
          onChange={e => setConcurrency(e.target.value)}
          onBlur={commitConcurrency}
          onKeyDown={e => { if (e.key === "Enter") e.currentTarget.blur(); }}
          className="w-16 rounded-lg border border-white/20 bg-white/50 px-2 py-1.5 text-right text-xs text-slate-700 outline-none dark:border-slate-600/30 dark:bg-slate-800/50 dark:text-slate-300"
        />
      </Row>
```

（`TextField` 的 `onChange` 是「失焦 / 回车提交」语义，与本页其它字段一致；清空即传 `""`，后端按「删除该键」处理。）

- [ ] **Step 4: 类型检查 + lint**

Run: `cd frontend && npx tsc -b && npm run lint`
Expected: 0 错、0 告警

- [ ] **Step 5: 手工验收**

Run: `python cli.py`（或 `python app.py` 起服务）→ 设置页：折叠条顶部显示「别名 + 分组 + 能力」，**没有启用开关**；展开后有「分组 / 别名 / 并发数」三行；改分组为「番茄」、别名为「番茄·直连」→ 刷新后仍在，且顶部随之更新。

- [ ] **Step 6: 提交**

```bash
git add frontend/src/api/endpoints.ts frontend/src/features/sources/SourceAccordion.tsx frontend/src/features/sources/sourceConfigForm.tsx
git commit -m "feat(frontend): 设置页显示别名与分组并支持编辑，移除启用开关"
```

---

### Task 4: 前端搜索页（标题 tab 双框、URL tab 分组单选、结果 tab 显示别名）

**Files:**
- Modify: `frontend/src/components/ui/select.tsx`（补 `SelectLabel` 导出）
- Modify: `frontend/src/api/endpoints.ts`（`SourceOption` / `toSourceOptions` / `searchDownload`）
- Modify: `frontend/src/hooks/index.ts`（`useSearch` 参数类型）
- Modify: `frontend/src/features/bookshelf/SearchBar.tsx`（双框 + URL 分组）
- Modify: `frontend/src/features/bookshelf/BookshelfPage.tsx`（搜索参数、结果 tab 别名）

**Interfaces:**
- Consumes: Task 3 的 `SourceInfo.source_group/source_alias`；Task 2 的 `sources=a,b,c`
- Produces: `SourceOption { name, alias, group, enabled }`、`searchDownload({query, source?, sources?})`、`useSearch(params: {query, source?, sources?} | null)`

- [ ] **Step 1: `ui/select.tsx` 补 `SelectLabel`**

在 `const SelectGroup = SelectPrimitive.Group;` 之后加 `const SelectLabel = SelectPrimitive.Label;`，并把导出行改为：

```ts
export { Select, SelectGroup, SelectLabel, SelectValue, SelectTrigger, SelectContent, SelectItem, SelectSeparator };
```

- [ ] **Step 2: `endpoints.ts` 的 `SourceOption` / `toSourceOptions` / `searchDownload`**

```ts
/** 选源 UI 用的书源项：name = source_name（技术键，提交用），alias/group 供显示与分组。 */
export interface SourceOption {
  name: string;
  alias: string;
  group: string;        // "" = 未分组
  enabled: boolean;     // Task 6 随 enabled 废弃删除
}

/** 把 useSources() 的响应转成选源列表：滤掉本环境不可用的源；未设别名时 alias 回落 source_name。 */
export function toSourceOptions(sources?: Record<string, SourceInfo> | null): SourceOption[] {
  if (!sources) return [];
  return Object.entries(sources)
    .filter(([, info]) => info.available !== false)
    .map(([name, info]) => ({
      name,
      alias: info.source_alias || name,
      group: info.source_group || "",
      enabled: info.enabled,
    }));
}

export function searchDownload(params: { query: string; source?: string; sources?: string[] }) {
  const qs = new URLSearchParams({ query: params.query });
  if (params.source) qs.set("source", params.source);
  if (params.sources?.length) qs.set("sources", params.sources.join(","));
  return apiGet<SearchResult[]>(`/download/search?${qs}`);
}
```

- [ ] **Step 3: `hooks/index.ts` 的 `useSearch` 参数**

```ts
export function useSearch(params: { query: string; source?: string; sources?: string[] } | null) {
```

（查询键仍是整个 `params` 对象，`sources` 数组参与 key → 勾选变化会重新搜索，符合预期。）

- [ ] **Step 4: `SearchBar.tsx` —— props 与双框状态**

props 类型改为：

```tsx
interface SearchBarProps {
  /** 标题搜索并发勾选的书源；URL 直达携带用户手选的单个书源。 */
  onSearch: (query: string, opts?: { source?: string; sources?: string[] }) => void;
  sources?: SourceOption[];
  loading?: boolean;
  defaultQuery?: string;
  prefill?: { nonce: number; query: string; source?: string } | null;
}
```

组件内新增（放在 `const [shake, setShake] = useState(false);` 之后）：

```tsx
  // 勾选集合：null = 未初始化（= 全选）。不持久化、不在 sources 刷新时重置用户选择。
  const [picked, setPicked] = useState<string[] | null>(null);
  const allNames = useMemo(() => sources.map(s => s.name), [sources]);
  const selected = picked ?? allNames;
  const selectedSet = useMemo(() => new Set(selected), [selected]);

  // 分组 → 该组书源（"" 走「未分组」桶，排在最后）
  const groupedSources = useMemo(() => {
    const groups = new Map<string, SourceOption[]>();
    for (const s of sources) {
      if (!groups.has(s.group)) groups.set(s.group, []);
      groups.get(s.group)!.push(s);
    }
    return [...groups.entries()].sort(([a], [b]) => (a === "" ? 1 : b === "" ? -1 : a.localeCompare(b)));
  }, [sources]);

  const toggleAll = () => setPicked(selected.length === allNames.length ? [] : allNames);
  const pickGroup = (group: string) => setPicked(sources.filter(s => s.group === group).map(s => s.name));
  const toggleOne = (name: string) => setPicked(selectedSet.has(name) ? selected.filter(n => n !== name) : [...allNames.filter(n => selectedSet.has(n) || n === name)]);
```

`trigger()` 的标题分支改为：

```tsx
    } else {
      if (selected.length === 0) {
        setShake(true);
        setTimeout(() => setShake(false), 400);
        return;
      }
      onSearch(q, { sources: selected });
    }
```

URL 分支改为 `onSearch(q, { source })`。

- [ ] **Step 5: `SearchBar.tsx` —— 标题 tab 的双框 UI**

把标题模式的末尾提示 `<p className="px-1 text-[11px] text-slate-400">并发搜索全部已启用书源</p>` 替换为：

```tsx
          <div className={cn("flex flex-col gap-2 rounded-xl border border-white/20 bg-white/50 p-2 backdrop-blur-sm dark:border-slate-600/30 dark:bg-slate-800/40",
                             shake && "border-red-300 bg-red-50 animate-shake")}>
            {/* 框 1：批量单选（全选 / 各分组 / 未分组） */}
            <div className="flex flex-wrap items-center gap-1">
              <button onClick={toggleAll}
                className={cn("rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors",
                  selected.length === allNames.length
                    ? "bg-indigo-100 text-indigo-600 dark:bg-indigo-500/20 dark:text-indigo-300"
                    : "text-slate-500 hover:text-slate-700 dark:text-slate-400")}>
                {selected.length === allNames.length ? "全不选" : "全选"}
              </button>
              {groupedSources.map(([group, items]) => {
                const names = items.map(i => i.name);
                const active = selected.length === names.length && names.every(n => selectedSet.has(n));
                return (
                  <button key={group} onClick={() => pickGroup(group)}
                    className={cn("rounded-lg px-2.5 py-1 text-[11px] font-medium transition-colors",
                      active ? "bg-indigo-100 text-indigo-600 dark:bg-indigo-500/20 dark:text-indigo-300"
                             : "text-slate-500 hover:text-slate-700 dark:text-slate-400")}>
                    {group || "未分组"}
                  </button>
                );
              })}
              <span className="ml-auto text-[11px] text-slate-400">已选 {selected.length}/{allNames.length}</span>
            </div>
            {/* 框 2：逐源复选（显示别名，按分组分节） */}
            <div className="flex flex-col gap-1">
              {groupedSources.map(([group, items]) => (
                <div key={group} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="w-16 shrink-0 truncate text-[10px] text-slate-400">{group || "未分组"}</span>
                  {items.map(s => (
                    <label key={s.name} className="flex cursor-pointer items-center gap-1 text-[11px] text-slate-600 dark:text-slate-300">
                      <input type="checkbox" checked={selectedSet.has(s.name)} onChange={() => toggleOne(s.name)} className="h-3.5 w-3.5 rounded border-slate-300" />
                      <span>{s.alias}</span>
                    </label>
                  ))}
                </div>
              ))}
              {sources.length === 0 && <span className="px-1 text-[11px] text-slate-400">没有可用的书源</span>}
            </div>
          </div>
```

- [ ] **Step 6: `SearchBar.tsx` —— URL tab 按分组分节**

把 URL 模式的 `<SelectContent>{sources.map(...)}</SelectContent>` 替换为：

```tsx
              <SelectContent>
                {groupedSources.map(([group, items]) => (
                  <SelectGroup key={group}>
                    <SelectLabel className="px-2 py-1 text-[10px] text-slate-400">{group || "未分组"}</SelectLabel>
                    {items.map(({ name, alias }) => (
                      <SelectItem key={name} value={name}>{alias}</SelectItem>
                    ))}
                  </SelectGroup>
                ))}
              </SelectContent>
```

并把 import 行扩为 `import {Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue} from "@/components/ui/select";`。

- [ ] **Step 7: `BookshelfPage.tsx` 适配**

搜索参数类型与调用：

```tsx
  const [searchParams, setSearchParams] = useState<{
    query: string; source?: string; sources?: string[];
  } | null>(null);
```

`handleOnlineSearch` 签名与标题分支：

```tsx
  const handleOnlineSearch = useCallback(async (query: string, opts?: { source?: string; sources?: string[] }) => {
    const source = opts?.source;
    if (!query.trim()) { setSearchParams(null); SessionCache.clearSearch(); return; }
    SessionCache.saveSearch(query, source);
    addHistoryMut.mutate({ source_name: source ?? "", keyword: query.trim() });
    // ...（URL 分支与原来一致，仍用 source）
    setSearchParams({ query, source, sources: opts?.sources });
  }, [navigate, toast, fetchMetaMut, addHistoryMut]);
```

结果 tab 用别名显示 —— 在 `showSourceTabs` 那段之前加映射，并把 `SOURCE_TABS` 的 label 换掉：

```tsx
            const aliasOf = new Map(sourceOptions.map(o => [o.name, o.alias]));
            const SOURCE_TABS = [
              { id: "all", label: "全部" },
              ...sourceNames.map(name => ({ id: name, label: aliasOf.get(name) ?? name })),
            ];
```

- [ ] **Step 8: 类型检查 + lint**

Run: `cd frontend && npx tsc -b && npm run lint`
Expected: 0 错、0 告警

- [ ] **Step 9: 手工验收**

Run: `python app.py` → 搜索页（标题 tab）：默认全部勾选；点「番茄」只勾番茄三个源且该按钮高亮；点「全不选」→ 全部取消且搜索按钮禁用；重新勾选两个源 → 结果只来自这两个源；URL tab 下拉按分组分节显示别名；搜索结果的来源 tab 显示别名。

- [ ] **Step 10: 提交**

```bash
git add frontend/src/components/ui/select.tsx frontend/src/api/endpoints.ts frontend/src/hooks/index.ts frontend/src/features/bookshelf/SearchBar.tsx frontend/src/features/bookshelf/BookshelfPage.tsx
git commit -m "feat(frontend): 搜索页按分组与别名勾选书源"
```

---

### Task 5: CLI（默认源集、别名/分组显示、删除启用开关）

**Files:**
- Modify: `cli/main.py`（`cmd_search`、`cmd_source`、`dev new-source`）
- Modify: `cli/interactive.py`（默认源集、结果来源显示）
- Modify: `cli/menus.py`（删除启用开关菜单项）
- Test: `tests/test_interactive_cli.py`、`tests/test_cli_effective_mode.py`

**Interfaces:**
- Consumes: Task 1 的 `default_source_names()` / `display_name()` / `source_group()`
- Produces: `python cli.py sources list` 的显示形状（别名 · 分组 · source_name）、`--json` 的键集合

- [ ] **Step 1: 写失败测试**

在 `tests/test_interactive_cli.py` 里，把 3 处 `monkeypatch.setattr(mod, "enabled_source_names", lambda: [...])` 改为 `monkeypatch.setattr(mod, "default_source_names", lambda: [...])`（`:264`、`:282`、`:297`、`:307`）。若断言依赖「未启用源不参与」，改为依赖 `default_source_names` 的返回值。

在 `tests/test_cli_effective_mode.py` 追加（若文件里尚无 sources 显示相关用例）：

```python
def test_cmd_source_list_shows_group_and_alias(monkeypatch, capsys):
    """`sources list` 显示别名与分组；`--json` 用 source_name / source_alias / source_group 键。"""
    from cli import main as cli_main

    monkeypatch.setattr("novelbase.source.list_sources", lambda: ["demo-requests-default"])
    monkeypatch.setattr(cli_main, "effective_capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr("shared.config.source_alias", lambda n: "演示源")
    monkeypatch.setattr("shared.config.source_group", lambda n: "演示组")

    class Args:
        source_command = "list"
        json = True

    cli_main.cmd_source(Args())
    out = capsys.readouterr().out
    assert '"source_name": "demo-requests-default"' in out
    assert '"source_alias": "演示源"' in out
    assert '"source_group": "演示组"' in out
    assert '"enabled"' not in out
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_cli_effective_mode.py tests/test_interactive_cli.py -q`
Expected: FAIL（`default_source_names` 未被 monkeypatch 到 / `cmd_source` 仍输出 `enabled`）

- [ ] **Step 3: 实现 `cli/main.py`**

`:124-126` 改为：

```python
    from shared.config import default_source_names

    sources = [args.source] if args.source else default_source_names()
```

`cmd_source` 整体替换为：

```python
def cmd_source(args):
    """书源管理（mode 显示有效值；显示别名与分组）。"""
    from novelbase.source import list_sources
    from shared.config import display_name, source_group

    if args.source_command != "list":
        return

    names = list_sources()
    if args.json:
        import json
        payload = {
            name: {
                "source_name": name,
                "source_alias": display_name(name),
                "source_group": source_group(name),
                "capabilities": effective_capabilities(name),
            }
            for name in names
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(f"可用书源 ({len(names)}):")
    for name in names:
        caps = effective_capabilities(name)
        cap_str = ", ".join(f"{c}:{m}" for c, m in caps.items()) or "无"
        print(f"  - {display_name(name)}  [{source_group(name) or '未分组'}]  ({name})  capabilities: {cap_str}")
```

`cmd_dev` 的 `new-source` 分支：删除 `enabled = mode != "api"` 行、`manifest` 里的 `"enabled": enabled,` 行、`save_site_config(name, {"enabled": enabled, ...})` 里的 `"enabled": enabled,`；并把该分支 docstring 里「出厂 `enabled`（D4）：api 类默认 `false`，requests/browser 类默认 `true`」整句删掉（`enabled` 已废弃）。

- [ ] **Step 4: 实现 `cli/menus.py`**

import 行去掉 `is_source_enabled`：

```python
from shared.config import merged_source_config, effective_capabilities
```

`_settings_source_detail` 整体替换（删启用开关、显示别名与分组）：

```python
def _settings_source_detail(cfg: dict, source_name: str) -> None:
    """单书源详情：别名/分组信息 + 各能力段入口。"""
    from shared.config import display_name, source_group
    while True:
        caps = effective_capabilities(source_name)
        print(f"\n[{display_name(source_name)} 设置]  {source_name}  分组: {source_group(source_name) or '未分组'}")
        entries = list(caps.items())
        for i, (cap, mode) in enumerate(entries, 1):
            print(f" {i}. {cap}（{mode}）配置")
        print(" 0. 返回")
        ch = input("请选择: ").strip()
        if ch == "0":
            return
        try:
            idx = int(ch) - 1
        except ValueError:
            continue
        if 0 <= idx < len(entries):
            _edit_capability(source_name, entries[idx][0], entries[idx][1])
```

删除 `_toggle_source_enabled` 函数（整块）。

- [ ] **Step 5: 实现 `cli/interactive.py`**

- import 行：`enabled_source_names` → `default_source_names`，并加 `display_name`。
- `:84` `sources = enabled_source_names()` → `sources = default_source_names()`。
- `:56` 附近 docstring 里「并发全部「启用书源」（`enabled_source_names()`）」→「并发全部可用书源（`default_source_names()`）」。
- 结果来源的显示：先定位打印点 ——

Run: `grep -n "source_name" cli/interactive.py`

把**用户可见的**结果行（形如 `print(f"  ... {r.source_name} ...")`）里的 `r.source_name` 改为 `display_name(r.source_name)`；写入配置/落库的地方**不动**（必须存 `source_name`）。

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/test_interactive_cli.py tests/test_cli_effective_mode.py -q`
Expected: 通过

- [ ] **Step 7: 手工冒烟**

```bash
python cli.py sources list
python cli.py sources list --json
```
Expected: 列表显示「别名 [分组] (source_name) capabilities: …」；JSON 键为 `source_name` / `source_alias` / `source_group` / `capabilities`（不含 `enabled`）。

- [ ] **Step 8: 跑全量**

Run: `python -m pytest tests -q`
Expected: 全绿（`499 passed` 附近）

- [ ] **Step 9: 提交**

```bash
git add cli/main.py cli/menus.py cli/interactive.py tests/test_interactive_cli.py tests/test_cli_effective_mode.py
git commit -m "feat(cli): 书源显示别名与分组，默认源集改为全部可用源"
```

---

### Task 6: 全链删除 `enabled`

本任务把 `enabled` 从契约、数据、代码、测试中彻底移除。**顺序重要**：先切数据与 core，再删消费者，最后跑 grep 验收。

**Files:**
- Modify: `novelbase/sources/manifest.py`、`novelbase/sources/*/source.json`（10 个）、`template/config/sites/*.yaml`（10 个）
- Modify: `shared/config.py`（删 `is_source_enabled` / `enabled_source_names`）
- Modify: `backend/routers/download.py`、`backend/routers/config.py`、`backend/services/source_guard.py`（docstring）
- Modify: `frontend/src/api/endpoints.ts`、`frontend/src/features/detail/SourcePickerDialog.tsx`
- Test: `tests/test_source_metadata.py`（合并三层合并用例）、删除 `tests/test_source_enabled.py`、`tests/test_source_availability.py`、`tests/test_backend_download_routes.py`

**Interfaces:**
- Produces: `source.json` 无 `enabled`（其余键不变）；`SourceInfo` 无 `enabled`；`SourceOption` 无 `enabled`

- [ ] **Step 1: `manifest.py` 去掉 `enabled`，加可选字段校验**

```python
IDENTITY_FIELDS = ("source_name",)
```

删掉 `enabled` 的 bool 校验两行（`if not isinstance(manifest["enabled"], bool): raise ManifestError(...)`），并在 `source_name` 校验之后插入：

```python
    for optional in ("source_alias", "source_group"):
        if optional in manifest and not (isinstance(manifest[optional], str) and manifest[optional].strip()):
            raise ManifestError(f"{path} 的 {optional} 必须是非空字符串")
```

- [ ] **Step 2: 改 10 个 `source.json`**

每个文件删 `"enabled": ...,` 一行，并加 `source_group` / `source_alias` 两行（值按下表，`source_alias` 在前、`source_group` 在后，紧跟 `source_name`）：

```json
{
  "source_name": "fanqie-requests-default",
  "source_alias": "番茄·直连",
  "source_group": "番茄",
  "concurrency": 1,
```

| 文件 | `source_alias` | `source_group` |
|---|---|---|
| `fanqie_requests_default` | 番茄·直连 | 番茄 |
| `fanqie_browser_default` | 番茄·浏览器 | 番茄 |
| `fanqie_api_rain` | 番茄·Rain API | 番茄 |
| `fanqie_api_oiapi` | 番茄·oiapi | 番茄 |
| `qidian_requests_default` | 起点·直连 | 起点 |
| `qidian_browser_default` | 起点·浏览器 | 起点 |
| `qimao_requests_default` | 七猫·直连 | 七猫 |
| `qimao_browser_default` | 七猫·浏览器 | 七猫 |
| `qimao_api_rain` | 七猫·Rain API | 七猫 |
| `92xs_requests_default` | 92xs | 92xs |

- [ ] **Step 3: 模板删 `enabled`**

`template/config/sites/*.yaml`（10 个）：删除第 1 行 `enabled: true` / `enabled: false`。若删后文件为空，写入一行注释避免空文件：

```yaml
# 该书的用户层配置（可选字段：source_group / source_alias / concurrency 与逐能力段）
```

- [ ] **Step 4: 写失败测试（契约与元信息）**

`tests/test_source_metadata.py` 追加：

```python
def test_manifest_rejects_blank_optional_meta(tmp_path, monkeypatch):
    """出厂 manifest 的 source_alias / source_group 必须是非空字符串。"""
    import json
    from novelbase.sources import manifest as mf

    src = tmp_path / "demo"
    src.mkdir()
    (src / "source.json").write_text(json.dumps({
        "source_name": "demo-requests-default",
        "source_group": "   ",
        "default_config": {},
    }), encoding="utf-8")
    with pytest.raises(mf.ManifestError):
        mf.load_manifest(src)


def test_manifest_without_enabled_is_valid(tmp_path):
    """source.json 不再需要 enabled。"""
    import json
    from novelbase.sources import manifest as mf

    src = tmp_path / "demo2"
    src.mkdir()
    (src / "source.json").write_text(json.dumps({
        "source_name": "demo2-requests-default",
        "source_group": "演示",
        "default_config": {},
    }), encoding="utf-8")
    assert mf.load_manifest(src)["source_name"] == "demo2-requests-default"
```

（`load_manifest(source_dir: Path)` 是现有入口，见 `novelbase/sources/manifest.py:36`；测试里的 `src` 已是 `Path`。）

`tests/test_source_metadata.py` 追加迁移过来的三层合并用例：

```python
def test_merged_source_config_three_layers(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr("novelbase.source.capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr("novelbase.source.get_manifest", lambda n: {
        "source_name": n,
        "default_config": {"search": {"mode": "requests", "timeout": 30, "retry_times": 3}},
    })
    merged = sc.merged_source_config("demo-requests-default")
    assert merged["search"]["mode"] == "requests"
    assert merged["search"]["timeout"] == 30          # 第 2 层
    sc.save_site_config("demo-requests-default", {"search": {"timeout": 99}})
    assert sc.merged_source_config("demo-requests-default")["search"]["timeout"] == 99
```

然后删除旧文件：

```bash
git rm tests/test_source_enabled.py
```

- [ ] **Step 5: 跑测试确认失败**

Run: `python -m pytest tests/test_source_metadata.py -q`
Expected: FAIL（`source_group` 非空校验尚未实现）

- [ ] **Step 6: `shared/config.py` 删除旧函数**

删除 `is_source_enabled()` 与 `enabled_source_names()` 两个函数整体。

- [ ] **Step 7: 后端去掉 `enabled`**

`backend/routers/download.py`：
- import 行去掉 `is_source_enabled`
- `list_all_sources()` 的返回值去掉 `"enabled": is_source_enabled(name),`

`backend/routers/config.py`：
- `get_source_config` 返回体去掉 `"enabled": ...` 行
- `save_source_config`：删除 `if isinstance(body.get("enabled"), bool): existing["enabled"] = body["enabled"]` 两行，并在元信息处理之前加清理：

```python
    existing.pop("enabled", None)   # enabled 已废弃：顺手清理旧用户层残留键
```

`backend/services/source_guard.py`：docstring 里 `（\`is_source_enabled()\` 会 \`KeyError\` → 500）` 改为 `（读未知书源的配置会 \`KeyError\` → 500）`。

- [ ] **Step 8: 前端去掉 `enabled`**

`frontend/src/api/endpoints.ts`：`SourceInfo` 删 `enabled: boolean;`、`SourceOption` 删 `enabled: boolean;`、`toSourceOptions` 的 map 去掉 `enabled: info.enabled,`。

`frontend/src/features/detail/SourcePickerDialog.tsx`：列表项改为显示别名且不再有「未启用」标注 ——

```tsx
          {sources.map(({name, alias}) => (
            <button key={name} onClick={() => setSelected(name)}
              className={cn(
                "w-full flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all",
                selected === name
                  ? "border-indigo-300 bg-indigo-50 dark:border-indigo-500/40 dark:bg-indigo-500/15"
                  : "border-white/20 bg-white/60 hover:border-slate-200"
              )}>
              <Globe className={cn("h-5 w-5 shrink-0", selected === name ? "text-indigo-500" : "text-slate-400")} strokeWidth={1.5} />
              <span className="flex min-w-0 flex-1 items-center gap-1.5">
                <span className={cn("truncate text-sm font-medium", selected === name ? "text-indigo-600 dark:text-indigo-400" : "text-slate-700")}>{alias}</span>
              </span>
              {name === current && (
                <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">当前</span>
              )}
            </button>
          ))}
```

并把该文件 props 注释里的「含 enabled，未启用的源仅标注、仍可选」改为「已过滤本环境不可用源」。

- [ ] **Step 9: 改剩余测试断言**

- `tests/test_source_availability.py`：3 处 `sc.enabled_source_names()` → `sc.default_source_names()`；删除与 `tests/test_source_metadata.py` 重复的用例（只保留环境能力表相关：`supported_modes` / `effective_capabilities` 覆盖回退 / `is_source_available` / API `available` 与 400 / core 兜底）。
- `tests/test_backend_download_routes.py`：`test_sources_shape_is_flat` 的期望去掉 `"enabled": True`（并去掉 `monkeypatch.setattr(dl, "is_source_enabled", ...)`）；`test_sources_include_disabled` 整例删除（`enabled` 已废弃）。
- `tests/test_backend_config_routes.py`：若断言 `GET /config/sources/{name}` 含 `enabled`，去掉该断言。

- [ ] **Step 10: 跑测试 + grep 验收**

```bash
python -m pytest tests -q
grep -rn "is_source_enabled\|enabled_source_names" --include=*.py backend/ cli/ shared/ novelbase/ init_config.py tests/ || echo "OK: 无残留"
grep -rn '"enabled"' novelbase/sources/*/source.json || echo "OK: source.json 已无 enabled"
grep -rn "^enabled:" template/config/sites/ || echo "OK: 模板已无 enabled"
cd frontend && npx tsc -b && npm run lint
```
Expected: pytest 全绿；三条 grep 均打印 OK；tsc 0 错、lint 0 告警

- [ ] **Step 11: 提交**

```bash
git add novelbase/sources/manifest.py novelbase/sources/*/source.json template/config/sites/*.yaml shared/config.py backend/routers/download.py backend/routers/config.py backend/services/source_guard.py frontend/src/api/endpoints.ts frontend/src/features/detail/SourcePickerDialog.tsx tests/test_source_metadata.py tests/test_source_availability.py tests/test_backend_download_routes.py tests/test_backend_config_routes.py
git rm --cached tests/test_source_enabled.py 2>/dev/null || true
git commit -m "refactor: 彻底移除 enabled，书源元信息改由分组与别名表达"
```

（若上一步 `git rm` 已在 Step 4 执行，`git rm --cached` 会被跳过。）

---

### Task 7: 文档追平

**Files:**
- Modify: `docs/session-prompt.md`、`docs/project/sources.md`、`docs/project/config.md`、`docs/project/cli.md`、`docs/project/updates.md`、`CHANGELOG.md`

- [ ] **Step 1: `docs/project/sources.md`**

- `source.json` 规范段：从字段表删除 `enabled` 行；新增 `source_alias` / `source_group`（**可选**顶层，字符串；出厂默认值，用户层可覆盖）；示例 JSON 同步。
- 「内置书源」表：加两列 `source_alias` / `source_group`（值取 Task 6 Step 2 的表），并删掉「enabled（出厂）」列。
- 环境能力表段：`enabled_source_names()` 的相关描述改为 `default_source_names()`（= 全部可用源）。

- [ ] **Step 2: `docs/project/config.md`**

- `sites/{source_name}.yaml` 示例：删 `enabled: true` 行，加 `source_group` / `source_alias` 两行与说明（空 = 未分组 / 未设显示名）。
- 「顶层 `enabled`」条目整体替换为：

```markdown
- **顶层 `source_group` / `source_alias`**：书源的分组名与显示别名；用户层覆盖出厂 `source.json` 的同名字段。
  空串（或删除该键）= 回落出厂值 / `source_name`。读取入口 `shared.config.source_group()` /
  `source_alias()` / `display_name()`。**`enabled` 已废弃**（2026-09-27）：书源不再有启用概念，
  搜索时由用户勾选参与的书源（默认全选），默认参与集 = `shared.config.default_source_names()`。
```

- [ ] **Step 3: `docs/session-prompt.md`**

在「关键约定」里更新/新增：

```markdown
- **书源元信息与选择（2026-09-27）**：`enabled` **已彻底废弃**（`source.json` 与用户层都不再有；旧键不读、PUT 时清理）。书源以 `source_group`（分组，一个源一个组，空 = 未分组）+ `source_alias`（显示别名，未设回落 `source_name`）表达；读取入口 `shared.config.source_group()/source_alias()/display_name()`。默认参与集 = `shared.config.default_source_names()`（本环境**可用**的全部源；Android 仍排除 browser 源）。搜索支持 `GET /download/search?sources=a,b,c`（缺省 = 默认参与集；未知/不可用源静默跳过，全无效 400）。前端搜索页（标题 tab）为「全选/分组」分段单选 + 逐源复选（**默认全选、不持久化**），URL tab 单选按分组分节显示别名。
```

并把「环境能力表」条目里 `enabled_source_names()` 的表述改为 `default_source_names()`。

- [ ] **Step 4: `docs/project/cli.md`**

- `sources list` 的输出说明：改为「显示 `别名 [分组] (source_name) capabilities`」；`--json` 的键说明同步（`source_name` / `source_alias` / `source_group` / `capabilities`）。
- 「书源与模式」段里 `enabled_source_names()` 的表述改为 `default_source_names()`（并注明缺省 = 全部可用源）。
- 交互式入口：删除「启用/停用书源」菜单项的说明（若存在）。

- [ ] **Step 5: `docs/project/updates.md` + `CHANGELOG.md`**

- `updates.md`：在 2026-09-27 节（`source_name` 全局唯一那节）之后追加子节：

```markdown
### 书源元信息（分组/别名）与按选择搜索

- **`enabled` 彻底废弃**：`source.json` 与用户层都不再有该字段；`is_source_enabled()` /
  `enabled_source_names()` 删除，改为 `default_source_names()`（= 本环境全部**可用**源）。
  旧用户层残留键不读，PUT 时清理
- **新增元信息**：用户层顶层 `source_group`（一个源一个组，空 = 未分组）/ `source_alias`
  （显示别名，未设回落 `source_name`）；读取入口 `source_group()` / `source_alias()` /
  `display_name()`；10 个内置源出厂预置分组与别名（`source.json` 可选字段，用户层可覆盖）
- **搜索多源**：`GET /download/search?sources=a,b,c`（缺省 = 默认参与集；未知/不可用源静默跳过，
  全无效 400）；前端标题 tab 双框（「全选/分组」分段单选 + 逐源复选，默认全选、不持久化），
  URL tab 单选按分组分节显示别名；结果来源 tab 显示别名
- **设置页**：折叠条顶部显示「别名 + 分组 + 能力」，**移除启用开关**，并发数移入展开区；
  展开区新增「分组 / 别名」输入
- **CLI**：`sources list` 显示别名与分组（去掉遗留 `show_name` 死键）、交互式菜单删除启用开关、
  `cmd_search` 默认源集改为 `default_source_names()`
- 设计见 `docs/superpowers/specs/2026-09-27-source-meta-and-search-selection-design.md`，
  计划见 `docs/superpowers/plans/2026-09-27-source-meta-and-search-selection.md`
- 测试：`python -m pytest tests -q` = **0 failed**；前端 `npx tsc -b` 0 错、`npm run lint` 0 告警
```

- `CHANGELOG.md`：在 `## Unreleased` 段补两条（「新增」里加元信息与搜索选择，「变更（破坏性）」里加 `enabled` 废弃）。测试数按实际填写。

- [ ] **Step 6: 提交**

```bash
git add docs/session-prompt.md docs/project/sources.md docs/project/config.md docs/project/cli.md docs/project/updates.md CHANGELOG.md
git commit -m "docs: 追平书源元信息与按选择搜索（enabled 废弃）"
```

---

## 计划自查（作者已跑）

- **spec 覆盖**：§1 数据模型 → T1/T6；§2 参与集 → T1/T6；§3 后端 API → T2/T6；§4 设置页 → T3；§5 搜索页 → T4；§6 CLI/模板 → T5/T6；§7 涉及文件 → 全部任务；§8 测试 → 各任务 Step 内；§9 风险 → Global Constraints + T6 Step 10 的 grep 验收。
- **占位符**：无 TBD/TODO；每个代码步骤都给了可粘贴的片段。
- **类型一致性**：`source_group()` / `source_alias()` / `display_name()` / `default_source_names()` 在 T1 定义，T2/T5 按同名消费；前端 `SourceInfo.source_group/source_alias` 在 T3 Step 1 定义，T4 消费；`SourceOption {name, alias, group, enabled}` 在 T4 Step 2 定义，T4 Step 5/6/7 消费（`enabled` 在 T6 Step 8 删除）。
- **已知顺序约束**：T6 必须在 T2–T5 之后（先切消费者再删数据）；T3 依赖 T2 的后端字段；T4 依赖 T3 的 `SourceInfo`。

## Execution Handoff

两种执行方式（完成后由执行者/主 agent 选择）：

1. **Subagent-Driven（推荐）** —— 每个 Task 派一个新 subagent，任务之间做 review；对应 skill `superpowers:subagent-driven-development`。
2. **Inline Execution** —— 在当前会话按批次执行并设检查点；对应 skill `superpowers:executing-plans`。

