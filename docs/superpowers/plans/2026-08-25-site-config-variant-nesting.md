# sites 配置嵌套 variant 层（browser/requests 加 default）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `sites/{platform}.yaml` 的 browser/requests 嵌套一层 variant（当前唯一 `default`），所有配置读取方（shared/cli/backend/前端）改为 variant 感知，与书源代码层 `{mode}/{variant}/` 结构对齐。

**Architecture:** 在 `shared/config.py`（配置单一数据源）新增 variant 感知辅助函数 `get_mode_variant_config` / `load_mode_config` / `mode_variants`，所有消费方统一改用辅助函数；配置文件更新为新格式；前端最小适配（读 `.default`、写 `default` 层）。

**Tech Stack:** Python 3.10+（pytest、PyYAML）、FastAPI、React 18 + TypeScript

## Global Constraints

- **只支持新格式**：不兼容旧的扁平 `browser:`/`requests:` 结构；老配置需手动删除由 `init_config` 重新生成
- **variant 感知语义**：variant 缺省时优先 `default`，无 `default` 取第一个 dict 值（与 `novelbase/source.resolve` 对齐）
- **提交约定**：中文提交消息、一个方面一条 commit、禁止 `git add -A`（显式 add）、dev 分支可自动提交推送
- **文档位置**：设计文档在根 `docs/superpowers/specs/2026-08-25-site-config-variant-nesting-design.md`，计划在根 `docs/superpowers/plans/`（均不入 git 仓库）
- **测试环境**：本机无 python，测试用 Docker 运行 pytest（镜像/命令执行时确认，如 `nld-test:3.11` 或 `python:3.11-slim` + 依赖安装）
- **前端验证**：`npx tsc --noEmit --project tsconfig.app.json`（node 本机可用）

---

### Task 1: shared/config.py 数据访问层（辅助函数 + 存量函数适配）

**Files:**
- Create: `tests/test_site_config.py`
- Modify: `shared/config.py`（`load_platform_configs` 附近新增辅助函数；`find_variant_options`、`load_platform_configs`、`build_options` 改用）

**Interfaces:**
- Consumes: 无（第一个任务）
- Produces（后续任务依赖的签名）:
  - `get_mode_variant_config(site_cfg: dict, mode: str, variant: str | None = None) -> dict` —— `site_cfg[mode][variant]`；variant=None → 优先 `default` → 否则第一个 dict 值；非 dict 结构返回 `{}`
  - `load_mode_config(platform: str, mode: str, variant: str | None = None) -> dict` —— `load_site_config(platform)` + `get_mode_variant_config`
  - `mode_variants(site_cfg: dict, mode: str) -> list[str]` —— 某 mode 下的 variant 名列表（仅 dict 值）
  - `find_variant_options(variant: str) -> dict | None` —— 扩展为跨 mode 查找（api → browser → requests），返回第一个匹配的 dict

- [ ] **Step 1: 写失败测试**

新建 `tests/test_site_config.py`：

