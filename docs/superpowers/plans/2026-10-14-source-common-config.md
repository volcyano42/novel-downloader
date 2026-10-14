# 书源「常规」配置段 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让书源配置里跨能力共享的字段（`key`/`params`/`delay`/`timeout`/…）在用户层只存一份（新增顶层 `common` 段），并在设置页提供一个默认展开的「常规」段、各能力段默认收起。

**Architecture:** 用户层 `sites/{name}.yaml` 新增可选顶层 `common`；`merged_source_config()` 在「出厂/书源默认」与「用户层能力段」之间插入「用户层 common」一层，能力段恒覆盖 common（保住逐能力覆盖）。写入 common 时顺带删除各能力段同名键（否则旧值优先、改了不生效）；另加 `converge` 端点把各段一致的键收敛到 common。

**Tech Stack:** Python 3.10 / FastAPI / PyYAML（后端）；React 18 + TS + react-router-dom + @tanstack/react-query（前端）；测试用 pytest（后端）与 Python Playwright headless（`scripts/ui_smoke.py`，前端）。

**Spec:** `docs/superpowers/specs/2026-10-14-source-common-config-design.md`

## Global Constraints

- **用户层能力段恒覆盖用户层 `common`**（保「逐能力覆盖」）
- **`common` 不含 `mode`**：常规段字段集 = 各能力段 mode 的共有字段去掉 `mode`
- **老用户层 yaml（无 `common` 段）的合并结果必须逐字不变**
- 写 `common` 某键时，**同时从各能力段删除同名键**；`{k: null}` = 删除 `common.k`
- `converge` 只收敛**出现在全部能力段且取值全相同**的键
- 顶层 `concurrency` / `source_group` / `source_alias` 不属 `common`，行为不变
- 提交纪律：中文 commit、一个方面一条 commit、显式列文件（禁 `git add -A`）；dev 可自动推送
- 后端路由测试**不启 lifespan/TestClient**，用 `asyncio.run` 直调路由函数（既有模式）

## Review Focus

1. **老 yaml（无 `common`）合并结果不变** —— 用户升级后最可能遇到的回归；`common` 缺失必须等价于空
2. **改 common 是否真的生效** —— 漏删各能力段同名键时，旧值优先级更高，用户会看到「改了没反应」
3. **能力段覆盖 common 的优先级** —— 反了就没法给单个能力设不同的 delay/timeout
4. **converge 的收敛条件** —— 若把「只出现在部分能力段」的键也收敛，其余能力会从「继承出厂」悄悄变成「继承 common」
5. **前端冒烟断言不得恒真** —— 必须用 `data-testid` 锚定到具体容器（2026-10-14 设置页 review 中，5 条断言因取与导航同字的文案而恒真）

---

### Task 1: 合并层插入「用户层 common」

**Files:**
- Modify: `shared/config.py:226-252`（`merged_source_config`）
- Test: `tests/test_source_common_config.py`（新建）

**Interfaces:**
- Consumes: `_user_site_cfg(source_name) -> dict`（用户层 yaml 原始内容）、`deep_merge(base, override)`、`ENGINE_DEFAULTS`、`effective_capabilities()`
- Produces: `merged_source_config(source_name) -> dict[str, dict]` —— 每个能力段的字段中，用户层 `common` 的键已并入，且**被用户层该能力段覆盖**

- [ ] **Step 1: 写失败测试**

