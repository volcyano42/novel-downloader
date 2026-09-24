# 书源扁平化重构（core 层）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `novelbase` 的书源发现/分发从「四层目录 `{platform}/{mode}/{variant}/{capability}.py`」改为「一层书源目录 + `source.json`」，并让 `downloader` 的 API 以 `source_name` 为键、`mode` 从入参变为出参。

**Architecture:** 每个书源是一个目录，内含一个空 `__init__.py`、一个 `source.json`（身份 + 出厂配置）与 4 个能力文件（`search.py` / `novel_info.py` / `chapter_list.py` / `chapter_content.py`）。`novelbase/source.py` 只暴露 4 个函数：`list_sources()` / `get_manifest(source_name)` / `capabilities(source_name) -> dict[capability, mode]` / `resolve(source_name, capability) -> (fn, mode)`。`downloader` 的 4 个下载函数接收 `source_name`（搜索接收一组 `source_name`）与一个「按 mode 取引擎」的解析器 `engines`。

**Tech Stack:** Python 3.11+、`importlib`、`json`、`dataclasses`、`inspect.signature`、pytest。

**Scope（2026-09-25 修订）**：本计划是 5 份计划的第 1 份，但**验收口径已扩大**（用户 2026-09-24 拍板）：

1. **验收标准 = `python -m pytest tests/ -q` 全绿**（基线实测 `313 passed, 2 skipped in 3.79s`，无 Steam++ 拖慢）。原先「只改 `novelbase/`、`backend/cli/frontend` 是不可用中间态」的说法作废。
2. 范围扩到 `tests/` 下**所有受影响文件**，本计划结束时整个测试套件必须绿。
3. 由此产生「backend/cli 最小适配」：某些测试测的是 `backend/`/`cli/` 的旧 API（见 Task 10），光改测试无法变绿，需要**新增任务**做 `backend/`/`cli/` 的**最小适配改造**（让调用点走新 API）。这部分与 spec「非目标：后端/CLI 改造属后续计划」偏离，**用户已批准**，并在本计划显式标注为扩大后的范围。

> 中间态说明：Task 3（删旧四层目录）之后、Task 8/9/10 之前，`tests/test_source_contracts.py`、`tests/test_source_async.py`、`tests/test_browser_sources.py`、`tests/test_interactive_cli.py`、`tests/test_cli_variant.py` 会处于红状态（它们仍 import 旧路径/旧 API）。这是**有意为之**的一次性切换窗口，各任务只跑指定子集；Task 11 才跑全量并收绿。

---

## 修订记录（2026-09-25）

- **验收口径改为 `pytest tests/ 全绿`**（用户 2026-09-24 拍板）；Scope 从「只改 novelbase/」扩到「tests/ 所有受影响文件 + backend/cli 最小适配」。
- **任务顺序重排**：`SearchResult.source_name` 字段定义（原 Task 8 前半）提前到 downloader 新签名（原 Task 7）之前，消除原自审记录里「Task 7 用 Task 8 才定义的字段」的循环依赖；删 platform_from_url/register_source 的独立任务（原 Task 6）并入 source.py 重写。
- **新增任务**：Task 8（test_source_contracts 全量重写）、Task 9（test_source_async / test_browser_sources 的 import 路径迁移）、Task 10（backend/cli 最小适配 + test_interactive_cli / test_cli_variant）。
- **删除原 Task 1 能力矩阵快照**：旧结构 `capabilities(name)` 是平台级 `{mode:{variant}}`，压平 `{capability: mode}` 有损（fanqie 的 search 同时存在于 api/browser/requests），无法精确对照；改为 Task 3 用写死的 10 行 mode 归属表做真断言。
- **修正 source_name 取值**：`list_sources()/get_manifest()/capabilities()/resolve()` 一律以 `source.json` 的 `source_name`（连字符，如 `fanqie-api-rain`）为键，目录名（下划线）只是磁盘位置；编译模式 `_manifest` 增 `SOURCE_DIRS` 映射。
- **清理自相矛盾**：新结构**不设 `_common.py`**、共享逻辑内联（spec 第 83 行）；Global Constraints 里「目录名必须是合法 Python 标识符」的真实理由是 `import_module("novelbase.sources.{dir}.{capability}")` 需要包标记 `__init__.py`，与 `from ._common import ...` 无关。
- **修正会崩的代码**：`resolve()` 编译分支里 `candidate` 未赋值会 `NameError`；`novelbase/__init__.py` 对 `downloader.get_source/list_sources` 的悬空导入。
- **行号核对**：`downloader` 的 `_normalize_mode/_variant_for` 调用点实为 121-122（resolve_meta）/150-151（resolve_chapter_list）/174-175（resolve_chapter）；`shared/config.py` 的 `set_api_options(name=...)` 实为 273-274。

**本轮（复核后）修订**（对应校验员 3 项未消除 + 12 项新发现）：

- **#1**：Task 4 Step 5 的 grep 改为只断言 `novelbase/source.py` 不再导出 `register_source`/`platform_from_url`，并把 `downloader.py` 的两处 `register_source` 引用显式列为 Task 6 待办。
- **#13**：Task 3 搬移改为「逐文件搬移 + 内联」，不再 `git mv` 整目录（避免把 `_helpers.py` 一并带过去）。
- **#14**：同步修正 spec 第 79 行的目录名理由措辞（spec 设计决策不变）。
- **新#1/#11**：新增 `backend/routers/download.py` 最小适配（顶层 `from novelbase.source import platform_from_url` 会让 `backend.main → server → test_android_server` 全红）。
- **新#2**：修 `resolve()` 纯私有源误走 `import_module`（改为内置/私有分流，私有走 `spec_from_file_location`）。
- **新#3/#10**：私有源测试目录名改下划线 `demo_requests_default`，`source_name` 保持连字符，与「目录名须合法标识符」一致。
- **新#6**：新增 `tests/test_novel_id_stability.py`（写死典型 url 的 `make_novel_id` 哈希 + 静态断言 92xs novel_info 不出现 `/html/` 规范化）。
- **新#7**：`get_manifest()` 非编译分支强制 `check_capability_files`（能力段 ⇔ `.py` 双向）；补 `source_name` 唯一性测试。
- **新#5**：修 Task 3 测试数（layout 21 例 + manifest 10 例 = 31 例，非 13 例）。
- **新#8**：明确 `engine_manager.py:138,189,212` 的 `set_api_options(name=)` 不会红（测试 monkeypatch/走 browser 分支，不触发 api 分支）。
- **新#9**：修交叉引用「Task 2 Step 2」→「Task 10 Step 2」及用例名。

**第三轮（终校验后）修订**：

- **M1**：`SearchResult(platform=...)` 构造点全库核实，只有 `92xs_requests_default/search.py:48` 传 `platform="92xs"`；Task 5 新增 Step 4b 删除该参数（`source_name` 由 downloader Task 6 统一打标，书源不写死）。
- **M2**：Task 11 总数修正为 313 − 13 + 46 = 346，删除/新增明细与总数一致。
- **low**：Task 10 Step 2 补 `do_search` 第 71 行 `_platform_from_url(query)`；`cli/core.py:59,251`、`cli/main.py:45,337` 函数内旧符号引用写明「无测试触发、顶层 import 不崩、留后续 CLI 计划」；Task 4 Step 5 grep 补 `exporter.py:11`/`build_manifest.py:64` 注释命中说明；spec:168 行号 149-150/173-174 → 150-151/174-175。

---

## Global Constraints

以下约束对每个任务都成立，值逐字取自设计文档 `docs/superpowers/specs/2026-09-24-book-source-flattening-design.md`：

- **不做旧结构兼容层**：旧的 `{platform}/{mode}/{variant}/` 目录、旧 `__init__.py` 里的 `NAME`/`SHOW_NAME`/`HOSTS` 约定、`platform_from_url()` 全部删除，不留 shim。
- **重构不得改变任何书源返回的 url**：`Novel.id = make_novel_id(novel.url) = sha256(url)[:32]`，`meta.id` 存该 url 原样。改变书源返回的 url = 已有书籍 id 漂移 = 书架/收藏/分组/阅读进度全部对不上。**尤其不要把 92xs 的 `/book/{id}.html` 「规范化」成 `/html/{id}/`。**
- **字段命名全链保持 `retry_times`**，不引入 `max_retry`。
- **目录名必须是合法 Python 标识符**（下划线形式），因为能力模块通过 `import_module("novelbase.sources.{dir}.{capability}")` 加载，`{dir}` 必须是合法标识符、且每个书源目录需要一个（空的）`__init__.py` 作包标记。**不设 `_common.py`**：书源各自独立、共享逻辑内联进需要它的能力文件（spec 第 83 行）。
- **`CAPABILITY_META` 保持 4 条**（`search` / `novel_info` / `chapter_list` / `chapter_content`），**不新增 `canonical_url`**。
- **私有源** `NLD_PRIVATE_SOURCES` 指向的目录结构镜像新的 `sources/{dir}/`，加载方式保持 `spec_from_file_location`。
- **`source_name` 与目录名解耦**：目录名只是磁盘位置，`source_name` 是系统内唯一 id（`sites/{source_name}.yaml` 用它命名）。`list_sources()`/`get_manifest()`/`capabilities()`/`resolve()` **一律以 `source.json` 里的 `source_name` 为键**，绝不以目录名当 `source_name`。10 个书源目录与 `source_name`：

| 目录 | `source_name` | 原路径 |
|---|---|---|
| `fanqie_api_oiapi` | `fanqie-api-oiapi` | `fanqie/api/oiapi/` |
| `fanqie_api_rain` | `fanqie-api-rain` | `fanqie/api/rain/` |
| `fanqie_browser_default` | `fanqie-browser-default` | `fanqie/browser/default/` |
| `fanqie_requests_default` | `fanqie-requests-default` | `fanqie/requests/default/` |
| `qidian_browser_default` | `qidian-browser-default` | `qidian/browser/default/` |
| `qidian_requests_default` | `qidian-requests-default` | `qidian/requests/default/` |
| `qimao_api_rain` | `qimao-api-rain` | `qimao/api/rain/` |
| `qimao_browser_default` | `qimao-browser-default` | `qimao/browser/default/` |
| `qimao_requests_default` | `qimao-requests-default` | `qimao/requests/default/` |
| `92xs_requests_default` | `92xs-requests-default` | `92xs/requests/default/` |

- **`variant` 字段已取消**（2026-09-24）：`source.json` 的能力段**没有 `variant`**（同一 mode 下的不同实现各自是一个书源，靠 `source_name` 区分）；`options.py` 的 `APIOptions.name`、`set_api_options(name=...)` 在本计划 Task 7 删除；`shared/config.py` 的 `mode_variants` / `find_variant_options` 属后续「配置」计划，不在本计划收口。
- **验收口径**：`python -m pytest tests/ -q` 全绿（基线 `313 passed, 2 skipped`，2026-09-24 实测）。中间任务只跑指定子集并标注预期；Task 11 跑全量并核对总数。
- **提交约定**：commit 消息用中文；一个方面一条 commit；禁止 `git add -A`（显式列文件）；中文消息用 `git commit -F <文件>` 传入。
- `app_data/config/sites/*.yaml` 的迁移**不在本计划内**（属后续「配置/后端」计划）；本计划只负责让 `source.json` 可被读取。

---

## 文件结构

**新建**

| 文件 | 职责 |
|---|---|
| `novelbase/sources/manifest.py` | 读 + 校验一个书源目录的 `source.json`（身份字段、`default_config` 的能力段与 mode 合法性、能力段 ⇔ `.py` 文件一致性） |
| `novelbase/sources/{10 个书源目录}/source.json` | 每个书源的出厂声明（`source_name` / `enabled` / `default_config`） |
| `tests/test_source_manifest.py` | `manifest.py` 的单元测试（合法/非法 json、能力段不一致、字段按 mode 校验） |
| `tests/test_source_layout.py` | 新目录结构的集成测试（10 个目录、source_name 与 mode 归属、旧目录已删） |
| `tests/test_source_api.py` | `source.py` 4 个 API 的单元测试（含编译模式、能力段 ⇔ `.py` 一致性） |
| `tests/test_novel_id_stability.py` | id 稳定性兜底：典型 url 的 `make_novel_id` 写死哈希 + 92xs 不得被 `/html/` 规范化 |