```python
"""site 配置 variant 感知辅助函数测试。"""
import pytest

from shared.config import (
    get_mode_variant_config, mode_variants, load_mode_config,
)


def _site():
    return {
        "browser": {"default": {"headless": False, "timeout": 30}},
        "requests": {"default": {"timeout": 30}},
        "api": {"oiapi": {"key": ""}, "rain": {"key": ""}},
    }


def test_get_mode_variant_config_default():
    assert get_mode_variant_config(_site(), "browser") == {"headless": False, "timeout": 30}


def test_get_mode_variant_config_named():
    assert get_mode_variant_config(_site(), "api", "rain") == {"key": ""}


def test_get_mode_variant_config_first_when_no_default():
    site = {"browser": {"alpha": {"a": 1}, "beta": {"b": 2}}}
    assert get_mode_variant_config(site, "browser") == {"a": 1}


def test_get_mode_variant_config_non_dict_returns_empty():
    assert get_mode_variant_config({"browser": {"default": "scalar"}}, "browser") == {}
    assert get_mode_variant_config({"browser": None}, "browser") == {}
    assert get_mode_variant_config({}, "browser") == {}


def test_mode_variants_lists_dict_keys_only():
    assert mode_variants(_site(), "browser") == ["default"]
    assert mode_variants(_site(), "api") == ["oiapi", "rain"]
    assert mode_variants({"browser": {"default": "scalar"}}, "browser") == []


def test_load_mode_config(tmp_path, monkeypatch):
    import shared.config as sc
    site_file = tmp_path / "sites" / "fanqie.yaml"
    site_file.parent.mkdir(parents=True)
    site_file.write_text(
        "browser:\n  default:\n    timeout: 42\n", encoding="utf-8")
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    assert load_mode_config("fanqie", "browser") == {"timeout": 42}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_site_config.py -v`
Expected: FAIL（`get_mode_variant_config` 不存在 / ImportError）

- [ ] **Step 3: 实现辅助函数并适配存量函数**

在 `shared/config.py` 的 `load_platform_raw` / `find_variant_options` 附近新增：

```python
def get_mode_variant_config(site_cfg, mode, variant=None) -> dict:
    """取 site 配置中某 mode 的 variant 配置。

    variant=None → 优先 "default"，无 "default" 取第一个 dict 值。
    非 dict 结构（扁平旧格式/标量）一律返回 {}（只支持新格式）。
    """
    mode_section = site_cfg.get(mode, {}) if isinstance(site_cfg, dict) else {}
    if not isinstance(mode_section, dict):
        return {}
    if variant is not None and variant in mode_section:
        cfg = mode_section[variant]
        return cfg if isinstance(cfg, dict) else {}
    if "default" in mode_section:
        cfg = mode_section["default"]
        return cfg if isinstance(cfg, dict) else {}
    for v, cfg in mode_section.items():
        if isinstance(cfg, dict):
            return cfg
    return {}


def load_mode_config(platform, mode, variant=None) -> dict:
    """从 sites/{platform}.yaml 加载某 mode 的 variant 配置（含 app_data 路径解析）。"""
    site = load_site_config(platform)
    return get_mode_variant_config(site, mode, variant)


def mode_variants(site_cfg, mode) -> list[str]:
    """返回某 mode 下的 variant 名列表（仅 dict 值）。"""
    mode_section = site_cfg.get(mode, {}) if isinstance(site_cfg, dict) else {}
    if not isinstance(mode_section, dict):
        return []
    return [k for k, v in mode_section.items() if isinstance(v, dict)]
```

`find_variant_options` 改为跨 mode（api → browser → requests）：

```python
def find_variant_options(variant):
    sites_dir = CONFIG_DIR / "sites"
    if not sites_dir.is_dir():
        return None
    for p in sites_dir.glob("*.yaml"):
        site = load_yaml(p)
        for mode in ("api", "browser", "requests"):
            cfg = get_mode_variant_config(site, mode, variant)
            if cfg:
                return cfg
    return None
```

`load_platform_configs` 的 browser/requests 分支改为 variant 容器：

```python
def load_platform_configs():
    result = {}
    sites_dir = CONFIG_DIR / "sites"
    if not sites_dir.is_dir():
        return result
    for p in sites_dir.glob("*.yaml"):
        platform = p.stem
        raw = load_yaml(p)
        entry = {}
        for mode in ("browser", "requests"):
            entry[mode] = {
                v: deep_merge(ENGINE_DEFAULTS[mode], get_mode_variant_config(raw, mode, v))
                for v in mode_variants(raw, mode)
            }
        api_section = raw.get("api", {}) if isinstance(raw.get("api"), dict) else {}
        entry["api"] = {k: v for k, v in api_section.items() if isinstance(v, dict)}
        entry["api_variants"] = list(entry["api"].keys())
        result[platform] = entry
    return result
```