```python
# tests/test_source_common_config.py
"""用户层 common 段的合并优先级（spec: 2026-10-14-source-common-config-design.md）。"""
import shared.config as config


def _patch_source(monkeypatch, user_cfg, caps=None, defaults=None):
    monkeypatch.setattr(config, "effective_capabilities",
                        lambda name: caps or {"search": "api", "novel_info": "api",
                                              "chapter_list": "api", "chapter_content": "api"})
    monkeypatch.setattr(config, "_user_site_cfg", lambda name: user_cfg)
    monkeypatch.setattr(config, "get_manifest",
                        lambda name: {"default_config": defaults or {c: {} for c in
                                      ("search", "novel_info", "chapter_list", "chapter_content")}},
                        raising=False)


def test_common_applies_to_every_capability(monkeypatch):
    """common 里的键出现在每个能力段。"""
    _patch_source(monkeypatch, {"common": {"timeout": 42, "key": "k1"}})
    out = config.merged_source_config("x")
    for cap in ("search", "novel_info", "chapter_list", "chapter_content"):
        assert out[cap]["timeout"] == 42
        assert out[cap]["key"] == "k1"


def test_capability_overrides_common(monkeypatch):
    """能力段的值压过 common（逐能力覆盖仍然有效）。"""
    _patch_source(monkeypatch, {"common": {"delay": [1, 1]},
                                "chapter_content": {"delay": [9, 9]}})
    out = config.merged_source_config("x")
    assert out["chapter_content"]["delay"] == [9, 9]
    assert out["search"]["delay"] == [1, 1]


def test_absent_common_is_noop(monkeypatch):
    """没有 common 段时，结果与旧行为一致（回归）。"""
    _patch_source(monkeypatch, {"search": {"timeout": 7}})
    out = config.merged_source_config("x")
    assert out["search"]["timeout"] == 7
    assert out["search"]["mode"] == "api"


def test_common_does_not_override_mode(monkeypatch):
    """common 里的 mode 不参与覆盖（有效 mode 不变量）。"""
    _patch_source(monkeypatch, {"common": {"mode": "browser"}})
    out = config.merged_source_config("x")
    assert out["search"]["mode"] == "api"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_source_common_config.py -q`
Expected: FAIL —— `test_common_applies_to_every_capability` 断言 timeout 42 失败（common 未并入）

- [ ] **Step 3: 在 `merged_source_config` 里插入 common 层**

在循环内、`out[cap] = deep_merge(base, user_cap)` 之前插入：取 `user.get("common")`（非 dict 时按 `{}`），并 **pop 掉其中的 `mode`**（`common` 不含 mode 的不变量），然后 `out[cap] = deep_merge(deep_merge(base, user_common), user_cap)`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_source_common_config.py -q`
Expected: 4 passed

- [ ] **Step 5: 跑既有相关测试，确认没破坏**

Run: `python -m pytest tests/test_site_config.py tests/test_config_effective_mode.py -q`
Expected: 全部 passed

- [ ] **Step 6: Commit**

```bash
git add shared/config.py tests/test_source_common_config.py
git commit -m "feat(config): 书源配置新增用户层 common 层（能力段仍优先）"
```

---

### Task 2: PUT 写 common（含清理同名键）+ GET 暴露 user_overrides

**Files:**
- Modify: `backend/routers/config.py:107-146`（`save_source_config`）、`:86-104`（`get_source_config`）
- Test: `tests/test_source_common_routes.py`（新建）

**Interfaces:**
- Consumes: `config_service.load_yaml` / `save_yaml` / `deep_merge` / `CONFIG_DIR`、`require_known_source`
- Produces:
  - `PUT /api/v2/config/sources/{name}` 的 body 支持顶层 `common`（`{k: null}` = 删键）
  - `GET /api/v2/config/sources/{name}` 响应新增 `user_overrides: dict[str, list[str]]`（各能力段在用户层里实际出现的键，用于 UI 标「继承常规 / 已覆盖」）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_source_common_routes.py
"""PUT/GET 的 common 契约（spec: 2026-10-14-source-common-config-design.md）。"""
import asyncio
import yaml

from backend.routers import config as cfg_router
from backend.services import source_guard


def _setup(tmp_path, monkeypatch, initial: dict | None = None):
    monkeypatch.setattr(cfg_router.config_service, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(source_guard, "list_sources", lambda: ["demo-api-default"])
    (tmp_path / "sites").mkdir(parents=True, exist_ok=True)
    if initial is not None:
        (tmp_path / "sites" / "demo-api-default.yaml").write_text(
            yaml.safe_dump(initial, allow_unicode=True), encoding="utf-8")
    return tmp_path / "sites" / "demo-api-default.yaml"


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_put_common_writes_and_clears_capability_keys(tmp_path, monkeypatch):
    """写 common.key 时，各能力段里的 key 被删除（否则旧值优先、改了不生效）。"""
    path = _setup(tmp_path, monkeypatch, {
        "search": {"mode": "api", "key": "old"},
        "novel_info": {"mode": "api", "key": "old"},
    })
    asyncio.run(cfg_router.save_source_config("demo-api-default", {"common": {"key": "new"}}))
    data = _load(path)
    assert data["common"]["key"] == "new"
    assert "key" not in data["search"]
    assert "key" not in data["novel_info"]
    assert data["search"]["mode"] == "api"          # 其它键不受影响


def test_put_common_null_deletes_key(tmp_path, monkeypatch):
    """{common: {k: null}} 删除该键。"""
    path = _setup(tmp_path, monkeypatch, {"common": {"timeout": 30, "key": "x"}})
    asyncio.run(cfg_router.save_source_config("demo-api-default", {"common": {"key": None}}))
    data = _load(path)
    assert "key" not in data["common"]
    assert data["common"]["timeout"] == 30


def test_get_reports_user_overrides(tmp_path, monkeypatch):
    """GET 返回各能力段在用户层实际出现的键。"""
    _setup(tmp_path, monkeypatch, {"common": {"key": "x"},
                                   "search": {"mode": "api", "delay": [1, 1]}})
    monkeypatch.setattr(cfg_router, "effective_capabilities", lambda n: {"search": "api"})
    monkeypatch.setattr(cfg_router, "capabilities", lambda n: {"search": "api"})
    monkeypatch.setattr(cfg_router.config_service, "merged_source_config",
                        lambda n: {"search": {"mode": "api"}})
    monkeypatch.setattr(cfg_router.config_service, "source_concurrency", lambda n: 1)
    monkeypatch.setattr(cfg_router.config_service, "source_group", lambda n: "")
    monkeypatch.setattr(cfg_router.config_service, "source_alias", lambda n: "")
    out = asyncio.run(cfg_router.get_source_config("demo-api-default"))
    assert out["user_overrides"]["search"] == ["delay", "mode"]
    assert out["user_overrides"].get("novel_info") in (None, [])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_source_common_routes.py -q`