**修改（novelbase/）**

| 文件 | 改动 |
|---|---|
| `novelbase/sources/contracts.py` | `CAPABILITY_META` 去掉 `file_stem`（能力名 = 文件名 = 函数名） |
| `novelbase/source.py` | 重写为 4 个 API（键 = source_name）；删除 `platform_from_url` / `register_source` / `_scan_sources` / `_scan_capabilities` 旧约定 |
| `novelbase/core/downloader.py` | 4 个下载函数换签名；删除 `_normalize_mode` / `_variant_for` / `get_source` / `list_sources` |
| `novelbase/__init__.py` | 删除 `get_source` 导入；`list_sources()` 改为转发 `source.list_sources()` |
| `novelbase/models/novel.py` | `Novel` 增 `source_name: str = ""`；`SearchResult.platform` → `source_name` |
| `novelbase/sources/92xs_requests_default/search.py` | 删 `SearchResult(platform="92xs")` 的 `platform=` 参数（source_name 由 downloader 统一打标） |
| `novelbase/core/options.py` | 删除 `APIOptions.name` 字段与 `Options.set_api_options(name: str, ...)` 的首参 |
| `novelbase/utils/build_manifest.py` | 适配新结构（遍历 `sources/*/source.json`，生成 `SOURCES` 与 `SOURCE_DIRS`） |

**修改（tests/）**

| 文件 | 改动 |
|---|---|
| `tests/test_source_contracts.py` | **全量重写**：新 API 的签名校验、CAPABILITY_META 一致性、capabilities 结构、私有源合并/优先级 |
| `tests/test_downloader.py` | 按新签名重写（`source_name` + `engines` 解析器） |
| `tests/test_models.py` | 追加 `Novel.source_name` / `SearchResult.source_name` 用例 |
| `tests/test_options.py` | 删除 `APIOptions.name` / `set_api_options(name=...)` 相关断言 |
| `tests/test_engine_httpx.py` | 两处 `set_api_options(name=...)` 去掉 `name=` |
| `tests/test_source_async.py` | import 路径从旧四层改为新一层目录；`fanqie._common` 内联后的能力文件 |
| `tests/test_browser_sources.py` | import 路径从旧四层改为新一层目录 |
| `tests/test_interactive_cli.py` | 删除 `_platform_from_url` 旧断言；`test_show_platforms` 改 monkeypatch 新 API；`do_search` 用例按新行为改 |
| `tests/test_cli_variant.py` | 删除 `cli.interactive._resolve_variant` 用例；`build_options` 的 `opts.api.name` 断言改为不依赖 name |
| `tests/check_imports.py` | `list_sources()` 输出改为新的 10 个 `source_name` |

**修改（backend/cli 最小适配，用户已批准偏离 spec 非目标）**

| 文件 | 改动 |
|---|---|
| `cli/interactive.py` | 删除顶层 `from novelbase.source import register_source, platform_from_url`；删 `_platform_from_url` 与 `_resolve_variant`（variant 概念取消）；`do_search` 用 `list_sources()` |
| `cli/ui.py` | `_show_platforms()` 改用 `list_sources()`（source_name 即标签），不再依赖 `register_source` |
| `cli/config.py` | `build_options()` 的 `set_api_options(name=name, ...)` 去掉 `name` 参数 |
| `backend/routers/download.py` | 删顶层 `from novelbase.source import platform_from_url`（否则 `backend.main` import 崩 → `test_android_server` 全红）；`_platform_from_url`/`detect`/`list_platforms`/`list_all_sources` 里的旧符号引用一并清理 |

> 经核实**不需要改**的文件（不红，勿动）：
> - `tests/test_engine_manager.py`、`tests/test_task_manager_async.py`：其测试通过 monkeypatch 隔离了被删 API，且 `backend/services/engine_manager.py`/`task_manager.py` 顶层 import（`from novelbase import Options/create_engine/resolve_meta` 等，Task 6/7 后仍在）不受影响；`engine_manager.py:138,189,212` 的 `set_api_options(name=...)` / `APIOptions(name=...)` 只在运行时 api 分支触发，而这两个测试 monkeypatch `create_engine_for_request` 或走 browser 分支，**不触发**，故不红。
> - `tests/test_site_config.py`（只测 `get_mode_variant_config`/`mode_variants`/`load_mode_config`，不调 `build_options`）、`tests/test_shared_user_data.py`（`shared/user_data.py` 不 import novelbase 旧 API）、`tests/test_cli_dev_new_variant.py`（`_scaffold_variant` 是文件操作，`import cli.main` 顶层不引用被删符号）、`tests/test_exceptions.py`（`AuthenticationError.platform` 不是 `SearchResult.platform`，Task 5 不删它）。

---

## Task 1: `CAPABILITY_META` 去掉 `file_stem`

**Files:**
- Modify: `novelbase/sources/contracts.py`（`CAPABILITY_META` 定义处）
- Modify: `novelbase/source.py`（两处读 `meta['file_stem']` 的地方做最小替换）
- Test: `tests/test_source_contracts.py`

**Interfaces:**
- Produces: `CAPABILITY_META: dict[str, dict]`，每项只有 `{"required_params": tuple[str, ...]}`，键即能力名（= 文件名 = 函数名）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_source_contracts.py（追加）
from novelbase.sources.contracts import CAPABILITY_META


def test_capability_meta_keys_are_file_stems():
    """能力名 = 文件名 = 函数名；meta 里不再有 file_stem 字段。"""
    assert set(CAPABILITY_META) == {"search", "novel_info", "chapter_list", "chapter_content"}
    for name, meta in CAPABILITY_META.items():
        assert "file_stem" not in meta
        assert "required_params" in meta


def test_required_params_unchanged():
    assert CAPABILITY_META["search"]["required_params"] == ("query", "engine")
    assert CAPABILITY_META["novel_info"]["required_params"] == ("url", "engine")
    assert CAPABILITY_META["chapter_list"]["required_params"] == ("url", "engine")
    assert CAPABILITY_META["chapter_content"]["required_params"] == ("chapter", "engine")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_source_contracts.py -q -k file_stems`
Expected: FAIL（当前 `meta` 里存在 `file_stem`）

- [ ] **Step 3: 改 `CAPABILITY_META`**

```python
CAPABILITY_META: dict[str, dict] = {
    "search":          {"required_params": ("query",   "engine")},
    "novel_info":      {"required_params": ("url",     "engine")},
    "chapter_list":    {"required_params": ("url",     "engine")},
    "chapter_content": {"required_params": ("chapter", "engine")},
}
```

同时更新该文件顶部 docstring 里「file_stem: 文件名 stem」那段说明（能力名即文件名）。

- [ ] **Step 4: 修 `source.py` 里对 `file_stem` 的引用**

`novelbase/source.py` 现有两处读 `meta['file_stem']`（`_scan_capabilities` 第 189 行、`resolve` 第 256 行起）。本任务只做最小改动让它继续可跑：把 `meta['file_stem']` 替换为能力名本身（循环变量 `func_name` / 参数 `function`）。完整重写在 Task 4。

- [ ] **Step 5: 运行测试**

Run: `python -m pytest tests/test_source_contracts.py tests/test_urls.py -q`
Expected: PASS（本任务只跑指定子集；Task 1 新增 2 例，其余不变）

- [ ] **Step 6: Commit**

```bash
git add novelbase/sources/contracts.py novelbase/source.py tests/test_source_contracts.py
git commit -F /tmp/msg.txt   # "refactor: CAPABILITY_META 去掉 file_stem（能力名即文件名）"
```

---

## Task 2: `source.json` 加载与校验

**Files:**
- Create: `novelbase/sources/manifest.py`
- Create: `tests/test_source_manifest.py`

**Interfaces:**
- Produces:
  - `IDENTITY_FIELDS = ("source_name", "enabled")`
  - `MODE_FIELDS: dict[str, tuple[str, ...]]` — 按 mode 列出合法字段（见下）
  - `load_manifest(source_dir: Path) -> dict` — 读 `source.json`，校验后返回其内容；返回前把顶层 `common` 段**合并进每个能力段**（能力段覆盖 `common`），所以 `default_config` 各段都是完整字段。文件缺失或非法时抛 `ManifestError`
  - `class ManifestError(ValueError)`
  - `check_capability_files(source_dir: Path, manifest: dict) -> None` — 断言「`default_config` 的能力段 ⇔ 目录下同名 `.py` 文件」双向一致，不一致抛 `ManifestError`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_source_manifest.py
import json
import pytest

from novelbase.sources.manifest import ManifestError, check_capability_files, load_manifest


def _write(tmp_path, manifest: dict, files: tuple[str, ...] = ()):  # 帮助函数
    (tmp_path / "source.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    for f in files:
        (tmp_path / f).write_text("", encoding="utf-8")
    return tmp_path


BASE = {
    "source_name": "demo-requests-default",
    "enabled": True,
    "default_config": {
        "search": {"mode": "requests", "timeout": 30, "retry_times": 3},
    },
}


def test_load_manifest_ok(tmp_path):
    d = _write(tmp_path, BASE, ("search.py",))
    m = load_manifest(d)
    assert m["source_name"] == "demo-requests-default"
    check_capability_files(d, m)  # 不抛


def test_load_manifest_missing_file(tmp_path):
    with pytest.raises(ManifestError):
        load_manifest(tmp_path)


def test_load_manifest_missing_identity_field(tmp_path):
    bad = {k: v for k, v in BASE.items() if k != "enabled"}
    d = _write(tmp_path, bad)
    with pytest.raises(ManifestError, match="enabled"):
        load_manifest(d)


def test_load_manifest_unknown_mode(tmp_path):
    bad = json.loads(json.dumps(BASE))
    bad["default_config"]["search"]["mode"] = "openapi"
    d = _write(tmp_path, bad)
    with pytest.raises(ManifestError, match="mode"):
        load_manifest(d)


def test_load_manifest_field_not_allowed_for_mode(tmp_path):
    bad = json.loads(json.dumps(BASE))
    bad["default_config"]["search"]["key"] = "xxx"        # key 只属于 api mode
    d = _write(tmp_path, bad)
    with pytest.raises(ManifestError, match="key"):
        load_manifest(d)


def test_variant_is_not_a_valid_field(tmp_path):
    """variant 字段已取消（2026-09-24）：同一 mode 下的不同实现各自是一个书源。"""
    bad = json.loads(json.dumps(BASE))
    bad["default_config"]["search"]["variant"] = "rain"
    d = _write(tmp_path, bad)
    with pytest.raises(ManifestError, match="variant"):
        load_manifest(d)


def test_common_is_merged_into_every_capability(tmp_path):
    """顶层 common 段自动并入每个能力段。"""
    m = dict(BASE)
    m["common"] = {"timeout": 30, "retry_times": 3}
    d = _write(tmp_path, m, ("search.py",))
    got = load_manifest(d)
    assert got["default_config"]["search"]["timeout"] == 30
    assert got["default_config"]["search"]["mode"] == "requests"      # 能力段自己的字段保留


def test_capability_overrides_common(tmp_path):
    m = dict(BASE)
    m["common"] = {"timeout": 30}
    m["default_config"] = {"search": {"mode": "requests", "timeout": 99}}
    d = _write(tmp_path, m, ("search.py",))
    got = load_manifest(d)
    assert got["default_config"]["search"]["timeout"] == 99


def test_common_field_illegal_for_one_mode(tmp_path):
    """同时存在 api / browser 能力时，common 不能放 api 专属字段。"""
    m = {
        "source_name": "demo-two-modes",
        "enabled": True,
        "common": {"key": "xxx"},                       # key 只属于 api
        "default_config": {
            "search": {"mode": "api"},
            "chapter_content": {"mode": "browser"},
        },
    }
    d = _write(tmp_path, m)
    with pytest.raises(ManifestError, match="common"):
        load_manifest(d)


def test_capability_files_both_ways(tmp_path):
    d = _write(tmp_path, BASE, ())                        # 有 search 段但没 search.py
    m = load_manifest(d)
    with pytest.raises(ManifestError, match="search.py"):
        check_capability_files(d, m)

    d2 = _write(tmp_path, BASE, ("search.py", "novel_info.py"))   # 有 novel_info.py 但没段
    m2 = load_manifest(d2)
    with pytest.raises(ManifestError, match="novel_info"):
        check_capability_files(d2, m2)
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_source_manifest.py -q`
Expected: FAIL with `ModuleNotFoundError: novelbase.sources.manifest`