`shared/config.py` 的 `build_options`（遗留，现无调用者）browser/requests 分支改用辅助：

```python
    if mode == "browser":
        browser_cfg = get_mode_variant_config(site_cfg, "browser")
        # ... 其余不变
    elif mode == "requests":
        req_cfg = get_mode_variant_config(site_cfg, "requests")
        # ... 其余不变
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_site_config.py -v`
Expected: PASS（6 个用例全过）

- [ ] **Step 5: 提交**

```bash
git add tests/test_site_config.py shared/config.py
git commit -m "feat: shared.config 新增 variant 感知辅助（get_mode_variant_config/load_mode_config/mode_variants），find_variant_options 跨 mode 查找"
```

---

### Task 2: 配置文件嵌套 default（template + app_data）

**Files:**
- Modify: `template/config/sites/fanqie.yaml`、`template/config/sites/qidian.yaml`、`template/config/sites/qimao.yaml`、`template/config/sites/92xs.yaml`
- Modify: `app_data/config/sites/fanqie.yaml`、`app_data/config/sites/qidian.yaml`、`app_data/config/sites/qimao.yaml`、`app_data/config/sites/92xs.yaml`（本地运行/测试用，**不进 git**）

**Interfaces:**
- Consumes: Task 1 的 `load_mode_config`（Step 2 用它验证）
- Produces: 新格式 site yaml（browser/requests 嵌套 `default`；api 不变）

- [ ] **Step 1: 更新 template 配置文件**

对 4 个 `template/config/sites/*.yaml`，把顶层 `browser:` 与 `requests:` 的内容整体缩进一层并包在 `default:` 下；`api:` 保持原样。

以 `template/config/sites/fanqie.yaml` 为例，改前：

```yaml
api:
  oiapi: {...}
  rain: {...}
browser:
  backoff_factor: 2
  browser_type: chromium
  delay: [2, 5]
  headless: false
  retry_times: 3
  timeout: 30
  user_data_dir: app_data\browser\Chromium\User Data
  viewport: {height: 720, width: 1280}
requests:
  backoff_factor: 2
  cookies: {}
  delay: [3, 5]
  headers: {...}
  proxies: {}
  retry_times: 3
  timeout: 30
```

改后（仅 browser/requests 部分，api 原样）：

```yaml
api:
  oiapi: {...}
  rain: {...}
browser:
  default:
    backoff_factor: 2
    browser_type: chromium
    delay: [2, 5]
    headless: false
    retry_times: 3
    timeout: 30
    user_data_dir: app_data\browser\Chromium\User Data
    viewport: {height: 720, width: 1280}
requests:
  default:
    backoff_factor: 2
    cookies: {}
    delay: [3, 5]
    headers: {...}
    proxies: {}
    retry_times: 3
    timeout: 30
```

其余 3 个平台（qidian/qimao/92xs）同样处理（92xs 只有 requests，无 browser/api 段则不动该段）。

- [ ] **Step 2: 同步 app_data 配置并验证加载**

把同样的嵌套结构应用到 `app_data/config/sites/*.yaml`（保持用户本地值，仅加 default 层）。

用 Docker 跑 pytest 验证（需要 `shared`、`novelbase`、依赖已装；或直接 py_compile + 下一条 Task 3 的引擎测试兜底）：

Run: `pytest tests/test_site_config.py -v`
Expected: PASS（`test_load_mode_config` 与真实 app_data 无关，此步为结构一致性人工核对）

同时人工核对：`shared.config.load_site_config` 返回的每个平台 yaml 中 `browser.default` / `requests.default` 均为 dict。

- [ ] **Step 3: 提交**

```bash
git add template/config/sites/fanqie.yaml template/config/sites/qidian.yaml template/config/sites/qimao.yaml template/config/sites/92xs.yaml
git commit -m "feat: sites 配置 browser/requests 嵌套 default variant 层（template 4 平台）"
```