Expected: FAIL —— `test_put_common_writes_and_clears_capability_keys` 断言 `data["common"]` 不存在（KeyError）

- [ ] **Step 3: 实现 PUT 的 common 处理**

在 `save_source_config` 处理完顶层 `concurrency`/`source_group`/`source_alias` 之后、`cfg_body` 之前插入：对 `body.get("common")` 中的每个键 —— `None` → `existing["common"].pop(k)` 且空 dict 时删除 `common` 自身；有值 → 写入 `existing["common"]`，并遍历 `existing` 中其它能力段（键在 `("common","concurrency","source_group","source_alias","enabled")` 之外且值是 dict 的项）执行 `pop(k, None)`。

- [ ] **Step 4: 实现 GET 的 user_overrides**

在 `get_source_config` 的返回里加 `"user_overrides"`：读 `config_service.load_yaml(config_service.CONFIG_DIR / "sites" / f"{source_name}.yaml")`，对每个 dict 型能力段取 `sorted(键名)`（排除 `mode`）。

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/test_source_common_routes.py -q`
Expected: 3 passed

- [ ] **Step 6: 跑既有后端测试**

Run: `python -m pytest tests/test_site_config.py tests/test_backend_config_routes.py -q`
Expected: 全部 passed

- [ ] **Step 7: Commit**

```bash
git add backend/routers/config.py tests/test_source_common_routes.py
git commit -m "feat(api): 书源配置支持写 common（同步清理各能力段同名键）并暴露 user_overrides"
```

---

### Task 3: `converge` 端点（收敛各段一致的键）

**Files:**
- Modify: `backend/routers/config.py`（`get_source_config` 增 `converge_candidates`；新增 `POST /sources/{source_name}/converge`）
- Test: `tests/test_source_common_routes.py`（追加）

**Interfaces:**
- Consumes: Task 2 的 `user_overrides` 取法（同一份"读用户层"逻辑应抽成一个模块级私有函数 `_user_sections(source_name) -> dict[str, dict]`，供 GET / converge 共用）
- Produces:
  - `GET` 响应新增 `converge_candidates: list[dict]`（元素形如 `{"key": "key", "value": "oiapi-x"}`）
  - `POST /api/v2/config/sources/{name}/converge` → `{"status": "ok", "converged": [...], "kept": [...]}`

- [ ] **Step 1: 写失败测试**

```python
def test_converge_moves_identical_keys_to_common(tmp_path, monkeypatch):
    """全部能力段都有且取值相同的键 → 搬到 common 并从各段删除。"""
    path = _setup(tmp_path, monkeypatch, {
        "search": {"timeout": 30}, "novel_info": {"timeout": 30},
        "chapter_list": {"timeout": 30}, "chapter_content": {"timeout": 30, "delay": [9, 9]},
    })
    out = asyncio.run(cfg_router.converge_source_config("demo-api-default"))
    data = _load(path)
    assert data["common"]["timeout"] == 30
    assert all("timeout" not in data.get(c, {}) for c in
               ("search", "novel_info", "chapter_list", "chapter_content"))
    assert data["chapter_content"]["delay"] == [9, 9]     # 不一致的键原地保留
    assert "timeout" in [c["key"] for c in out["converged"]]
    assert "delay" in [c["key"] for c in out["kept"]]