- [ ] **Step 3: 实现 `manifest.py`**

```python
"""书源 `source.json` 的加载与校验。

一个书源 = `novelbase/sources/{dir}/`，内含：
- `__init__.py`（空，包标记）
- `source.json`（身份 + 出厂配置）
- 能力文件 `search.py` / `novel_info.py` / `chapter_list.py` / `chapter_content.py`（按需）
"""

import json
from pathlib import Path
from typing import Any

IDENTITY_FIELDS = ("source_name", "enabled")

# 字段集按 mode 划分，与 novelbase/core/options.py 的三个 dataclass 一一对应
_MODE_COMMON = ("mode", "timeout", "retry_times", "delay", "backoff_factor")
MODE_FIELDS: dict[str, tuple[str, ...]] = {
    "api":      _MODE_COMMON + ("key", "params"),
    "requests": _MODE_COMMON + ("headers", "cookies", "proxies"),
    "browser":  _MODE_COMMON + ("browser_type", "headless", "user_data_dir",
                                "viewport", "extra_args", "auto_reconnect"),
}

MANIFEST_NAME = "source.json"


class ManifestError(ValueError):
    """`source.json` 缺失、字段非法或与目录内容不一致。"""


def load_manifest(source_dir: Path) -> dict[str, Any]:
    """读取并校验 `source_dir/source.json`。"""
    path = Path(source_dir) / MANIFEST_NAME
    if not path.is_file():
        raise ManifestError(f"缺少 {MANIFEST_NAME}: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ManifestError(f"{path} 不是合法 JSON: {e}") from e
    if not isinstance(manifest, dict):
        raise ManifestError(f"{path} 顶层必须是对象")

    for field in IDENTITY_FIELDS:
        if field not in manifest:
            raise ManifestError(f"{path} 缺少必填字段 {field}")
    if not isinstance(manifest["source_name"], str) or not manifest["source_name"]:
        raise ManifestError(f"{path} 的 source_name 必须是非空字符串")
    if not isinstance(manifest["enabled"], bool):
        raise ManifestError(f"{path} 的 enabled 必须是布尔值")

    config = manifest.get("default_config", {})
    if not isinstance(config, dict):
        raise ManifestError(f"{path} 的 default_config 必须是对象")
    common = manifest.get("common", {})
    if not isinstance(common, dict):
        raise ManifestError(f"{path} 的 common 必须是对象")

    # 1) 定每个能力段的有效 mode（自身 mode 优先，否则继承 common.mode）
    effective: dict[str, str] = {}
    for capability, section in config.items():
        if capability not in _capability_names():
            raise ManifestError(f"{path} 的 default_config 含未知能力 {capability!r}")
        if not isinstance(section, dict):
            raise ManifestError(f"{path} 的能力段 {capability} 必须是对象")
        mode = section.get("mode", common.get("mode"))
        if mode not in MODE_FIELDS:
            raise ManifestError(
                f"{path} 的 {capability}.mode 非法或缺失: {mode!r}（可选 {list(MODE_FIELDS)}）"
            )
        effective[capability] = mode

    # 2) common 的字段必须对所有出现的能力 mode 都合法（各 mode 字段集的交集）
    if common:
        modes = set(effective.values())
        allowed_common = set.intersection(*(set(MODE_FIELDS[m]) for m in modes))
        for key in common:
            if key not in allowed_common:
                raise ManifestError(
                    f"{path} 的 common 字段 {key!r} 对出现的 mode {sorted(modes)} 不都合法"
                    f"（公共字段只能是 {sorted(allowed_common)}）"
                )

    # 3) 合并 common（能力段覆盖），并逐段校验字段合法性
    merged: dict[str, dict] = {}
    for capability, section in config.items():
        mode = effective[capability]
        fields = {**common, **section}
        allowed = set(MODE_FIELDS[mode])
        for key in fields:
            if key not in allowed:
                raise ManifestError(
                    f"{path} 的 {capability} 段字段 {key!r} 不属于 mode={mode}（可选 {sorted(allowed)}）"
                )
        merged[capability] = fields

    manifest["default_config"] = merged
    return manifest


def check_capability_files(source_dir: Path, manifest: dict[str, Any]) -> None:
    """能力段存在 ⇔ 对应 `.py` 文件存在（双向）。"""
    source_dir = Path(source_dir)
    declared = set(manifest.get("default_config", {}))
    present = {
        name for name in _capability_names()
        if (source_dir / f"{name}.py").is_file()
    }
    missing = declared - present
    if missing:
        raise ManifestError(
            f"{source_dir} 声明了能力段但缺少文件: {sorted(f'{m}.py' for m in missing)}"
        )
    extra = present - declared
    if extra:
        raise ManifestError(
            f"{source_dir} 有文件但 default_config 未声明: {sorted(extra)}"
        )


def _capability_names() -> tuple[str, ...]:
    from .contracts import CAPABILITY_META
    return tuple(CAPABILITY_META)
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_source_manifest.py -q`
Expected: PASS（10 例）

- [ ] **Step 5: Commit**

```bash
git add novelbase/sources/manifest.py tests/test_source_manifest.py
git commit -F /tmp/msg.txt   # "feat: 新增 source.json 加载与校验（manifest.py）"
```

---

## Task 3: 目录扁平化（10 个书源目录 + `source.json`）

**Files:**
- Create: `novelbase/sources/{10 个目录}/`（`__init__.py` 空文件 + `source.json` + 4 个能力文件，由本任务步骤搬移生成）
- Delete: `novelbase/sources/{fanqie,qidian,qimao,92xs}/`（旧四层结构）
- Test: `tests/test_source_layout.py`（新建）

**Interfaces:**
- Consumes: `manifest.load_manifest` / `check_capability_files`（Task 2）
- Produces: 10 个书源目录，目录名与 `source_name` 见 Global Constraints 的表；每个目录有 4 个能力文件，mode 归属与迁移前一致

- [ ] **Step 1: 写失败测试（新结构 + mode 归属断言）**

```python
# tests/test_source_layout.py
from pathlib import Path

import pytest

from novelbase.sources.contracts import CAPABILITY_META
from novelbase.sources.manifest import check_capability_files, load_manifest

SOURCES = Path(__file__).resolve().parents[1] / "novelbase" / "sources"

# 每个新书源目录的 mode 归属 = 其原 {platform}/{mode}/{variant} 路径里的 mode。
# 这是「能力矩阵未被改坏」的真断言：4 个能力的 mode 必须与迁移前一致。
EXPECTED_MODE = {
    "fanqie_api_oiapi": "api",
    "fanqie_api_rain": "api",
    "fanqie_browser_default": "browser",
    "fanqie_requests_default": "requests",
    "qidian_browser_default": "browser",
    "qidian_requests_default": "requests",
    "qimao_api_rain": "api",
    "qimao_browser_default": "browser",
    "qimao_requests_default": "requests",
    "92xs_requests_default": "requests",
}

# 目录名 → source_name（Global Constraints 表）
DIR_TO_SOURCE_NAME = {
    "fanqie_api_oiapi": "fanqie-api-oiapi",
    "fanqie_api_rain": "fanqie-api-rain",
    "fanqie_browser_default": "fanqie-browser-default",
    "fanqie_requests_default": "fanqie-requests-default",
    "qidian_browser_default": "qidian-browser-default",
    "qidian_requests_default": "qidian-requests-default",
    "qimao_api_rain": "qimao-api-rain",
    "qimao_browser_default": "qimao-browser-default",
    "qimao_requests_default": "qimao-requests-default",
    "92xs_requests_default": "92xs-requests-default",
}


@pytest.mark.parametrize("dirname", sorted(EXPECTED_MODE))
def test_source_dir_has_identity_and_capabilities(dirname):
    d = SOURCES / dirname
    assert d.is_dir(), f"缺少书源目录 {dirname}"
    manifest = load_manifest(d)
    assert manifest["source_name"] == DIR_TO_SOURCE_NAME[dirname]
    check_capability_files(d, manifest)          # 能力段 ⇔ .py 文件
    assert (d / "__init__.py").is_file()


@pytest.mark.parametrize("dirname", sorted(EXPECTED_MODE))
def test_source_dir_mode_matches_legacy(dirname):
    """每个新书源的 4 个能力 mode 与迁移前目录层级一致（防能力矩阵改坏）。"""
    manifest = load_manifest(SOURCES / dirname)
    assert set(manifest["default_config"]) == set(CAPABILITY_META), dirname
    for cap, section in manifest["default_config"].items():
        assert section["mode"] == EXPECTED_MODE[dirname], f"{dirname}.{cap}"


def test_no_legacy_platform_dirs():
    """旧的 {platform}/{mode}/{variant} 四层目录不再存在。"""
    for legacy in ("fanqie", "qidian", "qimao", "92xs"):
        assert not (SOURCES / legacy).exists(), f"旧目录未删除: {legacy}"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_source_layout.py -q`
Expected: FAIL（10 个目录都不存在）

- [ ] **Step 3: 搬移目录并生成 `source.json`**

对 Global Constraints 表里的 10 行逐一执行（以 `fanqie/api/rain` → `fanqie_api_rain` 为例）：

```bash
# 以 fanqie/api/rain → fanqie_api_rain 为例：先建新目录，再逐文件搬 4 个能力文件 + 空 __init__.py。
# 注意：不搬 _helpers.py、不复制 _common.py（见下方内联规则）。
mkdir -p novelbase/sources/fanqie_api_rain
git mv novelbase/sources/fanqie/api/rain/search.py novelbase/sources/fanqie_api_rain/search.py
git mv novelbase/sources/fanqie/api/rain/novel_info.py novelbase/sources/fanqie_api_rain/novel_info.py
git mv novelbase/sources/fanqie/api/rain/chapter_list.py novelbase/sources/fanqie_api_rain/chapter_list.py
git mv novelbase/sources/fanqie/api/rain/chapter_content.py novelbase/sources/fanqie_api_rain/chapter_content.py
git mv novelbase/sources/fanqie/api/rain/__init__.py novelbase/sources/fanqie_api_rain/__init__.py
# 残留的 fanqie/api/rain/_helpers.py 与空目录不搬；整个 fanqie 旧树在 Step 4 一并 git rm。
```

**共享逻辑内联规则（2026-09-24 定：新结构不设 `_common.py`，见 spec 第 83 行）**：

1. 先 grep 该平台的 `_common.py` / `_helpers.py` 被哪些能力文件 import：`grep -rn "_common\|_helpers" novelbase/sources/fanqie/`
2. 对每个新书源目录，把它需要的函数**内联进对应的能力文件**——复制函数体，只带该文件真正调用的部分，**不要**整份复制 `_common.py`；`fanqie/api/rain/_helpers.py` 同样内联进 `fanqie_api_rain` 的 4 个能力文件
3. 内联完成后删除 `_common.py` / `_helpers.py`（随 Step 4 `git rm` 旧树一起），确认没有残留的相对 import（`from .._common import ...`、`from ..._common import ...`、`from ._helpers import ...`）
4. 逐个验证：`python -c "import novelbase.sources.fanqie_api_rain.search, novelbase.sources.92xs_requests_default.novel_info; print('ok')"`（新结构下不再有 `_common`/`_helpers` 可 import，import 失败即说明有残留引用）
5. `fanqie/_common.py`（19.8 KB）会被 4 个 fanqie 书源按各自用到的部分各内联一份，`qidian`（8.0 KB）/`qimao`（7.4 KB）同理——这是「书源各自独立」的直接代价，spec 已接受

> **搬移方式**：只搬 4 个能力文件 + 空 `__init__.py`，**不搬 `_helpers.py`、不复制 `_common.py`**。新结构不设 `_common.py`，共享逻辑（含 `_helpers.py`）必须内联进能力文件。

每个新目录写 `source.json`。以 `fanqie_api_rain` 为例（其余 9 个按「mode 归属 + 该 mode 的字段集」照此填，字段值取 `novelbase/core/options.py` 三个 dataclass 的默认值）：