> 注：`app_data/` 被 git 忽略，不进 commit。

---

### Task 3: CLI 适配（build_options + 交互菜单）

**Files:**
- Modify: `cli/config.py`（`build_options` 的 browser/requests 分支）
- Modify: `cli/menus.py`（`_settings_site_browser`、`_settings_site_requests`、`_get_delay`、`_set_delay`）
- Modify: `tests/test_interactive_cli.py`（`_get_delay` 断言数据）

**Interfaces:**
- Consumes: Task 1 的 `get_mode_variant_config`（`from shared.config import ...`）
- Produces: `cli.config.build_options(cfg, site_cfg)` 对嵌套结构返回正确 Options；CLI 交互菜单读写 default variant

- [ ] **Step 1: 改失败测试（交互菜单延迟读写）**

`tests/test_interactive_cli.py` 约 194-201 行，改断言数据为嵌套结构：

```python
        site_cfg = {"browser": {"default": {"delay": [1, 2]}}}
        assert _get_delay(site_cfg, "browser") == (1.0, 2.0)
        _set_delay(site_cfg, "browser", 0.5, 1.5)
        assert _get_delay(site_cfg, "browser") == (0.5, 1.5)
        assert _get_delay({}, "requests") == (3.0, 6.0)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_interactive_cli.py -k delay -v`
Expected: FAIL（`_get_delay` 从扁平结构取不到 delay，返回默认 (3,6)）

- [ ] **Step 3: 实现 CLI 适配**

`cli/config.py` 顶部 import 增加：

```python
from shared.config import get_mode_variant_config
```

`build_options` 的 browser/requests 分支：

```python
    if mode == "browser":
        browser_cfg = get_mode_variant_config(site_cfg, "browser")
        # ... 其余逻辑不变
    elif mode == "requests":
        req_cfg = get_mode_variant_config(site_cfg, "requests")
        # ... 其余逻辑不变
```

`cli/menus.py`：

```python
def _settings_site_browser(cfg, site_cfg):
    browser = site_cfg.setdefault("browser", {}).setdefault("default", {})
    # ... 其余逻辑不变

def _settings_site_requests(cfg, site_cfg):
    req = site_cfg.setdefault("requests", {}).setdefault("default", {})
    # ... 其余逻辑不变

def _get_delay(site_cfg, mode):
    section = site_cfg.get(mode, {}).get("default", {})
    delay = section.get("delay", (3, 6))
    if isinstance(delay, list):
        delay = tuple(delay)
    return delay[0], delay[1]

def _set_delay(site_cfg, mode, lo, hi):
    site_cfg.setdefault(mode, {}).setdefault("default", {})["delay"] = [lo, hi]
```

（`_settings_site_requests` 原实现若用 `site_cfg.setdefault("requests", {})` 局部变量，改同上；api 菜单 `_settings_site_api` 不动。）

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_interactive_cli.py -v`
Expected: PASS（含 delay 相关用例）

- [ ] **Step 5: 提交**

```bash
git add cli/config.py cli/menus.py tests/test_interactive_cli.py
git commit -m "refactor: CLI 配置读取改 variant 感知（build_options/交互菜单读写 default variant）"
```

---

### Task 4: Backend 适配（engine_manager + config 路由）

**Files:**
- Modify: `backend/services/engine_manager.py`（`_fingerprint`、`create_engine_for_request`）
- Modify: `backend/routers/config.py`（`get_site`、`save_site`）

**Interfaces:**
- Consumes: Task 1 的 `get_mode_variant_config`、`mode_variants`
- Produces: `create_engine_for_request(platform, mode, variant)` 对嵌套结构正确建引擎；`GET/PUT /api/v2/config/sites/{platform}` 透传嵌套结构

- [ ] **Step 1: 更新 engine_manager**

`backend/services/engine_manager.py` 顶部 import：

```python
from shared.config import load_site_config, find_variant_options, get_mode_variant_config
```

`_fingerprint` browser 分支：

```python
    if mode == "browser":
        site = load_site_config(platform)
        mode_cfg = get_mode_variant_config(site, mode, variant)
        vp = mode_cfg.get("viewport")
        raw = (
            f"{platform}|{mode}|{mode_cfg.get('browser_type','chromium')}|"
            f"{mode_cfg.get('user_data_dir','')}|"
            f"{json.dumps(vp, sort_keys=True) if vp else ''}|"
            f"{mode_cfg.get('headless', True)}"
        )