def test_converge_keeps_partial_coverage_keys(tmp_path, monkeypatch):
    """只出现在部分能力段的键不收敛（否则其余段会从继承出厂变成继承 common）。"""
    path = _setup(tmp_path, monkeypatch, {"search": {"key": "x"}, "novel_info": {"key": "x"}})
    asyncio.run(cfg_router.converge_source_config("demo-api-default"))
    data = _load(path)
    assert "common" not in data or "key" not in data.get("common", {})
    assert data["search"]["key"] == "x"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_source_common_routes.py -q`
Expected: FAIL —— `AttributeError: module ... has no attribute 'converge_source_config'`

- [ ] **Step 3: 实现 `_user_sections` + `converge_candidates` + `converge_source_config`**

`_user_sections`：读用户层 yaml，返回 `{cap: dict}`（排除 `common` 与顶层元信息键）。
`converge_candidates`：对每个键统计"出现在哪些能力段"——只有**出现在全部能力段且取值全相同**才入选。
`converge_source_config`：按同一条件把键写入 `existing["common"]` 并从各段 `pop`；其余键进 `kept`；写回 yaml 后返回三个列表。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_source_common_routes.py -q`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/config.py tests/test_source_common_routes.py
git commit -m "feat(api): 新增书源配置 converge（仅收敛各能力段一致且全覆盖的键）"
```

---

### Task 4: 前端「常规」段 + 能力段默认收起

**Files:**
- Modify: `frontend/src/features/sources/sourceConfigForm.tsx:131-274`（`SourceConfigEditor`）
- Modify: `frontend/src/features/sources/sourceConfigFields.ts`（新增 `commonFieldsFor(modes)` 纯函数）
- Modify: `frontend/src/features/sources/SourceAccordion.tsx`（书源标题按钮加 `data-testid={`source-${name}`}`，供冒烟定位）
- Modify: `frontend/src/api/endpoints.ts`（`SourceConfig` 类型加 `user_overrides` / `converge_candidates`）
- Modify: `scripts/ui_smoke.py`（追加常规段/折叠断言）

**Interfaces:**
- Consumes: Task 2/3 的 `user_overrides` / `converge_candidates` / `POST …/converge`；既有 `useSourceConfig` / `useSaveSourceConfig` / `ENGINE_FIELDS` / `CAP_LABELS`
- Produces:
  - `commonFieldsFor(modes: string[]): EngineField[]`（`sourceConfigFields.ts`，纯函数：取各 mode 字段的 `key` 交集，去掉 `mode`）
  - 常规段容器带 `data-testid="source-common"`；每个能力段标题按钮带 `data-testid={`cap-${cap}`}`，展开区带 `data-testid={`cap-${cap}-body`}`

- [ ] **Step 1: 写失败测试（冒烟断言）**

在 `scripts/ui_smoke.py` 的 `browser.close()` 之前追加（**只用 `data-testid` 锚定，不取页面通用文案** —— Review Focus #5）：

```python
        # 附加 5（书源「常规」段 + 能力段默认收起）
        cfg = browser.new_page(viewport={"width": 1280, "height": 900})
        cfg.goto(args.base_url + "/settings/sources", wait_until="domcontentloaded")
        src_buttons = cfg.locator('[data-testid^="source-"]')
        if src_buttons.count() == 0:
            failures.append("失败 书源列表未渲染（[data-testid^=source-] 为空）")
        else:
            src_buttons.first.click()
            common = cfg.locator('[data-testid="source-common"]')
            try:
                common.wait_for(state="visible", timeout=8000)
                print("完成 书源展开后「常规」段可见")
            except Exception:
                failures.append("失败 书源展开后未出现 [data-testid=source-common]")
            cap_body = cfg.locator('[data-testid="cap-search-body"]')
            if cap_body.count() > 0 and cap_body.first.is_visible():
                failures.append("失败 能力段「搜索」默认应为收起，实际可见")
            else:
                print("完成 能力段默认收起")
            cfg.locator('[data-testid="cap-search"]').first.click()
            try:
                cap_body.first.wait_for(state="visible", timeout=8000)
                print("完成 点击后能力段可展开")
            except Exception:
                failures.append("失败 点击能力段标题后其内容区仍未可见")
        cfg.screenshot(path=str(out / "settings-source-common.png"), full_page=True)
        cfg.close()