```json
{
  "source_name": "fanqie-api-rain",
  "enabled": false,
  "common": {
    "mode": "api",
    "timeout": 30,
    "retry_times": 3,
    "delay": [3, 5],
    "backoff_factor": 2,
    "key": "",
    "params": {}
  },
  "default_config": {
    "search":          {},
    "novel_info":      {},
    "chapter_list":    {},
    "chapter_content": {}
  }
}
```

（该书的 4 个能力同为 `api` mode，所以 `mode`、`key`、`params` 都能放进 `common`；能力段留空 `{}` 继承。若某个能力要换 mode（如 `chapter_content` 走 `browser`），就在该段里写 `"mode": "browser"` 与 browser 专属字段——此时 `common` 里就不能再有 `key`/`params`，`load_manifest` 会报错。）

`enabled` 的取值规则（书源唯一的出厂开关）：

- `enabled`：**`api` 类默认 `false`（需要 key），`requests` / `browser` 默认 `true`**（spec 风险节的建议）

> **书源没有中文显示名**（2026-09-24 取消 `show_name`）：界面与日志统一显示 `source_name`（如 `fanqie-requests-default`）。因此本步搬移时**丢弃**原 `__init__.py` 里的 `SHOW_NAME`（它不再有任何消费方）。

`default_config` 里各能力的 `mode` 归属**照搬迁移前的目录层级**（`fanqie/api/rain/*` → `"mode": "api"`；`92xs/requests/default/*` → `"mode": "requests"`），**不要顺手改动任何一个**。能力函数体的 url 生成逻辑也**一字不改**（Global Constraints：不得改变书源返回的 url）。

- [ ] **Step 4: 删除旧目录与旧元数据**

```bash
git rm -r novelbase/sources/fanqie novelbase/sources/qidian novelbase/sources/qimao novelbase/sources/92xs
```

同时**清空每个新目录里 `__init__.py` 的内容**（旧文件里有 `NAME`/`SHOW_NAME`/`HOSTS`，新结构下身份由 `source.json` 提供）：每个新目录的 `__init__.py` 必须是 **0 字节空文件**。

- [ ] **Step 5: 运行测试**

Run: `python -m pytest tests/test_source_layout.py tests/test_source_manifest.py -q`
Expected: PASS（31 例：layout 21 例 = 10 identity parametrize + 10 mode parametrize + 1 no_legacy；manifest 10 例；以实际 pytest 输出为准）

Run: `python -c "import novelbase.sources.fanqie_api_rain.search, novelbase.sources.92xs_requests_default.novel_info; print('imports ok')"`
Expected: `imports ok`

> **中间态注意**：本任务删了旧四层目录后，`tests/test_source_contracts.py`（`capabilities("fanqie")` 变空）、`tests/test_source_async.py`、`tests/test_browser_sources.py`（import 旧路径）会红，直到 Task 8/9 收口。**不要**在此时跑全量。

- [ ] **Step 6: Commit**

```bash
git add novelbase/sources tests/test_source_layout.py
git commit -F /tmp/msg.txt   # "refactor: 书源目录扁平化（四层 → 一层 + source.json）"
```

---

## Task 4: `source.py` 新 API

**Files:**
- Modify: `novelbase/source.py`（整体重写，312 行 → 约 180 行）
- Test: `tests/test_source_api.py`（新建）

**Interfaces:**
- Consumes: `manifest.load_manifest`（Task 2）、`CAPABILITY_META`（Task 1）
- Produces（后续任务与其它 4 份计划都依赖这 4 个签名）：
  - `list_sources() -> list[str]` — 内置 + 私有书源的 **source_name**（读 `source.json`，不是目录名），去重排序
  - `get_manifest(source_name: str) -> dict` — `source.json` 内容；找不到抛 `KeyError`
  - `capabilities(source_name: str) -> dict[str, str]` — `{"search": "api", ...}`；找不到返回 `{}`
  - `resolve(source_name: str, capability: str) -> tuple[Callable, str]` — 返回 `(函数, 该能力的 mode)`
  - `resolve_book_url(raw: str) -> str` — 保持现状（仅接受 http(s)）
  - **删除** `platform_from_url` / `register_source` / `_scan_sources` / `_scan_capabilities`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_source_api.py
import pytest

from novelbase.source import capabilities, get_manifest, list_sources, resolve


def test_list_sources_contains_ten_new_names():
    names = list_sources()
    assert "fanqie-requests-default" in names
    assert "92xs-requests-default" in names
    assert "fanqie" not in names                  # 旧的平台名不再是书源名
    assert "fanqie_requests_default" not in names  # 目录名不是 source_name（下划线 vs 连字符）
    assert len(set(names)) == len(names)


def test_get_manifest_identity():
    m = get_manifest("92xs-requests-default")
    assert m["source_name"] == "92xs-requests-default"
    assert isinstance(m["enabled"], bool)


def test_get_manifest_unknown():
    with pytest.raises(KeyError):
        get_manifest("nope")


def test_capabilities_returns_capability_to_mode():
    caps = capabilities("92xs-requests-default")
    assert caps == {
        "search": "requests",
        "novel_info": "requests",
        "chapter_list": "requests",
        "chapter_content": "requests",
    }
    assert capabilities("nope") == {}


def test_resolve_returns_function_and_mode():
    fn, mode = resolve("92xs-requests-default", "search")
    assert callable(fn)
    assert mode == "requests"
    assert fn.__name__ == "search"


def test_resolve_unknown_capability():
    with pytest.raises(ValueError):
        resolve("92xs-requests-default", "canonical_url")


def test_resolve_signature_check():
    """resolve 返回的函数必须含 CAPABILITY_META 声明的必需参数。"""
    fn, _ = resolve("92xs-requests-default", "novel_info")
    assert {"url", "engine"} <= set(fn.__code__.co_varnames[: fn.__code__.co_argcount])


def test_platform_concepts_removed():
    import novelbase.source as s
    for gone in ("platform_from_url", "register_source"):
        assert not hasattr(s, gone), f"{gone} 应已删除"


def test_get_manifest_checks_capability_files(tmp_path, monkeypatch):
    """能力段 ⇔ .py 文件双向一致：get_manifest 时校验（spec 规则 1）。"""
    import novelbase.source as s
    from novelbase.sources.manifest import ManifestError

    d = tmp_path / "demo_requests_default"
    d.mkdir()
    (d / "source.json").write_text(
        '{"source_name": "demo-requests-default", "enabled": true, '
        '"default_config": {"search": {"mode": "requests"}}}', encoding="utf-8")
    # 缺 search.py → check_capability_files 抛 ManifestError
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", str(tmp_path))
    with pytest.raises(ManifestError):
        s.get_manifest("demo-requests-default")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_source_api.py -q`
Expected: FAIL（`capabilities` 仍返回 `{mode: {variant: [functions]}}`，`resolve` 仍是 4 参数）

- [ ] **Step 3: 重写 `source.py`**

```python
"""Source 能力发现与动态分发（公共 API）。

书源 = `novelbase/sources/{dir}/`，身份与出厂配置在 `source.json`，能力在 `{capability}.py`。
本模块对外只有 4 个函数 + 1 个 URL 入口：

- `list_sources()`                        所有书源名（source.json 的 source_name）
- `get_manifest(source_name)`             `source.json` 内容
- `capabilities(source_name)`             `{capability: mode}`
- `resolve(source_name, capability)`      `(函数, mode)`
- `resolve_book_url(raw)`                 把输入规范成完整 URL

键约定：`source_name` 与目录名解耦（目录名是合法标识符的磁盘位置，source_name 是
`source.json` 里的唯一 id，形如 `fanqie-api-rain`）。本模块所有公开 API 均以
`source_name` 为键；目录名只在 `import_module` 时使用。

私有源：`NLD_PRIVATE_SOURCES` 指向的目录镜像 `sources/{dir}/`，同名书源目录里
已存在的能力文件优先用内置，缺失的用私有实现补齐。
"""

import os
from importlib import import_module, util as importlib_util
from inspect import signature
from pathlib import Path
from typing import Callable

from .sources.contracts import CAPABILITY_META
from .sources.manifest import ManifestError, check_capability_files, load_manifest

__all__ = ["list_sources", "get_manifest", "capabilities", "resolve", "resolve_book_url"]

_PRIVATE_SOURCES_ROOT: str | None = os.environ.get("NLD_PRIVATE_SOURCES")

_SOURCES_DIR = Path(__file__).parent / "sources"


def _is_compiled() -> bool:
    """Nuitka/PyInstaller 产物里 `__compiled__` 会出现在模块 globals。"""
    return "__compiled__" in globals()


def _compiled_sources() -> dict[str, dict]:
    """编译模式下的书源表：{目录名: source.json 内容}。"""
    from .utils import _manifest
    return _manifest.SOURCES


def _compiled_dir_by_source() -> dict[str, str]:
    """编译模式下的 {source_name: 目录名} 映射（供 import_module 用）。"""
    from .utils import _manifest
    return _manifest.SOURCE_DIRS