```

`create_engine_for_request`：

```python
    site = load_site_config(platform)
    mode_cfg = get_mode_variant_config(site, mode, variant)
    _cfg = lambda k, default=None: mode_cfg.get(k, default)
```

（API 分支逻辑不变，仍走 `find_variant_options`；`mode_cfg` 对 API 返回 `{}`，但 API 分支提前 return，不冲突。）

- [ ] **Step 2: 更新 config 路由**

`backend/routers/config.py` 的 `get_site`：

```python
@router.get("/sites/{website}")
async def get_site(website: str):
    raw = config_service.load_yaml(_cfg_dir / "sites" / f"{website}.yaml")
    entry: dict = {}
    for mode in ("browser", "requests"):
        entry[mode] = {
            v: config_service.deep_merge(
                config_service.ENGINE_DEFAULTS[mode],
                config_service.get_mode_variant_config(raw, mode, v),
            )
            for v in config_service.mode_variants(raw, mode)
        }
    api_section = raw.get("api", {}) if isinstance(raw.get("api"), dict) else {}
    entry["api"] = {k: v for k, v in api_section.items() if isinstance(v, dict)}
    entry["api_variants"] = list(entry["api"].keys())
    return entry
```

`save_site` 的 browser/requests 分支：

```python
    for mode in ("browser", "requests"):
        if mode in body and isinstance(body[mode], dict):
            existing_mode = existing.get(mode, {}) if isinstance(existing.get(mode), dict) else {}
            for v, cfg in body[mode].items():
                if isinstance(cfg, dict):
                    existing_mode[v] = config_service.deep_merge(
                        existing_mode.get(v, {}), cfg,
                    )
            existing[mode] = existing_mode
```

- [ ] **Step 3: 验证**

Run: `pytest tests/test_engine_manager.py tests/test_cli_storage.py -v`
Expected: PASS（engine fingerprint/创建走真实 app_data 新格式配置）

Run: `python -m py_compile backend/services/engine_manager.py backend/routers/config.py`（Docker）
Expected: 无语法错误

- [ ] **Step 4: 提交**

```bash
git add backend/services/engine_manager.py backend/routers/config.py
git commit -m "refactor: backend 引擎创建与 config 路由改 variant 感知（sites 配置嵌套 default）"
```

---

### Task 5: 前端适配（类型 + 设置页表单）

**Files:**
- Modify: `frontend/src/api/endpoints.ts`（`SiteConfig` 类型）
- Modify: `frontend/src/features/settings/SettingsPage.tsx`（`engineCfg` 读取、`updateField` 保存）

**Interfaces:**
- Consumes: backend `GET/PUT /api/v2/config/sites/{platform}` 的嵌套结构（browser/requests 为 `{default: {...}}`）
- Produces: 设置页 browser/requests 表单读 `.default`、保存写 `default` 层

- [ ] **Step 1: 更新类型**

`frontend/src/api/endpoints.ts` 第 76-79 行：

```ts
export interface SiteConfig {
  browser: Record<string, EngineOptions>; requests: Record<string, EngineOptions>; api: Record<string, EngineOptions>;
  api_variants: string[];
}
```

（`EngineOptions` 保持原样；若 `EngineOptions` 已含 `[key: string]: unknown` 索引签名则无需动。）

- [ ] **Step 2: 更新 SettingsPage 读取与保存**

`frontend/src/features/settings/SettingsPage.tsx`：

第 164 行附近，`engineCfg` 改为 browser/requests 取 `default`：

```ts
  const rawModeCfg = (siteCfg?.[mode as keyof SiteConfig] as Record<string, unknown> | undefined) ?? {};
  // browser/requests 是 variant 容器，表单操作 default variant；api 保持 variant 容器原样
  const engineCfg = (mode === "api"
    ? rawModeCfg
    : ((rawModeCfg.default as Record<string, unknown> | undefined) ?? {}));