```

- [ ] **Step 2: 跑脚本确认失败**

Run: `python scripts/ui_smoke.py`（需先 `cd frontend && npm run build`，并起 `npx vite preview --port 4173`）
Expected: FAIL —— 未找到 `[data-testid="source-common"]`

- [ ] **Step 3: 实现 `commonFieldsFor` + 常规段 + 能力段折叠**

`commonFieldsFor`：`ENGINE_FIELDS[m]` 的 `key` 集合求交（`modes` 为空 → `[]`），映射回字段对象，过滤 `key === "mode"`。
`SourceConfigEditor`：在 `并发数` 之后渲染常规段（`useState` 控制展开，默认 true），字段值取 `merged[该 mode]`；能力段改为 `useState` 记录各段展开状态（默认全 false），标题按钮点击切换，body 仅展开时渲染；被 `user_overrides[cap]` 含有的键在常规段字段旁显示「已在 <能力> 单独设置」提示，在能力段里对这些键显示「已覆盖」、其余共享字段显示「继承常规」。

- [ ] **Step 4: 跑脚本确认通过**

Run: `python scripts/ui_smoke.py`
Expected: 含常规段与折叠三条断言全部「完成」，退出码 0

- [ ] **Step 5: 类型检查 + lint + 既有断言回归**

Run: `cd frontend && npx tsc -b && npm run lint && npm run build`，再 `python scripts/ui_smoke.py`
Expected: 0 错 / 0 告警 / 原有 15 条断言仍全绿

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/sources/sourceConfigForm.tsx frontend/src/features/sources/sourceConfigFields.ts frontend/src/api/endpoints.ts scripts/ui_smoke.py
git commit -m "feat(settings): 书源配置新增「常规」段、能力段默认收起（共享字段只填一次）"
```

---

## 中间态安全性（执行顺序的依据）

后端（Task 1-3）先合并是**安全**的：老前端仍逐能力段写入，用户层 yaml 里根本没有 `common` 键 → 新增的合并层等价于空 → 合并结果与改动前逐字一致；`GET` 多出的两个字段对老前端是无害的额外字段；`converge` 没有 UI 入口也就不会被调用。反向（前端先做）则不行 —— 前端要用 `user_overrides`，所以顺序固定为 **后端 → 前端**。

## Self-Review

**Spec coverage**：§3 数据模型/优先级 → Task 1；§4 写入语义与收敛 → Task 2、Task 3；§5 字段集算法 → Task 4（`commonFieldsFor`）；§6 UI 形态 → Task 4；§7 API 变更 → Task 2、Task 3；§8 兼容边界 → Task 1（`test_absent_common_is_noop`）、Task 2（`enabled` 清理与顶层字段不受影响）；§9 测试策略 → 各任务的测试步骤。
**未纳入**：spec §10 的非目标（`common` 支持 mode、常规字段「恢复默认」入口、展开状态持久化）。