def _iter_source_dirs(source_name: str) -> list[tuple[Path, bool]]:
    """按 source_name 反查目录（(路径, 是否内置)），内置在前、私有在后。"""
    dirs: list[tuple[Path, bool]] = []
    if _SOURCES_DIR.is_dir():
        for entry in sorted(_SOURCES_DIR.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_") or not (entry / "source.json").is_file():
                continue
            try:
                if load_manifest(entry).get("source_name") == source_name:
                    dirs.append((entry, True))
            except ManifestError:
                continue
    if _PRIVATE_SOURCES_ROOT:
        p = Path(_PRIVATE_SOURCES_ROOT)
        if p.is_dir():
            for entry in sorted(p.iterdir()):
                if entry.is_dir() and not entry.name.startswith("_") and (entry / "source.json").is_file():
                    try:
                        if load_manifest(entry).get("source_name") == source_name:
                            dirs.append((entry, False))
                    except ManifestError:
                        continue
    return dirs


def list_sources() -> list[str]:
    """列出内置 + 私有书源的 source_name（去重排序）。"""
    if _is_compiled():
        return sorted(m["source_name"] for m in _compiled_sources().values())
    names: set[str] = set()
    roots: list[Path] = []
    if _SOURCES_DIR.is_dir():
        roots.append(_SOURCES_DIR)
    if _PRIVATE_SOURCES_ROOT:
        p = Path(_PRIVATE_SOURCES_ROOT)
        if p.is_dir():
            roots.append(p)
    for root in roots:
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_") or not (entry / "source.json").is_file():
                continue
            try:
                names.add(load_manifest(entry)["source_name"])
            except ManifestError:
                continue
    return sorted(names)


def get_manifest(source_name: str) -> dict:
    """返回书源的 `source.json` 内容（内置优先；非编译模式校验能力段 ⇔ .py 文件）。"""
    if _is_compiled():
        dirname = _compiled_dir_by_source().get(source_name)
        if dirname is None or dirname not in _compiled_sources():
            raise KeyError(f"unknown source: {source_name}")
        return _compiled_sources()[dirname]
    dirs = _iter_source_dirs(source_name)
    if not dirs:
        raise KeyError(f"unknown source: {source_name}")
    d, _ = dirs[0]
    manifest = load_manifest(d)
    check_capability_files(d, manifest)  # spec 规则 1：能力段 ⇔ .py 文件双向一致
    return manifest


def capabilities(source_name: str) -> dict[str, str]:
    """返回 `{capability: mode}`；书源不存在或声明非法时返回 `{}`。"""
    try:
        manifest = get_manifest(source_name)
    except (KeyError, ManifestError):
        return {}
    return {cap: section["mode"] for cap, section in manifest.get("default_config", {}).items()}


def _resolve_import(source_name: str, capability: str, dirname: str):
    """按目录名 import 能力模块并返回函数。"""
    module_path = f"novelbase.sources.{dirname}.{capability}"
    try:
        module = import_module(module_path)
    except ImportError as e:
        raise ImportError(f"Failed to resolve {module_path}: {e}") from e
    fn = getattr(module, capability, None)
    if fn is None:
        raise ImportError(f"{module_path} 里没有名为 {capability} 的函数")
    return fn


def resolve(source_name: str, capability: str):
    """动态加载并返回 `(函数, 该能力的 mode)`。"""
    meta = CAPABILITY_META.get(capability)
    if meta is None:
        raise ValueError(f"unknown capability {capability!r}. Known: {list(CAPABILITY_META)}")

    mode = capabilities(source_name).get(capability)
    if mode is None:
        raise ValueError(f"{source_name} 未声明能力 {capability!r}")

    if _is_compiled():
        # 编译模式：能力模块已被 --include-package=novelbase.sources 打进产物，
        # 文件系统里没有 .py 可查，直接按目录名 import
        dirname = _compiled_dir_by_source().get(source_name)
        if dirname is None:
            raise ImportError(f"unknown source: {source_name}")
        fn = _resolve_import(source_name, capability, dirname)
    else:
        fn = None
        for d, is_builtin in _iter_source_dirs(source_name):
            if is_builtin:
                # 内置：import_module；同名能力内置优先，内置缺失再试私有补齐
                try:
                    fn = _resolve_import(source_name, capability, d.name)
                except ImportError:
                    continue
            else:
                # 私有：在包外（NLD_PRIVATE_SOURCES），必须走 spec_from_file_location（spec:163）
                candidate = d / f"{capability}.py"
                if not candidate.is_file():
                    continue
                module_name = f"novelbase_private.sources.{d.name}.{capability}"
                spec = importlib_util.spec_from_file_location(module_name, str(candidate))
                if spec is None or spec.loader is None:
                    raise ImportError(f"Failed to load spec from {candidate}")
                module = importlib_util.module_from_spec(spec)
                spec.loader.exec_module(module)
                fn = getattr(module, capability, None)
            if fn is not None:
                break
        if fn is None:
            raise ImportError(f"{source_name} 缺少能力文件 {capability}.py")

    sig = signature(fn)
    missing = [p for p in meta["required_params"] if p not in sig.parameters]
    if missing:
        raise ValueError(f"{source_name}.{capability} 签名缺少参数: {missing}. 当前签名: {list(sig.parameters)}")
    return fn, mode


def resolve_book_url(raw: str) -> str:
    """把输入规范成完整 URL（仅接受 http(s)；无法识别时抛 ValueError）。"""
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    raise ValueError(f"无法识别书源或 ID 格式: {raw}")
```

**注意**：本任务**删除** `platform_from_url` / `register_source` / `_scan_sources` / `_scan_capabilities`。`register_source` 的调用方（`downloader.get_source`/`downloader.list_sources`、`backend/`、`cli/`）在后续任务收口；本任务内先保证 `source.py` 自身可用。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_source_api.py -q`
Expected: PASS（9 例）

- [ ] **Step 5: 全库找出 `register_source`/`platform_from_url` 引用（供后续任务使用，本任务不修）**

Run: `grep -rn "platform_from_url\|register_source" --include=*.py novelbase backend cli tests`
Expected: `novelbase/source.py` 内已无 `platform_from_url`/`register_source`（定义、`__all__`、docstring 均无）；`novelbase/core/downloader.py` 仍有 `get_source`/`list_sources` 两处 `register_source` 引用（**留到 Task 6 删除**）；另会命中两处**注释**——`novelbase/exporter.py:11`（docstring 提到 register_source/list_sources，属后续「导出器」文档收口）与 `novelbase/utils/build_manifest.py:64`（生成模板注释，Task 11 重写 build_manifest 时自然消除）——均非代码引用；`backend/`、`cli/`、`tests/` 的引用留给 Task 10。

- [ ] **Step 6: Commit**

```bash
git add novelbase/source.py tests/test_source_api.py
git commit -F /tmp/msg.txt   # "refactor: source.py 改为 list_sources/get_manifest/capabilities/resolve 四个 API（键=source_name）"
```

---

## Task 5: 模型字段 `source_name`（`models/novel.py`）

> 本任务在 downloader（Task 6）之前，使 `SearchResult.source_name` 先于 Task 6 的测试存在。

**Files:**
- Modify: `novelbase/models/novel.py`（`Novel` dataclass 字段区 + `SearchResult`）
- Modify: `novelbase/sources/92xs_requests_default/search.py`（删 `SearchResult(platform="92xs")` 的 `platform=` 参数）
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `Novel.source_name: str = ""`（空 = 旧数据或来源未知）；`SearchResult.source_name: str = ""`（替代 `platform`）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_models.py（追加）
def test_novel_has_source_name_default_empty():
    n = Novel(title="t", url="https://x/y", id="abc", serial=0, author="a", description="d")
    assert n.source_name == ""


def test_novel_loads_tolerates_missing_source_name():
    """旧 JSON 没有 source_name 字段也能加载（setattr 兜底）。"""
    n = Novel.loads(title="t", url="https://x/y", id="abc", serial=0,
                    author="a", description="d")
    assert n.source_name == ""


def test_search_result_uses_source_name():
    r = SearchResult(title="t", author="a")
    assert r.source_name == ""
    assert not hasattr(r, "platform")
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_models.py -q -k source_name`
Expected: FAIL（`Novel` 无 `source_name`；`SearchResult` 仍叫 `platform`）

- [ ] **Step 3: 改模型**

- `Novel` dataclass 字段区加 `source_name: str = ""`
- `SearchResult.platform: str = ""` → `source_name: str = ""`
- 检查 `Novel.loads`：其 `**kwargs` + `setattr` 已能吸收 `source_name`，无需改动

- [ ] **Step 4: 全库改调用点（仅 `novelbase/` 内）**

Run: `grep -rn "\.platform\|platform=" --include=*.py novelbase`
把 `SearchResult` 上的 `platform` 全部改为 `source_name`（`downloader.py` 的 `r.platform = name` 在 Task 6 随新签名一并改；本任务先改 `models/novel.py`）。`novel.extra["platform"]` 的键名**保持不变**（历史数据兼容）。

- [ ] **Step 4b: 删除 92xs 书源 `SearchResult(platform=...)` 构造点**

全库 `SearchResult(` 构造点核实结果：只有 `novelbase/sources/92xs_requests_default/search.py:48` 传了 `platform="92xs"`（其余构造点——`fanqie/api/oiapi/search.py:25`、`fanqie/api/rain/search.py:43`、`qimao/api/rain/search.py:40`、`fanqie/_common.py:158`、`qidian/_common.py:38`、`qimao/_common.py:53`——均不传 `platform`，改名后走默认 `source_name=""`，不崩）。字段改名后 `platform="92xs"` 会 `TypeError`。

删除该参数（**不要**改成 `source_name=`）：`source_name` 是系统级 id（如 `92xs-requests-default`），由 `downloader.search()` 在 Task 6 统一打标 `r.source_name = name`；书源侧不写死、旧值 `"92xs"` 是 platform 短名，本来就被 downloader 覆盖，无消费价值。对前端/后端显示的影响：搜索结果的来源标识统一来自 downloader 打标（`source_name`），前端按 `source_name` 分组展示（属后续「前端」计划），书源无需自报。

- [ ] **Step 5: 运行测试**

Run: `python -m pytest tests/test_models.py -q`
Expected: PASS（59 例：原有 56 例 + 新增 3 例）

Run: `grep -rn "platform=" --include=*.py novelbase/sources`
Expected: 无输出（书源内不再有 `SearchResult(platform=...)`）

- [ ] **Step 6: Commit**

```bash
git add novelbase/models/novel.py novelbase/sources/92xs_requests_default/search.py tests/test_models.py
git commit -F /tmp/msg.txt   # "refactor: Novel 增 source_name、SearchResult.platform 改名 source_name；删 92xs 构造点 platform= 参数"
```

---

## Task 6: `downloader.py` 新签名 + `novelbase/__init__.py` 适配

**Files:**
- Modify: `novelbase/core/downloader.py`（`14-178` 行）
- Modify: `novelbase/__init__.py`（删除 `get_source` 导入；`list_sources` 转发到 `source.list_sources`）
- Test: `tests/test_downloader.py`

**Interfaces:**
- Consumes: `source.resolve / capabilities / list_sources`（Task 4）
- Produces:
  ```python
  async def search(sources: Sequence[str], query: str, engines, skip_delay: bool = False, **kwargs) -> tuple[SearchResult, ...]
  async def resolve_meta(url: str, source_name: str, engines, skip_delay: bool = False, **kwargs) -> Novel
  async def resolve_chapter_list(url: str, source_name: str, engines, skip_delay: bool = False, **kwargs) -> Chapters
  async def resolve_chapter(chapter: Chapter, source_name: str, engines, skip_delay: bool = False, **kwargs) -> Chapter | None
  ```
  `engines` 是「按 mode 取引擎」的解析器：`engines(mode) -> engine`（可调用对象）。**删除** `get_source()` / `list_sources()` / `_normalize_mode()` / `_variant_for()`。

- [ ] **Step 1: 写失败测试（重写整个文件）**

```python
# tests/test_downloader.py（重写）
import asyncio

import pytest

from novelbase.core.downloader import resolve_meta, search
from novelbase.core.exceptions import SourceNotFoundError
from novelbase.models.novel import Novel, SearchResult
from novelbase.utils.urls import make_novel_id


class _Engine:
    def __init__(self, mode="requests"):
        self.mode = mode


def _engines(engine):
    return lambda mode: engine


def test_resolve_meta_returns_novel_with_id(monkeypatch):
    novel = Novel(title="t", url="https://fanqienovel.com/page/7123456789012345678",
                  serial=1, author="a", description="d")

    async def _fake(url, engine, **kw):
        return novel

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    result = asyncio.run(resolve_meta(novel.url, "fanqie-requests-default", _engines(_Engine())))
    assert result.id == make_novel_id(novel.url)
    assert result.extra["platform"] == "fanqie-requests-default"


def test_resolve_meta_unknown_source(monkeypatch):
    def _boom(name, cap):
        raise ValueError("unknown capability")

    monkeypatch.setattr("novelbase.source.resolve", _boom)
    with pytest.raises(SourceNotFoundError):
        asyncio.run(resolve_meta("https://x/y", "nope", _engines(_Engine())))


def test_search_tags_each_result_with_source(monkeypatch):
    async def _fake(query, engine, **kw):
        return (SearchResult(title="a", author="b", url="https://x/1"),)

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    res = asyncio.run(search(["s1", "s2"], "关键词", _engines(_Engine())))
    assert {r.source_name for r in res} == {"s1", "s2"}


def test_search_skips_failing_source(monkeypatch):
    async def _ok(query, engine, **kw):
        return (SearchResult(title="a", author="b", url="https://x/1"),)

    def _resolve(name, cap):
        if name == "bad":
            raise ImportError("boom")
        return _ok, "requests"

    monkeypatch.setattr("novelbase.source.resolve", _resolve)
    res = asyncio.run(search(["bad", "good"], "关键词", _engines(_Engine())))
    assert len(res) == 1 and res[0].source_name == "good"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_downloader.py -q`
Expected: FAIL（`resolve_meta` 仍是 `(url, engine, ...)`；`get_source` 已随旧文件删除不再可 import）

- [ ] **Step 3: 实现新签名**

```python
async def search(sources: Sequence[str], query: str, engines,
                 skip_delay: bool = False, **kwargs) -> tuple[SearchResult, ...]:
    """并发搜索给定书源；单个书源失败静默跳过。"""
    from ..source import resolve as _resolve

    async def _one(name: str) -> list[SearchResult]:
        fn, mode = _resolve(name, "search")
        kwargs["skip_delay"] = skip_delay
        results = await fn(query=query, engine=engines(mode), **kwargs)
        for r in results:
            r.source_name = name
        return list(results)

    gathered = await asyncio.gather(*(_one(n) for n in sources), return_exceptions=True)
    out: list[SearchResult] = []
    for item in gathered:
        if isinstance(item, Exception):
            _log.warning("search failed for one source: %s", item)
            continue
        out.extend(item)
    return tuple(out)


async def resolve_meta(url: str, source_name: str, engines, skip_delay: bool = False, **kwargs) -> Novel:
    from ..source import resolve as _resolve

    try:
        fn, mode = _resolve(source_name, "novel_info")
    except (ValueError, ImportError) as e:
        raise SourceNotFoundError(f"source not found: {source_name}") from e
    kwargs["skip_delay"] = skip_delay
    novel = await fn(url=url, engine=engines(mode), **kwargs)
    novel.id = make_novel_id(novel.url)
    novel.extra["platform"] = source_name
    return novel


async def resolve_chapter_list(url: str, source_name: str, engines, skip_delay: bool = False, **kwargs) -> Chapters:
    from ..source import resolve as _resolve

    fn, mode = _resolve(source_name, "chapter_list")
    kwargs["skip_delay"] = skip_delay
    return await fn(url=url, engine=engines(mode), **kwargs)


async def resolve_chapter(chapter: Chapter, source_name: str, engines, skip_delay: bool = False, **kwargs) -> Chapter | None:
    from ..source import resolve as _resolve

    fn, mode = _resolve(source_name, "chapter_content")
    kwargs["skip_delay"] = skip_delay
    return await fn(chapter=chapter, engine=engines(mode), **kwargs)
```

文件顶部加 `import asyncio`；**删除** `_normalize_mode` / `_variant_for` / `get_source` / `list_sources` 及旧 `search`/`resolve_*` 的实现。

**同时改 `novelbase/__init__.py`**（否则 Task 6 删了 `get_source`/`list_sources` 后整个包 import 失败）：

- 删除第 1-10 行 import 里的 `get_source`，删除 `__all__` 里的 `"get_source"`。
- 第 38-41 行的 `list_sources()` 改为转发 `source.list_sources`：

```python
def list_sources():
    """列出所有可用 source 名称。"""
    from .source import list_sources as _ls
    return _ls()
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_downloader.py -q`
Expected: PASS（4 例）

Run: `python -c "import novelbase; print(novelbase.list_sources())"`
Expected: 打印 10 个 `source_name`（证明 `__init__.py` 未断）

- [ ] **Step 5: Commit**

```bash
git add novelbase/core/downloader.py novelbase/__init__.py tests/test_downloader.py
git commit -F /tmp/msg.txt   # "refactor: downloader 四个下载函数改为按 source_name 分发、engines 解析器取引擎；__init__ 去 get_source"
```

---

## Task 7: 选项字段清理（`core/options.py` 删 `name`）

**Files:**
- Modify: `novelbase/core/options.py`（删 `APIOptions.name` 字段 + `Options.set_api_options` 的首参 `name`）
- Modify: `tests/test_options.py`（删 `name` 相关断言）
- Modify: `tests/test_engine_httpx.py`（两处 `set_api_options(name=...)` 去掉 `name=`）

**Interfaces:**
- Produces: `APIOptions` 不再有 `name` 字段；`Options.set_api_options(delay=..., timeout=..., retry_times=..., backoff_factor=..., key=..., params=...)` 不再接收 `name`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_options.py（改写三个现有用例，用例名与现有文件一致）
# TestAPIOptions.test_defaults：`assert o.name is None` → `assert not hasattr(o, "name")`
# TestAPIOptions.test_custom：去掉 `name="myapi"` 与 `assert o.name == "myapi"`
# TestOptions.test_set_api_options：`set_api_options(name="test", ...)` 去掉 `name=`；`assert o.api.name == "test"` 删除
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_options.py -q`
Expected: FAIL（`TestAPIOptions.test_defaults`/`test_custom`/`TestOptions.test_set_api_options` 仍依赖 `name`）

- [ ] **Step 3: 改选项与调用点**

- `novelbase/core/options.py`：删除 `APIOptions` 的 `name: str | None = None` 字段；删除 `Options.set_api_options` 的第一个位置参数 `name`，`APIOptions(...)` 构造时不再传 `name`。
- `tests/test_options.py`：`TestAPIOptions.test_defaults` / `TestAPIOptions.test_custom` / `TestOptions.test_set_api_options` 三个用例改写为不依赖 `name`（见 Step 1）。
- `tests/test_engine_httpx.py`：第 102-103 行与第 482 行的 `set_api_options(name="test", ...)` 去掉 `name=`。

> **连带影响（Task 10 收口，本任务不改）**：`shared/config.py:273-274`、`backend/services/engine_manager.py:138,189,212`、`cli/config.py:265-266` 仍在传 `name=`，做完本任务后这些调用点在**运行时**会 `TypeError`。它们由 Task 10（backend/cli 最小适配）与后续「配置」计划收口；本计划结束时 `pytest tests/` 仍绿，因为受波及测试要么不触发这些路径、要么已改。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_options.py tests/test_engine_httpx.py -q`
Expected: PASS（21 例 options + 28 例 engine_httpx）

- [ ] **Step 5: Commit**

```bash
git add novelbase/core/options.py tests/test_options.py tests/test_engine_httpx.py
git commit -F /tmp/msg.txt   # "refactor: APIOptions 删除 name 字段、set_api_options 去掉 name 参数"
```

---

## Task 8: 私有源适配 + `test_source_contracts.py` 全量重写

**Files:**
- Modify: `novelbase/source.py`（Task 4 已按新结构实现，本任务补私有源测试与文档）
- Modify: `tests/test_source_contracts.py`（**全量重写**：原文件其余用例仍调用旧 4 参数 `resolve()` 与旧 `{mode:{variant}}` 形状）

**Interfaces:**
- Consumes: `_PRIVATE_SOURCES_ROOT`（模块级，读环境变量 `NLD_PRIVATE_SOURCES`）
- Produces: 私有书源目录（`{NLD_PRIVATE_SOURCES}/{dir}/{capability}.py`）与内置书源合并；同名能力**内置优先**

- [ ] **Step 1: 写失败测试（私有源部分）**

```python
# tests/test_source_contracts.py（私有源部分）
import json


def test_private_source_merged(tmp_path, monkeypatch):
    d = tmp_path / "demo_requests_default"   # 目录名：下划线（合法标识符）
    d.mkdir()
    (d / "source.json").write_text(json.dumps({
        "source_name": "demo-requests-default",   # source_name：连字符（与目录名解耦）
        "enabled": True,
        "default_config": {"search": {"mode": "requests"}},
    }, ensure_ascii=False), encoding="utf-8")
    (d / "search.py").write_text(
        "async def search(query, engine, **kwargs):\n    return ()\n", encoding="utf-8")

    import novelbase.source as s
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", str(tmp_path))

    assert "demo-requests-default" in s.list_sources()
    assert s.capabilities("demo-requests-default") == {"search": "requests"}
    fn, mode = s.resolve("demo-requests-default", "search")
    assert callable(fn) and mode == "requests"


def test_builtin_wins_over_private(tmp_path, monkeypatch):
    """同名书源的同名能力文件：内置优先于私有。"""
    import novelbase.source as s
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", str(tmp_path))
    fn, _ = s.resolve("92xs-requests-default", "search")
    assert fn.__module__ == "novelbase.sources.92xs_requests_default.search"
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_source_contracts.py -q -k private`
Expected: 当前文件其余用例因旧 API 已红，`-k private` 只选私有源用例；若 Task 4 实现无误，私有源用例可能直接 PASS —— 那说明实现已满足契约，仍继续 Step 3。

- [ ] **Step 3: 全量重写 `tests/test_source_contracts.py`**

旧文件的 `TestSignatureValidation`（旧 4 参数 `resolve("fanqie","browser","search")`）、`TestCapabilityMetaConsistency`（旧 `{mode:{variant}}` 遍历）、`TestCapabilitiesOutput`（`capabilities("fanqie")["api"]["oiapi"]`）、`TestPrivateSources`（旧 `fanqie/api/mypriv` 目录）全部按新结构重写：

```python
"""测试 source 能力契约：签名校验、CAPABILITY_META 一致性、capabilities 输出、私有源。"""
from inspect import signature

import pytest

import novelbase.source as _source_mod
from novelbase.source import capabilities, list_sources, resolve
from novelbase.sources.contracts import CAPABILITY_META


class TestSignatureValidation:
    """运行时签名校验：缺参数拒绝 / 未知能力拒绝。"""

    def test_rejects_missing_params(self, monkeypatch):
        def bad_search(q, engine):  # 用 q 而非 query
            pass

        class FakeMod:
            pass

        fake_mod = FakeMod()
        setattr(fake_mod, "search", bad_search)
        original_import = _source_mod.import_module

        def fake_import(name, package=None):
            if name.endswith(".search"):
                return fake_mod
            return original_import(name, package=package)

        monkeypatch.setattr(_source_mod, "import_module", fake_import)
        with pytest.raises(ValueError, match="query"):
            resolve("92xs-requests-default", "search")

    def test_unknown_capability_raises(self):
        with pytest.raises(ValueError, match="unknown capability"):
            resolve("92xs-requests-default", "nonexistent")


class TestCapabilityMetaConsistency:
    """CAPABILITY_META 定义与真实源文件签名一致。"""

    def test_all_sources_pass_signature_check(self):
        for name in list_sources():
            caps = capabilities(name)
            for cap in caps:
                fn, _mode = resolve(name, cap)
                sig = signature(fn)
                required = CAPABILITY_META[cap]["required_params"]
                missing = [p for p in required if p not in sig.parameters]
                assert not missing, f"{name}/{cap} 签名缺少参数: {missing}"

    def test_capability_names_in_meta(self):
        for name in list_sources():
            for cap in capabilities(name):
                assert cap in CAPABILITY_META, f"{name} 的能力 {cap!r} 不在 CAPABILITY_META 中"


class TestCapabilitiesOutput:
    """capabilities() 输出结构：dict[str, str]（{capability: mode}）。"""

    def test_92xs_all_requests(self):
        assert capabilities("92xs-requests-default") == {
            "search": "requests", "novel_info": "requests",
            "chapter_list": "requests", "chapter_content": "requests",
        }

    def test_nonexistent_source_returns_empty(self):
        assert capabilities("nonexistent") == {}

    def test_ten_sources_listed(self):
        names = list_sources()
        assert len(names) == 10
        assert "fanqie-api-rain" in names and "fanqie" not in names

    def test_source_names_unique(self):
        """source_name 唯一性（spec:254）：所有书源的 source_name 互不重复。"""
        names = list_sources()
        assert len(names) == len(set(names))
```

私有源的两个用例（Step 1）接在本文件末尾。旧文件里 `@pytest.mark.skip(reason="monkeypatch + tmp_path 在 Windows 上超时")` 的用例**删除**（新结构不再需要旧四层私有目录）。

- [ ] **Step 3b: 新增 id 稳定性测试（spec:255 的防 novel_id 漂移兜底）**

新建 `tests/test_novel_id_stability.py`：

```python
"""id 稳定性：重构不得改变书源返回的 url（防 novel_id 漂移，spec:255）。

两层兜底：
1. 每个书源典型 novel.url 的 make_novel_id 输出写死哈希（迁移前实测值）；
2. 静态断言 92xs novel_info 不把 /book/{id}.html 规范化为 /html/{id}/。
"""
from pathlib import Path

from novelbase.utils.urls import make_novel_id

SOURCES = Path(__file__).resolve().parents[1] / "novelbase" / "sources"

# {source_name: (典型 novel.url, 迁移前 make_novel_id(url) 前 32 位)}
STABLE = {
    "92xs-requests-default":   ("http://www.92xs.info/book/9999.html", "293af2df7c5561ec56995462caf24871"),
    "fanqie-requests-default": ("https://fanqienovel.com/page/7123456789012345678", "ace9f3fa0bbb2f9f5dff75687612cda2"),
    "qidian-requests-default": ("https://www.qidian.com/book/1012345678/", "be10875dc3ca3985813a83110d18c92c"),
    "qimao-requests-default":  ("https://www.qimao.com/shuku/195958/", "4afb6803aa4d6440123faa8affbe6612"),
}


def test_make_novel_id_stable_for_typical_urls():
    for source_name, (url, expected) in STABLE.items():
        assert make_novel_id(url) == expected, source_name


def test_92xs_novel_info_url_not_normalized():
    """92xs novel_info 透传输入 url，不得把 /book/{id}.html 规范化为 /html/{id}/。"""
    src = (SOURCES / "92xs_requests_default" / "novel_info.py").read_text(encoding="utf-8")
    assert "/html/" not in src
```

- [ ] **Step 4: 按需修正实现**

确保 `_iter_source_dirs()` / `list_sources()` 每次调用都读模块级 `_PRIVATE_SOURCES_ROOT`（不要在 import 时缓存进局部变量），这样 `monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", ...)` 生效。

- [ ] **Step 5: 运行测试**

Run: `python -m pytest tests/test_source_contracts.py tests/test_source_api.py tests/test_novel_id_stability.py -q`
Expected: PASS（21 例：contracts 重写后 10 例 + source_api 9 例 + novel_id_stability 2 例）

- [ ] **Step 6: Commit**

```bash
git add novelbase/source.py tests/test_source_contracts.py tests/test_novel_id_stability.py
git commit -F /tmp/msg.txt   # "test: 私有源新结构合并与优先级；test_source_contracts 全量重写；id 稳定性兜底"
```

---

## Task 9: 书源测试的 import 路径迁移（`test_source_async` / `test_browser_sources`）

**Files:**
- Modify: `tests/test_source_async.py`（import 路径从旧四层改为新一层目录；`fanqie._common` → 内联后的能力文件）
- Modify: `tests/test_browser_sources.py`（import 路径改为新一层目录）

**Interfaces:**
- Consumes: Task 3 生成的新目录结构
- Produces: 两个测试文件 import 新路径，测试逻辑不变

- [ ] **Step 1: 确认失败现状**

Run: `python -m pytest tests/test_source_async.py tests/test_browser_sources.py -q`
Expected: FAIL with `ModuleNotFoundError`（旧四层路径已被 Task 3 删除）

- [ ] **Step 2: 改 `tests/test_source_async.py` 的 import 路径**

旧路径 → 新路径对照（按 Task 3 的 `source_name` 表）：

| 旧路径 | 新路径 |
|---|---|
| `novelbase.sources.fanqie.requests.default` | `novelbase.sources.fanqie_requests_default` |
| `novelbase.sources.fanqie.browser.default` | `novelbase.sources.fanqie_browser_default` |
| `novelbase.sources.fanqie.api.oiapi` | `novelbase.sources.fanqie_api_oiapi` |
| `novelbase.sources.fanqie.api.rain` | `novelbase.sources.fanqie_api_rain` |
| `novelbase.sources.qidian.requests.default` | `novelbase.sources.qidian_requests_default` |
| `novelbase.sources.qidian.browser.default` | `novelbase.sources.qidian_browser_default` |
| `novelbase.sources.qimao.requests.default` | `novelbase.sources.qimao_requests_default` |
| `novelbase.sources.qimao.browser.default` | `novelbase.sources.qimao_browser_default` |
| `novelbase.sources.qimao.api.rain` | `novelbase.sources.qimao_api_rain` |
| `novelbase.sources.92xs.requests.default` | `novelbase.sources.92xs_requests_default` |

第 109/120 行的 `from novelbase.sources.fanqie._common import parse_chapter_content`：`_common.py` 已在 Task 3 内联进能力文件，`parse_chapter_content` 现在位于**用到它的能力文件**里（`fanqie` 各书源的 `chapter_content.py`，因为它是解析章节正文的纯函数）。改为：

```python
from novelbase.sources.fanqie_requests_default.chapter_content import parse_chapter_content
```

（`parse_chapter_content` 被 `chapter_content.py` 内联；若 Task 3 内联时放进了别的文件，以 Task 3 的实际内联位置为准——先 `grep -rn "def parse_chapter_content" novelbase/sources/` 定位。）

- [ ] **Step 3: 改 `tests/test_browser_sources.py` 的 import 路径**

第 7-8 行：

```python
qidian_search = import_module("novelbase.sources.qidian_browser_default.search")
qimao_chapter_list = import_module("novelbase.sources.qimao_browser_default.chapter_list")
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_source_async.py tests/test_browser_sources.py -q`
Expected: PASS（18 例：source_async 15 例 + browser_sources 3 例）

- [ ] **Step 5: Commit**

```bash
git add tests/test_source_async.py tests/test_browser_sources.py
git commit -F /tmp/msg.txt   # "test: 书源测试 import 路径迁移到新一层目录结构"
```

---

## Task 10: backend/cli 最小适配（让调用点走新 API）

> **范围说明**：本任务偏离 spec「非目标：后端/CLI 改造属后续计划」，是用户 2026-09-24 批准「验收口径扩到 pytest tests/ 全绿」后新增的**最小适配**——只改到「`import cli.interactive` / `cli.ui` / `cli.config` 不崩、且 tests/ 里测这些模块的用例能过」。完整后端/CLI/前端改造仍属后续 4 份计划。

**Files:**
- Modify: `cli/interactive.py`
- Modify: `cli/ui.py`
- Modify: `cli/config.py`
- Modify: `backend/routers/download.py`
- Modify: `tests/test_interactive_cli.py`
- Modify: `tests/test_cli_variant.py`

**Interfaces:**
- Consumes: `novelbase.source.list_sources`（Task 4）；`Options.set_api_options` 无 name（Task 7）
- Produces: `cli.interactive` 可 import；`_platform_from_url` / `_resolve_variant` 删除；`_show_platforms` 用 source_name；`cli.config.build_options` 不再传 `name`；`backend.main` 可 import（`download.py` 不再 import `platform_from_url`）

- [ ] **Step 1: 确认失败现状**

Run: `python -m pytest tests/test_interactive_cli.py tests/test_cli_variant.py -q`
Expected: FAIL（`cli/interactive.py` 顶层 `from novelbase.source import register_source, platform_from_url` ImportError；`cli.config.build_options` 的 `set_api_options(name=...)` TypeError；`test_cli_variant` 的 `opts.api.name` 断言 AttributeError）

- [ ] **Step 2: 改 `cli/interactive.py`**

- 第 17 行删除 `from novelbase.source import register_source, platform_from_url`（保留第 13-16 行对 `resolve_meta` 等的导入）。
- 删除 `_platform_from_url`（26-31）与 `_resolve_variant`（34-52）及 `_variant_cache`（`variant` 概念取消、core 已无 URL→来源推断能力）。
- 以下所有旧 API 调用点改走新 API（否则运行时崩；本任务保证模块可 import 且被测函数不崩）：
  - `do_search`（67-113）：第 71 行 `_platform_from_url(query)`（URL 分支）随 `_platform_from_url` 删除 → 改为「URL 输入需用户手选书源」；第 84-85 行 `register_source()` → `list_sources()`（标签直接用 source_name，`show_name` 已取消）；第 74 行 `resolve_meta(query, engine=engine)` → 新签名 `resolve_meta(url, source_name, engines)`；第 93 行 `search(platform, query, engine=engine)` → 新签名 `search(sources, query, engines)`。
  - `do_download`（119-137）：第 126 行 `_platform_from_url(url)` 已删 → 改为「用户手选书源」或取 `list_sources()[0]`。
  - `_update_one_async`（143-187）：第 148 行 `_platform_from_url` 已删；第 151 行 `resolve_chapter_list(novel.url, engine=engine)` → 新签名；第 171 行 `resolve_chapter(ch, engine=engine)` → 新签名。
  - `do_visit_site`（249-278）：第 253 行 `register_source()` → `list_sources()`；第 258 行 `sources[platform].get("hosts")` 已无 hosts（source.json 无 hosts）→ 用 `source_name` 或直接打开 `https://` 首页占位。
  - `_get_engine`（55-61）：第 60 行 `_resolve_variant(...)` 已删 → 直接按 `capabilities(source_name)` 建引擎。
- `engines` 解析器由 `capabilities(source_name)` 的 mode 集合懒建（本任务内先用 `lambda mode: create_engine(...)` 的最小实现，完整改造留后续计划）。

> **不属本任务的其他 cli 旧符号残留**（已核实：无 pytest 测试触发、且顶层 import 不引用被删符号，故不红，留后续「CLI」计划）：`cli/core.py:59`（`_platform_from_url` 函数内 `from novelbase.source import platform_from_url`）与 `cli/core.py:251`（`_platform_from_url(novel.url)` 调用）；`cli/main.py:45`（`_parse_platform` 内 `_platform_from_url(url)`）、`cli/main.py:337`（`cmd_source` 函数内 `from novelbase.source import register_source`）。`cli/core.py` 顶层只 import `novelbase` 的 `resolve_meta/resolve_chapter_list/resolve_chapter/export/create_engine/StorageOptions`（Task 6 后仍在），`cli/main.py` 顶层只 import `create_engine/resolve_meta`，两者 import 不崩。

> 由于 `cli/interactive.py` 的完整改造（并发全启用书源搜索、手选书源交互）属后续「CLI」计划，本任务**只保证模块可 import、被测函数不崩**；`do_search` 的行为细节以测试通过为准。

- [ ] **Step 3: 改 `cli/ui.py`**

`_show_platforms()` 改为用 `list_sources()`（source_name 即标签）：

```python
def _show_platforms() -> dict[str, str]:
    """返回 {显示标签: 内部名} 的书源映射（source_name 即标签）。"""
    try:
        from novelbase.source import list_sources
        return {name: name for name in list_sources()}
    except Exception:
        return {}
```

`_platform_label` 保持不动（它按 name 反查标签，现在 label == name）。

- [ ] **Step 4: 改 `cli/config.py`**

第 265-266 行 `options.set_api_options(name=name, ...)` 去掉 `name=name`（`APIOptions` 已无 name）。

- [ ] **Step 5: 改 `backend/routers/download.py`（让 `backend.main` 可 import）**

`backend/main.py:16` 顶层 `from backend.routers import ... download ...`；`android/server.py:54` 又 `from backend.main import app`。`download.py:11` 的顶层 `from novelbase.source import platform_from_url, resolve_book_url` 在 Task 4 删 `platform_from_url` 后会让整条 import 链崩，`tests/test_android_server.py` 全红。最小适配：

- 第 11 行改为 `from novelbase.source import resolve_book_url`（删 `platform_from_url`）。
- `_platform_from_url`（16-21）改为「URL 无法自动推断，需用户指定书源」：

```python
def _platform_from_url(url: str) -> str:
    raise HTTPException(400, f"无法自动识别书源 URL，请显式指定书源: {url}")
```

- 第 180/186 行的函数内 `from novelbase.source import platform_from_url`、第 150/158 行的函数内 `from novelbase.source import register_source` 一并删除或改 `list_sources()`（这些只在路由被调用时执行，不导致 import 崩，但属旧符号残留，一并清理；完整后端改造留后续「后端」计划）。

> **注**：`backend/services/engine_manager.py:138,189,212` 的 `set_api_options(name=...)` / `APIOptions(name=...)` **不红**（`test_engine_manager.py` 三个用例 monkeypatch `create_engine_for_request` 或走 browser 分支，不触发 api 分支），本任务不改；`shared/config.py:273-274` 同理属后续「配置」计划。

- [ ] **Step 6: 改 `tests/test_interactive_cli.py`**

- 删除 `test_platform_from_url_fanqie/qidian/qimao/unknown_raises/92xs_alias` 五个用例（`_platform_from_url` 已删除，旧行为「core 由 URL 推断平台」被 spec 明确废弃）。
- `test_show_platforms` 改为：

```python
def test_show_platforms(self, monkeypatch):
    from cli.ui import _show_platforms
    import novelbase.source as src_mod
    monkeypatch.setattr(src_mod, "list_sources", lambda: ["fanqie-api-rain", "92xs-requests-default"])
    labels = _show_platforms()
    assert labels == {"fanqie-api-rain": "fanqie-api-rain", "92xs-requests-default": "92xs-requests-default"}
```

- `test_do_search_keyword_search_error` 按本任务 Step 2 改后的 `do_search` 行为调整 monkeypatch（`mod.search` 仍 monkeypatch 为 `boom`），断言不变（`url is None and plat is None`）。

- [ ] **Step 7: 改 `tests/test_cli_variant.py`**

- 删除 `test_interactive_resolve_variant_asks_and_caches` / `test_interactive_resolve_variant_cancel_falls_back` / `test_interactive_resolve_variant_single_no_ask` 三个用例（`cli.interactive._resolve_variant` 已删除，`variant` 概念取消）。
- `test_build_options_api_explicit_variant`（第 67 行）与 `test_build_options_api_unset_takes_first_enabled`（第 77 行）的 `opts.api.name == ...` 断言删除或改为断言 `opts.api.key`（variant 名不再进字段）。
- 其余 `test_resolve_variant_*`（`cli.config.resolve_variant`）与 `test_main_resolve_variant_*`（`cli.main._resolve_variant`）**保持不动**：这些函数本计划不删（`cli/config.py` 的 `mode_variants`/`resolve_variant` 属后续「CLI」计划），其测试继续绿。

- [ ] **Step 8: 运行测试**

Run: `python -m pytest tests/test_interactive_cli.py tests/test_cli_variant.py tests/test_android_server.py -q`
Expected: PASS（49 例：interactive_cli 36−5=31 例 + cli_variant 17−3=14 例 + android_server 4 例；以实际 pytest 输出为准）

- [ ] **Step 9: Commit**

```bash
git add cli/interactive.py cli/ui.py cli/config.py backend/routers/download.py tests/test_interactive_cli.py tests/test_cli_variant.py
git commit -F /tmp/msg.txt   # "refactor: backend/cli 最小适配（去掉 register_source/platform_from_url/variant 依赖，调用点走新 API）"
```

---

## Task 11: 全量回归与文档收口

**Files:**
- Modify: `novelbase/utils/build_manifest.py`（必须适配，见 Step 3）
- Modify: `tests/check_imports.py`
- Modify: `AGENTS.md`（书源契约段落）

- [ ] **Step 1: 跑全量并核对基线**

Run: `python -m pytest tests/ -q`
Expected: PASS。总数 = 313 − 13 + 46 = 346（估算）：删除 = contracts 13→10(−3) + downloader 6→4(−2) + interactive_cli −5 + cli_variant −3 = −13；新增 = manifest 10 + layout 21 + source_api 10 + novel_id_stability 2 + models 3 = 46。**以实际 pytest 输出为准，最终口径是全绿**。

- [ ] **Step 2: 修 `tests/check_imports.py`**

把第 28 行 `print("  注册的 Source: " + str(list_sources()))` 的预期从旧平台名改为新的 10 个 `source_name`（本文件是 CI 单独跑的导入检查脚本，非 pytest 用例，改为打印即可，必要时加一行 `assert set(list_sources()) >= {...10 个 source_name}`）。

> **说明（预检 #11 处置）**：`tests/check_imports.py` 当前只有 `print` 没有断言，本任务**补一个真断言**（`assert` 10 个 source_name 都在 `list_sources()` 里），而不是沿用「更新输出断言」的措辞。

- [ ] **Step 3: 适配 Nuitka manifest（必须做，不是可选项）**

Nuitka 是**活的构建路径**：`.github/workflows/build-windows-nuitka.yml` + `scripts/build-nuitka.ps1` + `scripts/build-nuitka.sh` 都在用，两个脚本都会先执行 `python -m novelbase.utils.build_manifest`（onefile 产物无法扫描文件系统）。当前 `build_manifest.py` 依赖**将被删除**的 `_scan_capabilities()` 与 `__init__.py` 的 `NAME`/`SHOW_NAME`/`HOSTS`，不改就会直接把 Nuitka 构建打断。

把 `novelbase/utils/build_manifest.py` 改为：

```python
"""构建时工具：扫描 sources/*/source.json 生成 _manifest.py 供 Nuitka onefile 模式使用。

用法: python -m novelbase.utils.build_manifest

onefile 产物无法扫描文件系统，`source.py` 在编译模式下改读本文件内嵌的
`SOURCES`（目录名 → source.json 内容）与 `SOURCE_DIRS`（source_name → 目录名）。
"""
import json
import os
from pathlib import Path

SRC = Path(__file__).parent.parent / "sources"
OUT = Path(__file__).parent / "_manifest.py"


def build() -> None:
    if not SRC.exists():
        print(f"ERROR: sources dir not found: {SRC}")
        return

    sources: dict[str, dict] = {}
    source_dirs: dict[str, str] = {}
    for entry in sorted(os.listdir(SRC)):
        if entry.startswith("_") or entry == "__pycache__":
            continue
        d = SRC / entry
        if not d.is_dir() or not (d / "source.json").is_file():
            continue
        manifest = json.loads((d / "source.json").read_text(encoding="utf-8"))
        sources[entry] = manifest
        source_dirs[manifest["source_name"]] = entry

    lines = [
        "# Auto-generated by novelbase.utils.build_manifest. DO NOT EDIT.",
        "# Nuitka 模式下 source.py 的 list_sources() / get_manifest() / resolve() 读取此文件。",
        "# 删/增书源后重新运行: python -m novelbase.utils.build_manifest",
        "",
        "SOURCES: dict[str, dict] = {",
    ]
    for name, manifest in sources.items():
        lines.append(f"    {name!r}: {manifest!r},")
    lines.append("}")
    lines.append("")
    lines.append("SOURCE_DIRS: dict[str, str] = {")
    for source_name, dirname in sorted(source_dirs.items()):
        lines.append(f"    {source_name!r}: {dirname!r},")
    lines.append("}")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Generated {OUT} ({len(sources)} sources)")


if __name__ == "__main__":
    build()
```

同时删除本地的 `novelbase/utils/_manifest.py`（旧结构的生成物、内容已失效；它**已被 `.gitignore:44` 的 `_*.py` 规则忽略、从未进过版本库**，所以只需删本地文件——**不要写 `git rm`**）。下次跑 `build_manifest` 会按新格式重新生成。

- [ ] **Step 4: 加一个编译模式的测试**

```python
# tests/test_source_api.py（追加）
def test_compiled_mode_reads_manifest(monkeypatch):
    """编译模式（__compiled__ 在 globals）下，list_sources/get_manifest 走 _manifest。"""
    import novelbase.source as s

    fake_sources = {"demo_requests_default": {
        "source_name": "demo-requests-default",
        "enabled": True,
        "default_config": {"search": {"mode": "requests"}},
    }}
    monkeypatch.setattr(s, "_is_compiled", lambda: True)
    monkeypatch.setattr(s, "_compiled_sources", lambda: fake_sources)
    monkeypatch.setattr(s, "_compiled_dir_by_source",
                        lambda: {"demo-requests-default": "demo_requests_default"})

    assert s.list_sources() == ["demo-requests-default"]
    assert s.capabilities("demo-requests-default") == {"search": "requests"}
    assert s.get_manifest("demo-requests-default")["enabled"] is True
```

- [ ] **Step 5: 生成一次 manifest 并核对**

Run: `python -m novelbase.utils.build_manifest`
Expected: `Generated .../novelbase/utils/_manifest.py (10 sources)`；随后 `python -c "from novelbase.utils import _manifest; print(len(_manifest.SOURCES), len(_manifest.SOURCE_DIRS))"` 输出 `10 10`

- [ ] **Step 6: 更新 `AGENTS.md` 的书源契约段落**

把旧描述（`registry.resolve(name, mode, function, provider?)` + `FUNC_FILE_MAP`）替换为：

```markdown
书源 = `novelbase/sources/{dir}/`，身份在 `source.json`，能力在 `{capability}.py`。
对外 API：`list_sources()` / `get_manifest(name)` / `capabilities(name) -> {capability: mode}` / `resolve(name, capability) -> (fn, mode)`。
`source_name`（source.json 里）与目录名解耦；目录名是合法 Python 标识符，能力通过 `import_module("novelbase.sources.{dir}.{capability}")` 加载。
新增书源：建目录 + 空 `__init__.py` + `source.json` + 4 个能力文件，无注册表改动。
```

- [ ] **Step 7: 运行全量 + 提交**

```bash
python -m pytest tests/ -q
git add novelbase/utils/build_manifest.py tests/check_imports.py tests/test_source_api.py AGENTS.md
git commit -F /tmp/msg.txt   # "docs: 收口 core 层重构（manifest 处理、契约文档、回归基线）"
```

---

## 自审记录（写计划时执行）

**1. spec 覆盖检查**

| spec 章节 | 对应任务 |
|---|---|
| 目录结构（10 个书源目录、目录名规则） | Task 3 |
| source.json 规范（字段集、能力段 ⇔ 文件、规则 1-5） | Task 2（实现）+ Task 3（数据） |
| 加载与分发（4 个 API、`CAPABILITY_META` 去 `file_stem`） | Task 1、Task 4 |
| 配置合并（`default_config` 只是一层） | **不在本计划**（配置加载在 `shared/config.py`，属后续计划）；本计划只让 `source.json` 可读 |
| 数据与兼容（模型 `source_name`） | Task 5 |
| 测试（contracts 重写、source.json 校验、source_name 唯一性、id 稳定性） | Task 2（manifest 校验含能力段 ⇔ `.py` 双向）、Task 4（`get_manifest` 强制 `check_capability_files`）、Task 8（contracts 重写 + `test_source_names_unique` 唯一性 + `test_novel_id_stability.py`：典型 url 哈希写死 + 92xs 不规范化）、Task 9（import 迁移） |
| 私有源 | Task 8 |
| 后端 / CLI / 前端改造 | **最小适配在 Task 10**（`cli/interactive`、`cli/ui`、`cli/config`、`backend/routers/download.py` + 相应测试，用户批准偏离 spec 非目标）；完整改造仍在第 2-5 份计划 |
| 未决事项 1（URL 自动匹配书源） | 不在本计划（需书源声明 URL 模式）；Task 10 删除 `_platform_from_url` 后 URL 解析改用户手选书源 |

**2. 占位符扫描**：无 TBD/TODO；每个代码步骤都给了可运行代码或确切命令。

**3. 类型一致性**：`capabilities()` 全程返回 `dict[str, str]`（`{capability: mode}`）；`resolve()` 全程返回 `tuple[Callable, str]`；`list_sources()` 全程返回 `list[str]`（source_name）。`SearchResult.source_name` 在 Task 5 定义、Task 6 写入（顺序保证 Task 5 在 Task 6 之前）。

**4. 任务间依赖顺序**（重排后自洽）：

| 任务 | 依赖 | 说明 |
|---|---|---|
| Task 4 | Task 2（manifest）、Task 1（CAPABILITY_META） | source.py 新 API |
| Task 5 | 无（只动 models/novel.py） | 先定义 source_name 字段 |
| Task 6 | Task 4（resolve）、Task 5（SearchResult.source_name） | downloader 新签名 |
| Task 7 | Task 6 之后（`_variant_for` 已删） | options 删 name |
| Task 8 | Task 4 | 私有源 + contracts 重写 + id 稳定性 |
| Task 9 | Task 3 | import 路径迁移 |
| Task 10 | Task 4（list_sources）、Task 7（set_api_options 无 name） | backend/cli 最小适配（含 download.py） |
| Task 11 | 全部 | 回归 + build_manifest + 文档 |

**5. 受影响测试文件 → 归属任务映射**（`pytest tests/` 全绿的硬要求，逐文件清点）：

| 测试文件 | 会红原因 | 归属任务 |
|---|---|---|
| `tests/test_source_contracts.py` | 旧 4 参数 `resolve`、旧 `{mode:{variant}}` | Task 8（全量重写） |
| `tests/test_downloader.py` | import `get_source`、旧 `resolve_meta(url, engine)` | Task 6（重写） |
| `tests/test_source_async.py` | import 旧四层路径 + `fanqie._common`（92xs `platform=` 构造点已在 Task 5 Step 4b 删除） | Task 9 |
| `tests/test_browser_sources.py` | import 旧四层路径（7-8 行） | Task 9 |
| `tests/test_options.py` | `APIOptions(name=)`、`.name`、`set_api_options(name=)` | Task 7 |
| `tests/test_engine_httpx.py` | 两处 `set_api_options(name=)` | Task 7 |
| `tests/test_interactive_cli.py` | `monkeypatch register_source`、`_platform_from_url` 旧断言 | Task 10 |
| `tests/test_cli_variant.py` | `import cli.interactive` 崩、`opts.api.name`、`build_options` api 分支 `name=` | Task 10 |
| `tests/test_android_server.py` | `backend.main → routers.download` 顶层 `platform_from_url` 崩 | Task 10（改 `backend/routers/download.py`） |
| `tests/check_imports.py` | `list_sources()` 旧输出（CI 脚本，非 pytest 收集） | Task 11 |

不红（勿动，已核实）：`test_engine_manager.py`、`test_task_manager_async.py`、`test_site_config.py`、`test_shared_user_data.py`、`test_cli_dev_new_variant.py`、`test_exceptions.py`、`test_cli_storage.py`、`test_exporter.py`、`test_export_config.py`、`test_encoding.py`、`test_urls.py`、`test_storage.py`、`test_engine_reconnect.py`、`test_user_db_template.py`、`test_check_public.py`、`conftest.py`。