```

第 181-183 行，`updateField` 保存加 `default` 层（只服务 browser/requests 字段，api 走 `ApiVariantsSection`）：

```ts
  const updateField = useCallback((key: string, value: unknown) => {
    saveSite.mutate({ [mode]: { default: { [key]: value } } });
  }, [mode, saveSite]);
```

`ApiVariantsSection` 及其调用（第 229-231 行 `hasVariants`/`engineCfg` 传参）不动。

- [ ] **Step 3: 类型检查**

Run: `cd frontend && npx tsc --noEmit --project tsconfig.app.json`
Expected: 无类型错误

- [ ] **Step 4: 提交**

```bash
git add frontend/src/api/endpoints.ts frontend/src/features/settings/SettingsPage.tsx
git commit -m "feat: 前端设置页适配 sites 配置嵌套 variant（browser/requests 读写 default）"
```

---

### Task 6: 全量验证 + 文档

**Files:**
- Modify: `docs/project/config.md`（根 docs/，不进 git）
- Verify: 全量 pytest + 前端 tsc

**Interfaces:**
- Consumes: 全部前序任务
- Produces: 重构完成证据

- [ ] **Step 1: 全量后端测试**

Run: `pytest tests/ -v --tb=short`（Docker）
Expected: 全量通过（参考基线：280 passed / 2 skipped）

- [ ] **Step 2: 前端类型检查**

Run: `cd frontend && npx tsc --noEmit --project tsconfig.app.json`
Expected: 无类型错误

- [ ] **Step 3: 更新文档**

根 `docs/project/config.md` 第 14-16 行的 `sites/*.yaml` 说明改为：

```markdown
## sites/*.yaml

每个平台三个引擎段的配置（api/browser/requests）。api 为 variant 容器（如 `api.oiapi`/`api.rain`）；
browser/requests 也嵌套一层 variant（当前唯一 `default`，如 `browser.default.headless`）。
字段含 delay、retry_times、timeout、backoff_factor。fanqie 的 `api.oiapi.enabled` 设为 false。
```

（文档在根 `docs/`，不入 git 仓库，无需提交。）

- [ ] **Step 4: 收尾确认**

Run: `git status --short`
Expected: 干净（无未提交改动）

确认工作区所有必要文件已提交，向用户汇报：改动文件清单、测试结果、app_data 需删除旧配置由 init_config 重新生成的提示。

---

## 自审记录

- **Spec 覆盖**：配置文件嵌套（Task 2）✓；数据访问层辅助（Task 1）✓；cli/config + menus（Task 3）✓；engine_manager + config 路由（Task 4）✓；前端 endpoints + SettingsPage（Task 5）✓；测试与文档（Task 1/3/6）✓；明确不做的部分（前端 variant UI、旧格式兼容）未纳入任务 ✓
- **占位扫描**：无 TBD/TODO；每步含实际代码
- **类型一致性**：`get_mode_variant_config(site_cfg, mode, variant=None) -> dict`、`load_mode_config(platform, mode, variant=None) -> dict`、`mode_variants(site_cfg, mode) -> list[str]` 在 Task 1 定义，Task 3/4 按此签名使用；前端 `engineCfg` 读取与 `updateField` 保存键路径（`[mode].default`）与后端 `get_site`/`save_site` 返回/接收结构一致
