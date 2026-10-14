# 下载器分发层 engines 解析器 → 单个 Engine 实例 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `novelbase` 4 个公共下载函数的 `engines`（`engines(mode) -> Engine` 解析器，无类型标注）改为单个 `Engine` 实例，并删除随之失去意义的 `mode_overrides`。

**Architecture:** core 只做「解析能力 + 把注入的引擎原样交给书源能力函数」，不再关心 mode；「选哪个 mode 的引擎」这一步完全归调用方（`shared.config.effective_capabilities()` 给出的有效 mode → 各自的引擎工厂）。`novelbase/source.py` 的 `capabilities()` / `resolve()` 保持原样（`resolve()` 仍返回 `(fn, mode)`，mode 交给调用方用）。破坏性变更由 core 里的一道 `TypeError` 防呆兜住，让旧代码响亮失败。

**Tech Stack:** Python 3.10+ / asyncio / pytest；`novelbase`（核心库）、`backend`（FastAPI + 服务层）、`cli`（非交互 + 交互入口）。前端不涉及。

**Spec:** `docs/superpowers/specs/2026-10-14-downloader-engine-param-design.md`

## Global Constraints

- **不改** `novelbase/source.py` 的 `list_sources()` / `get_manifest()` / `capabilities()` / `resolve()` / `resolve_book_url()` —— 公共 API 稳定（约定：novelbase 函数参数不轻易更改）
- **不改** 11 个书源的能力函数签名（`novelbase/sources/*/{search,novel_info,chapter_list,chapter_content}.py`）
- **不动版本号**：不 bump `novelbase/__init__.py` / `pyproject.toml`，不写 `CHANGELOG.md`
- **不动前端**（`frontend/`）
- 验证命令：`python -m pytest tests -q`；基线 = **513 passed**
- Git：dev 分支可自动提交；**一个方面一条 commit**；**禁止 `git add -A`**（显式列文件）；中文 commit 消息用 `-F <file>` 传入
- 新签名一律 `engine: Engine`（单数、第 3 位不变）；`skip_delay: bool = False` 与 `**kwargs` 语义不变
- 调用方在「能力不在有效映射里」时的 mode 回落统一为 `caps.get(capability) or next(iter(caps.values()), "browser")`（与 `cli.core._get_engine` 既有回落一致）

## Review Focus

以下输入/条件 spec 隐含、但最容易在实现时被忽略（每条都已落到具体任务的测试里）：

1. **测试不得真建引擎** —— 改造后 `_engine_for()` 在**调用处**求值（不再等 core 回调），任何走到它的测试若不 patch 引擎工厂，会真的创建 browser 引擎（启动 Chromium，慢/失败）→ Task 2 第 2 步专门交代
2. **书源未声明某能力** —— 调用方会先建引擎、core 后才报错；回落必须是「该源自己的 mode」，不得因回落引入异 mode 引擎 → Task 2/3/4 的 `_engine_for` / `_mode_for` / `getter` 均按此实现
3. **旧解析器仍在第三方代码里** —— 必须 `TypeError` 且消息含迁移指引，不得静默走错分支 → Task 1 第 1 步的 `test_rejects_legacy_engines_resolver`
4. **browser 引擎首次创建落在事件循环线程** —— 会阻塞整个 FastAPI 数秒，`novel_info` 与 `chapter_content` 两个能力都要预热 → Task 3 第 3 步
5. **多源并发搜索的引擎绑定** —— 每源必须拿自己的引擎，不得退化为「共用首个源的引擎」 → Task 2 的 `test_parallel_same_mode_uses_per_source_engine`

---

## 任务依赖与中间态（必读）

- **Task 1 是前提**，Task 2 / 3 / 4 都依赖它，彼此**互相独立**（可任意顺序、可并行）。
- **Task 1 完成后 `pytest tests -q` 会有失败**（backend / cli 的 fake 仍按旧签名收 `engines`，且旧调用点会触发防呆 `TypeError`）——这是**预期中间态**，Task 2~4 修完即恢复。不要在 Task 1 里顺手改调用方，也不要据此调试。
- Task 5 只在 2/3/4 全部完成后执行。
- `dist/` 与 `.superpowers/` 下的旧签名代码**未入库**（`git ls-files dist` = 0），不在影响面，不要改。

---

### Task 1: core 契约改造（单个 `Engine` 实例 + 防呆 + 导出 `Engine`）

**Files:**
- Modify: `novelbase/core/downloader.py`（4 个函数 + 新增私有 helper）
- Modify: `novelbase/__init__.py`（导出 `Engine`）
- Rename+Rewrite: `tests/test_downloader_mode_overrides.py` → `tests/test_downloader_engine_injection.py`

**Interfaces:**
- Consumes: nothing（起点）
- Produces: 后续任务依赖的精确签名

```python
novelbase.search(source_name: str, query: str, engine: Engine,
                 skip_delay: bool = False, **kwargs) -> SearchResult | None
novelbase.resolve_meta(url: str, source_name: str, engine: Engine,
                       skip_delay: bool = False, **kwargs) -> Novel
novelbase.resolve_chapter_list(url: str, source_name: str, engine: Engine,
                               skip_delay: bool = False, **kwargs) -> Chapters
novelbase.resolve_chapter(chapter: Chapter, source_name: str, engine: Engine,
                          skip_delay: bool = False, **kwargs) -> Chapter | None
novelbase.Engine          # 新导出（Engine 抽象基类）
```

- [ ] **Step 1: 重命名测试文件并写入新契约测试**

```bash
git mv tests/test_downloader_mode_overrides.py tests/test_downloader_engine_injection.py
```

然后把 `tests/test_downloader_engine_injection.py` 内容整体替换为（新契约：core 把注入实例**原样**交给书源能力函数，且不再有 mode 概念）：

```python
"""分发层注入单个 Engine 实例：core 原样交给书源能力函数，不再解析 mode。"""
import asyncio

import pytest

from novelbase.core import downloader
from novelbase.models.novel import Chapter, Novel, SearchResult
from novelbase.utils.urls import make_novel_id


def _patch_resolve(monkeypatch, result, seen: dict):
    """替换 novelbase.source.resolve：返回记录 kwargs 的假能力函数。"""

    async def fake(**kwargs):
        seen.update(kwargs)
        return result

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake, "requests"))


def test_search_passes_injected_engine(monkeypatch):
    engine = object()
    seen: dict = {}
    _patch_resolve(monkeypatch, [], seen)

    assert asyncio.run(downloader.search("src", "q", engine)) is None
    assert seen["engine"] is engine
    assert seen["skip_delay"] is False


def test_search_stamps_source_name(monkeypatch):
    engine = object()
    seen: dict = {}
    _patch_resolve(monkeypatch, [SearchResult(title="t", author="a", url="https://x/1")], seen)

    hit = asyncio.run(downloader.search("src", "q", engine))
    assert hit.source_name == "src"      # 统一打标（书源侧不写死）


def test_resolve_meta_passes_injected_engine(monkeypatch):
    engine = object()
    seen: dict = {}
    _patch_resolve(monkeypatch, Novel(title="t", url="https://x/n1", author="a",
                                      serial=1, description="d"), seen)

    novel = asyncio.run(downloader.resolve_meta("https://x/n1", "src", engine))
    assert seen["engine"] is engine
    assert novel.id == make_novel_id("https://x/n1")     # 中心赋值仍生效


def test_resolve_chapter_list_passes_injected_engine(monkeypatch):
    engine = object()
    seen: dict = {}
    _patch_resolve(monkeypatch, [], seen)

    asyncio.run(downloader.resolve_chapter_list("https://x/n1", "src", engine))
    assert seen["engine"] is engine


def test_resolve_chapter_passes_injected_engine(monkeypatch):
    engine = object()
    seen: dict = {}
    _patch_resolve(monkeypatch, None, seen)
    chapter = Chapter(id="c1", url="https://x/1", novel_id="n1", title="t", order=1)

    asyncio.run(downloader.resolve_chapter(chapter, "src", engine))
    assert seen["engine"] is engine
    assert seen["chapter"] is chapter


def test_rejects_legacy_engines_resolver(monkeypatch):
    """旧的 `engines(mode) -> engine` 解析器必须响亮报错（第三方迁移指引）。"""
    with pytest.raises(TypeError) as ei:
        asyncio.run(downloader.search("src", "q", lambda mode: object()))
    assert "Engine 实例" in str(ei.value)
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `python -m pytest tests/test_downloader_engine_injection.py -q`
Expected: FAIL（`test_*_passes_injected_engine` 因 `engines(mode)` 仍被调用而报 `TypeError: 'object' object is not callable`；`test_rejects_legacy_engines_resolver` 因无防呆而**不抛** TypeError）

- [ ] **Step 3: 改 `novelbase/core/downloader.py`**

顶部 import 增加：`from .engine import Engine`（`engine.py` 不 import 本模块，无循环导入）。

新增模块级私有 helper：

```python
def _reject_legacy_engines(engine) -> None:
    """防呆：`engines(mode) -> engine` 解析器已移除，这里必须是 Engine 实例。"""
    if callable(engine):
        raise TypeError(
            "engine 现在必须传入 Engine 实例（原 engines(mode) 解析器已移除）；"
            "请用 shared.config.effective_capabilities(source_name) 选 mode 后自行 create_engine"
        )
```

`search` 改为（这是其余三个函数的样板）：

```python
async def search(source_name: str, query: str, engine: Engine,
                 skip_delay: bool = False, **kwargs) -> SearchResult | None:
    """搜索**单个**书源，返回第一条命中；该源无结果 → None。

    源报错 / 不支持搜索（`FeatureNotSupportedError`）**向上抛异常**，由调用方决定
    提示还是跳过——多源并发由调用方各自 gather（core 不再吞异常）。
    `engine` 由调用方按该能力的**有效 mode** 建好后传入。
    """
    from ..source import resolve as _resolve

    _reject_legacy_engines(engine)
    fn, _ = _resolve(source_name, "search")
    kwargs["skip_delay"] = skip_delay
    results = await fn(query=query, engine=engine, **kwargs)
    for r in results:                        # 统一打标（书源侧不写死 source_name）
        r.source_name = source_name
    return results[0] if results else None
```

`resolve_meta` / `resolve_chapter_list` / `resolve_chapter` 同构改造，逐函数只做三件事：

1. 签名：`engines` → `engine: Engine`，**删掉 `mode_overrides: dict[str, str] | None = None`**（参数序里它原本紧跟 `skip_delay`，删后无位置冲突）
2. 函数体开头加 `_reject_legacy_engines(engine)`
3. 删掉 `mode = (mode_overrides or {}).get(cap) or mode` 一行；`fn, mode = _resolve(...)` 改 `fn, _ = _resolve(...)`；`engine=engines(mode)` 改 `engine=engine`

保留不动：`resolve_meta` 的 `try/except (ValueError, ImportError) → SourceNotFoundError` 包装、`novel.id = make_novel_id(novel.url)`、四处 `kwargs["skip_delay"] = skip_delay`、`export()` / `get_exporters()` / `get_exporter_options()`。

- [ ] **Step 4: 改 `novelbase/__init__.py`**

```python
from .core.engine import Engine, create_engine
```

`__all__` 列表里 `"create_engine"` 一行后加 `"Engine"`。

- [ ] **Step 5: 运行测试，确认通过**

Run: `python -m pytest tests/test_downloader_engine_injection.py -q`
Expected: `7 passed`

- [ ] **Step 6: 验证公共签名与导出**

Run: `python -c "import inspect, novelbase; print(novelbase.Engine); print(inspect.signature(novelbase.resolve_meta)); print(inspect.signature(novelbase.search))"`
Expected: 打印 `<class 'novelbase.core.engine.Engine'>`，两个签名都含 `engine: 'Engine'` 且**不含** `mode_overrides`

- [ ] **Step 7: Commit**

```bash
printf 'refactor(novelbase): 下载器 4 个公共函数收单个 Engine 实例，删除 mode_overrides\n\nengines(mode) -> Engine 解析器改为单个 Engine 实例（仍在第 3 位），并删除随之\n失去意义的 mode_overrides；core 不再关心 mode。新增防呆：传旧解析器抛 TypeError。\n同时导出 Engine 抽象基类（公共签名需要）。\n' > "$TEMP/nld_c1.txt"
git add novelbase/core/downloader.py novelbase/__init__.py tests/test_downloader_engine_injection.py
git commit -F "$TEMP/nld_c1.txt"
```

（`git mv` 的删除侧 `tests/test_downloader_mode_overrides.py` 由 `git add` 同一次提交带上；提交前 `git status --short` 确认无遗漏。中文消息一律走 `-F` 文件——`cmd` 引号会吞中文。后续任务的 commit 步骤同此写法，只改文件名与消息。）

---

### Task 2: backend download 路由改造

**Files:**
- Modify: `backend/routers/download.py`（helper `:32-39`；调用点 `:75-76, :88-89, :105-106, :125-126, :141-142, :157-158`；模块 docstring 第 4 行）
- Modify: `tests/test_backend_download_routes.py`

**Interfaces:**
- Consumes: Task 1 的 `resolve_meta(url, source_name, engine, ...)` / `resolve_chapter_list(...)` / `search(source_name, query, engine, ...)`
- Produces: `backend.routers.download._engine_for(source_name: str, capability: str) -> Engine`

- [ ] **Step 1: 改 helper**

把 `_engines_for` 与 `_mode_overrides` 整体替换为：

```python
def _engine_for(source_name: str, capability: str):
    """按书源 + 能力取引擎：mode = 用户层覆盖后的**有效** mode。

    能力不在该源的有效映射里时，回落该源首个有效 mode —— 只为避免在错误路径上
    启一个「异 mode」引擎；core 随后会以 `ValueError` 拒绝这次调用（书源未声明该能力）。
    """
    caps = effective_capabilities(source_name)
    mode = caps.get(capability) or next(iter(caps.values()), "browser")
    return get_cached_engine(source_name, mode)
```

模块 docstring 第 4 行的「由路由以关键字 `mode_overrides=` 透传给 core 分发层」改为「由路由按能力取好引擎实例后传给 core 分发层」。

- [ ] **Step 2: 改 6 个调用点**

| 位置 | capability |
|---|---|
| `search_novels` URL 直达分支（`resolve_meta`） | `"novel_info"` |
| `search_novels` 单书源（`search`） | `"search"` |
| `search_novels` `_search_one`（`search`） | `"search"` |
| `resolve_meta_route`（`resolve_meta`） | `"novel_info"` |
| `get_remote_novel`（`resolve_meta`） | `"novel_info"` |
| `resolve_chapter_list_route`（`resolve_chapter_list`） | `"chapter_list"` |

统一形态：`_engines_for(source_name), mode_overrides=_mode_overrides(source_name)` → `_engine_for(source_name, "<capability>")`（`mode_overrides=` 关键字一并删除）。`_search_one` 里的注释「每个源用自己的 `_engines_for(name)`」改为「`_engine_for(name, ...)`」。

- [ ] **Step 3: 更新测试**（`tests/test_backend_download_routes.py`）

**关键**：改造后 `_engine_for()` 在路由函数体里**立即求值**。凡会走到它的测试，都必须 `monkeypatch.setattr(dl, "get_cached_engine", ...)`，否则会真的创建 browser 引擎。逐个核对下表：

| 测试 | 改动 |
|---|---|
| `test_search_empty_source_uses_default_sources` | **新增** `monkeypatch.setattr(dl, "get_cached_engine", lambda name, mode: object())`；fake 签名 `engines` → `engine` |
| `test_search_single_source_binds_engine` | fake 签名 `engine`；`captured["engine"] = engine`（原为 `engines("requests")`）；**新增** `monkeypatch.setattr(dl, "effective_capabilities", lambda n: {"search": "requests"})`；`assert seen == [("92xs-requests-default", "requests")]` 不变 |
| `test_parallel_same_mode_uses_per_source_engine` | fake 签名 `engine`；`per_source_engine[source_name] = engine`；**新增** `effective_capabilities` → `{"search": "requests"}`（否则回落 `browser`，`engine_calls` 断言会变成 `browser`）；其余断言不变 |
| `test_parallel_one_source_fails_others_survive` | fake 签名 `engine`；**新增** `effective_capabilities` → `{"search": "requests"}` |
| `test_url_search_returns_source_name` / `test_resolve_meta_route_with_source` / `test_chapter_list_route_with_source` | 无需改（只 monkeypatch `novelbase.source.resolve` + 引擎工厂，签名由 core 决定） |
| `test_search_uses_selected_sources` / `test_search_default_sources_when_param_absent` | fake 签名 `engine`（`effective_capabilities` 与 `get_cached_engine` 已 patch） |
| `test_search_passes_mode_overrides_by_keyword` | **改名** `test_search_uses_effective_mode_for_engine`：`effective_capabilities` → `{"search": "browser"}`；fake 签名 `(source_name, query, engine, skip_delay=False, **kw)` 记录 `captured["engine"] = engine`；断言 `seen == [("92xs-requests-default", "browser")]` 且 `captured["engine"] is not None` |
| `test_resolve_meta_route_passes_mode_overrides_by_keyword` | 改名 `test_resolve_meta_route_uses_effective_mode_for_engine`：`{"novel_info": "browser"}`；断言 `seen == [("fanqie-requests-default", "browser")]` + `captured["engine"] is not None` |
| `test_get_remote_novel_passes_mode_overrides_by_keyword` | 改名 `test_get_remote_novel_uses_effective_mode_for_engine`：`{"novel_info": "browser"}`；断言同上（source_name = `92xs-requests-default`） |
| `test_chapter_list_route_passes_mode_overrides_by_keyword` | 改名 `test_chapter_list_route_uses_effective_mode_for_engine`：`{"chapter_list": "browser"}`；断言 `seen == [("92xs-requests-default", "browser")]` + `captured["engine"] is not None` |

四个改名测试统一用 `seen = _patch_engine_factory(monkeypatch)` 拿到 `(source_name, mode)` 记录，从而钉住「用的是有效 mode 而不是书源声明值」。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_backend_download_routes.py -q`
Expected: 全 PASS

若出现 Chromium/Playwright 相关超时或报错，说明有测试漏 patch `dl.get_cached_engine` —— 回到 Step 3 的表逐条核对，**不要**改成真建引擎。

- [ ] **Step 5: Commit**

```bash
printf 'refactor(backend): download 路由改为按能力取引擎实例传给 core\n\n_engines_for(source_name) + _mode_overrides(source_name) 替换为\n_engine_for(source_name, capability)：按 effective_capabilities() 的有效 mode 取引擎。\n测试新增 effective_capabilities / get_cached_engine 隔离，避免真建引擎。\n' > "$TEMP/nld_c2.txt"
git add backend/routers/download.py tests/test_backend_download_routes.py
git commit -F "$TEMP/nld_c2.txt"
```

---

### Task 3: task_manager 改造（含预热扩到 `chapter_content`）

**Files:**
- Modify: `backend/services/task_manager.py`（`:287-330` 的引擎构造与预热、`:404` 的章节调用）
- Modify: `tests/test_novel_source_writes.py`（`test_task_manager_passes_mode_overrides_to_core`）

**Interfaces:**
- Consumes: Task 1 的 `resolve_meta(url, source_name, engine, ...)` / `resolve_chapter(chapter, source_name, engine, ...)`
- Produces: nothing（终端调用方）

- [ ] **Step 1: 改写引擎构造与预热**

把这段（`engines_cache` 闭包 + `primary_mode` 预热）整体替换为：

```python
    _caps = effective_capabilities(source_name)

    def _mode_for(capability: str) -> str:
        """该能力的有效 mode；能力缺失时回落该源首个有效 mode（core 随后会报错）。"""
        return _caps.get(capability) or next(iter(_caps.values()), "browser")

    # 预热：get_cached_engine 是同步调用，browser 模式首次创建会启动 Chromium，
    # 若首次创建落在事件循环线程会阻塞整个 FastAPI（含其它任务、暂停/取消接口）数秒。
    # 引擎现在由本函数直接取（不再由 core 经解析器回调），故两个用到的能力
    # （novel_info / chapter_content）都先经 to_thread 建好；同 mode 只建一次。
    for _m in dict.fromkeys((_mode_for("novel_info"), _mode_for("chapter_content"))):
        await asyncio.to_thread(get_cached_engine, source_name, _m)

    meta_engine = get_cached_engine(source_name, _mode_for("novel_info"))
    chapter_engine = get_cached_engine(source_name, _mode_for("chapter_content"))
```

`_caps` 的定义从原预热块下方**上移**到这里（原处删除）。`src_conc`、`source_concurrency` 那一行保持不动。

- [ ] **Step 2: 改两个调用点**

```python
meta = await resolve_meta(novel_url, source_name, meta_engine)
downloaded = await resolve_chapter(ch, source_name, chapter_engine)
```

（删掉各自的 `mode_overrides=_caps`。）

- [ ] **Step 3: 重写测试断言**

`tests/test_novel_source_writes.py::test_task_manager_passes_mode_overrides_to_core` 改名为 `test_task_manager_passes_engine_instance_to_core`，docstring 改为「task_manager 必须把按**有效 mode**取到的引擎实例传给 core」；并把 mock 与断言改为：

```python
    overrides = {"novel_info": "browser", "chapter_content": "browser"}
    seen = {}

    engines_seen: list[tuple[str, str]] = []

    def fake_get_cached_engine(name, mode):
        engines_seen.append((name, mode))
        return f"engine:{name}:{mode}"

    async def fake_resolve_meta(url, source_name, engine, skip_delay=False, **kw):
        seen["meta"] = engine
        return novel

    async def fake_resolve_chapter(ch, source_name, engine, skip_delay=False, **kw):
        seen["chapter"] = engine
        return Chapter(id=ch.id, url=ch.url, novel_id=ch.novel_id,
                       title=ch.title, order=ch.order)
```

（`monkeypatch.setattr(task_manager, "get_cached_engine", ...)` 改指向 `fake_get_cached_engine`；`config_service.effective_capabilities` 仍指向 `overrides`；其余如 `create_storage` / `set_novel_source` / `task` 字典保持原样。）

末尾断言改为：

```python
    assert seen["meta"] == "engine:fanqie-requests-default:browser"
    assert seen["chapter"] == "engine:fanqie-requests-default:browser"
    assert engines_seen == [("fanqie-requests-default", "browser")]   # 预热去重：同 mode 只建一次
```

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_novel_source_writes.py -q`
Expected: 全 PASS

- [ ] **Step 5: Commit**

```bash
printf 'refactor(task_manager): 按能力取引擎实例并预热 novel_info/chapter_content\n\n删除 engines_cache 解析器闭包；改为 _mode_for(capability) + get_cached_engine，\n预热扩到 chapter_content（browser 引擎在事件循环线程首建会阻塞整个 FastAPI）。\n' > "$TEMP/nld_c3.txt"
git add backend/services/task_manager.py tests/test_novel_source_writes.py
git commit -F "$TEMP/nld_c3.txt"
```

---

### Task 4: CLI 改造（`cli/core.py` + `cli/interactive.py` + `cli/main.py`）

**Files:**
- Modify: `cli/core.py`（`_make_engines` `:58-74` → `_make_engine_getter`；`_do_download_inner` 签名与 3 处调用；update 路径 2 处调用）
- Modify: `cli/interactive.py`（`_make_engines` `:34-45` → `_make_engine_getter`；4 处调用）
- Modify: `cli/main.py`（`cmd_search` `:139-160`、`cmd_info` `:249-254`）
- Modify: `tests/test_cli_engine_modes.py`、`tests/test_cli_effective_mode.py`

**Interfaces:**
- Consumes: Task 1 的 4 个新签名
- Produces: `cli.core._make_engine_getter(source_name: str, options_hook=None) -> Callable[[str], Engine]`，返回值带 `.cache: dict[str, Engine]`（键 = 能力名）

- [ ] **Step 1: `cli/core.py` —— 替换 `_make_engines`**

```python
def _make_engine_getter(source_name: str, options_hook=None):
    """构造 `get(capability) -> engine`：按能力的**有效 mode**（`effective_capabilities`）懒建并缓存。

    `options_hook(options)` 在 `create_engine` 之前调用——供 cli.main 注入导出配置装配
    （`cli.core` 不能反向 import `cli.main`，故用依赖注入）。

    缓存暴露为 `get.cache`（键 = 能力名），便于调用方在结束时 close 所有引擎。
    """
    cache: dict[str, object] = {}

    def get(capability: str):
        if capability not in cache:
            caps = effective_capabilities(source_name)
            mode = caps.get(capability) or next(iter(caps.values()), "browser")
            cache[capability] = _get_engine(source_name, mode, options_hook)
        return cache[capability]

    get.cache = cache  # type: ignore[attr-defined]
    return get
```

`_get_engine(source_name, mode=None, options_hook=None)` **保持不变**（mode 缺省回落首个能力 mode 的行为与用例保留）。

- [ ] **Step 2: `cli/core.py` —— 调用点**

- `_do_download_inner(..., skip_export: bool = True, engine_getter=None)`（参数由 `engines=None` 改名）：函数体里 `if engines is None: engines = _make_engines(source_name)` → `if engine_getter is None: engine_getter = _make_engine_getter(source_name)`
- 同函数删掉 `_overrides = effective_capabilities(source_name)` 一行
- `resolve_meta(url, source_name, engine_getter("novel_info"), skip_delay=skip_delay)`（删 `mode_overrides=_overrides`）
- `resolve_chapter_list(novel.url, source_name, engine_getter("chapter_list"), skip_delay=skip_delay)`（同上）
- `resolve_chapter(ch, source_name, engine_getter("chapter_content"))`（同上）
- update 路径：`engines = _make_engines(source_name)` + `_overrides = ...` → `get = _make_engine_getter(source_name)`；两处调用改 `get("chapter_list")` / `get("chapter_content")`；结尾 `for eng in getattr(engines, "cache", {}).values():` → `for eng in get.cache.values():`

- [ ] **Step 3: `cli/interactive.py` —— 同形改造**

`_make_engines` → `_make_engine_getter`（与本文件 `_get_engine` 配套，`options_hook` 参数可省略）；4 处调用点：

| 位置 | capability |
|---|---|
| `do_search` URL 分支（`resolve_meta`） | `"novel_info"` |
| `do_search` 关键字分支 `_one`（`search`） | `"search"` |
| `do_download`（传给 `_do_download_inner`） | 传 `engine_getter=get`，不传具体能力 |
| `_update_one_async`（`resolve_chapter_list` / `resolve_chapter`） | `"chapter_list"` / `"chapter_content"` |

三处收尾 `for eng in getattr(engines, "cache", {}).values():` → `for eng in get.cache.values():`；各调用点删除 `mode_overrides=...`（含 `effective_capabilities` 的临时变量）。

- [ ] **Step 4: `cli/main.py` —— 2 处调用**

- `cmd_search`：`from cli.core import _make_engines` → `_make_engine_getter`；`engines = _make_engines(name)` → `get = _make_engine_getter(name)`；`search(name, args.query, get("search"), page=args.page)`；收尾 `for eng in engines.cache.values():` → `for eng in get.cache.values():`；删除 `mode_overrides=effective_capabilities(name)`
- `cmd_info`：`engines = _make_engines(source_name, options_hook=_apply_export_options)` → `get = _make_engine_getter(source_name, options_hook=_apply_export_options)`；`resolve_meta(args.url, source_name, get("novel_info"))`；删除 `mode_overrides=effective_capabilities(source_name)`

保留「**每源各用自己的引擎**」的既有不变量（`cmd_search` 的 `_search_one` 仍每源一个 getter）。

- [ ] **Step 5: 更新 `tests/test_cli_engine_modes.py`**

`test_make_engines_builds_per_mode_and_applies_hook` 改名为 `test_engine_getter_builds_per_capability_and_applies_hook`，内容替换为按**能力**建引擎：

```python
def test_engine_getter_builds_per_capability_and_applies_hook(monkeypatch):
    built: list[str] = []
    hooked: list[str] = []

    monkeypatch.setattr(cli.core, "build_options", lambda name, mode: _FakeOptions(mode))
    monkeypatch.setattr(cli.core, "effective_capabilities",
                        lambda n: {"search": "requests", "chapter_content": "browser"})

    def fake_create(options):
        built.append(options.mode)
        return f"engine:{options.mode}"

    monkeypatch.setattr(cli.core, "create_engine", fake_create)

    get = cli.core._make_engine_getter("x-requests-default",
                                       options_hook=lambda o: hooked.append(o.mode))

    assert get("search") == "engine:requests"
    assert get("search") is get("search")          # 同能力复用缓存
    assert get("chapter_content") == "engine:browser"

    assert built == ["requests", "browser"]
    assert hooked == ["requests", "browser"]
    assert set(get.cache) == {"search", "chapter_content"}
```

`test_get_engine_defaults_to_first_capability_mode` **保持不变**。

- [ ] **Step 6: 更新 `tests/test_cli_effective_mode.py`**

`test_download_inner_passes_mode_overrides_by_keyword` 改名为 `test_download_inner_passes_engine_per_capability`：

```python
def test_download_inner_passes_engine_per_capability(monkeypatch):
    """下载路径必须按能力取引擎：novel_info / chapter_list 各传对应实例。

    （chapter_content 的映射由 test_cli_engine_modes.py 的 getter 用例覆盖：
    本用例让章节列表为空以终止流程，避免触发存储与导出。）
    """
    monkeypatch.setattr(cli_core, "effective_capabilities",
                        lambda n: {"novel_info": "requests", "chapter_list": "requests",
                                   "chapter_content": "browser"})
    monkeypatch.setattr(cli_core, "build_options",
                        lambda name, mode: types.SimpleNamespace(mode=mode))
    monkeypatch.setattr(cli_core, "create_engine", lambda options: f"engine:{options.mode}")
    captured = {}

    async def fake_resolve_meta(url, source_name, engine, skip_delay=False, **kw):
        captured["meta"] = (engine, skip_delay)
        return types.SimpleNamespace(url=url, title="T", author="A")

    async def fake_resolve_chapter_list(url, source_name, engine, skip_delay=False, **kw):
        captured["cl"] = (engine, skip_delay)
        return []

    monkeypatch.setattr(cli_core, "resolve_meta", fake_resolve_meta)
    monkeypatch.setattr(cli_core, "resolve_chapter_list", fake_resolve_chapter_list)

    asyncio.run(cli_core._do_download_inner(KNOWN, "https://x/page/1", "default", {}))

    assert captured["meta"] == ("engine:requests", False)
    assert captured["cl"] == ("engine:requests", False)
```

（不再传 `engines=`；`_do_download_inner` 内部自建 getter。其余测试不动。）

- [ ] **Step 7: 运行测试**

Run: `python -m pytest tests/test_cli_engine_modes.py tests/test_cli_effective_mode.py -q`
Expected: 全 PASS

- [ ] **Step 8: Commit**

```bash
printf 'refactor(cli): 改为按能力取引擎实例传给 core\n\ncli/core.py 与 cli/interactive.py 的 _make_engines(mode 解析器) 改为\n_make_engine_getter(capability)（.cache 键 = 能力名，收尾 close 不变）；\ncli/main.py 的 cmd_search / cmd_info 同步。\n' > "$TEMP/nld_c4.txt"
git add cli/core.py cli/interactive.py cli/main.py tests/test_cli_engine_modes.py tests/test_cli_effective_mode.py
git commit -F "$TEMP/nld_c4.txt"
```

---

### Task 5: 文档同步 + 全量验收

**Files:**
- Modify: `docs/session-prompt.md:48`（「下载器 API」条）
- Modify: `docs/project/sources.md:98`
- Modify: `docs/project/cli.md:22`

**Interfaces:**
- Consumes: Task 1~4 全部完成后的仓库状态
- Produces: nothing（终端任务）

- [ ] **Step 1: 改 `docs/session-prompt.md` 第 48 行**

新内容（一条，替换原条目的签名与 `engines` 说明段）：

```markdown
- **下载器 API**（2026-10-14 修订 engine / 删除 mode_overrides）：`async search(source_name, query, engine, skip_delay=False, **kwargs) -> SearchResult | None`（**单源**搜索，返回该源**第一条**命中，无结果 → `None`；源报错 / `FeatureNotSupportedError` **上抛**） / `resolve_meta(url, source_name, engine, skip_delay=False, **kwargs)` / `resolve_chapter_list(url, source_name, engine, skip_delay=False, **kwargs)` / `resolve_chapter(chapter, source_name, engine, skip_delay=False, **kwargs)`。`engine` 是**单个 `Engine` 实例**（`novelbase.Engine`，第 3 位），由调用方按该能力的**有效 mode**（`shared.config.effective_capabilities(source_name)`）自行 `create_engine` 后注入；core **不关心 mode**（原 `mode_overrides` 参数已删除），传旧 `engines(mode)` 解析器会抛 `TypeError`；`skip_delay=False` 仍经 `**kwargs` 传递到底层函数
```

- [ ] **Step 2: 改 `docs/project/sources.md:98`**

把「core 分发层 `novelbase/core/downloader.py` 的 4 个函数接受可选 `mode_overrides`（能力名 → mode），…」整句改为「core 分发层 4 个函数接受**单个 `Engine` 实例**（调用方按 `effective_capabilities()` 选有效 mode 后建好），core 自身不解析 mode」——保持该条其余文字（能力声明 / `resolve()` 语义）不变。

- [ ] **Step 3: 改 `docs/project/cli.md:22`**

把「CLI 按有效 mode 建引擎并透传 `mode_overrides`」改为「CLI 按有效 mode 建引擎（`_make_engine_getter(capability)`）后注入 core」。

- [ ] **Step 4: 全量测试**

Run: `python -m pytest tests -q`
Expected: `passed`，且总数 **≥ 513**、`0 failed`

- [ ] **Step 5: 静态验收（spec §10）**

```bash
grep -rn "mode_overrides" --include=*.py backend cli novelbase shared tests   # 期望：零命中
grep -rn "engines" --include=*.py novelbase/ | grep -v __pycache__            # 期望：零命中
python -c "import inspect, novelbase; print(hasattr(novelbase, 'Engine')); print(inspect.signature(novelbase.search))"
```

Expected: 两条 grep 无输出；`True` + 签名含 `engine: 'Engine'`

（grep 只扫入库目录：`dist/` 与 `.superpowers/` 是**未入库**的历史快照，仍带旧签名，不参与验收。）

- [ ] **Step 6: CLI 冒烟（需网络，可择书源）**

```bash
python cli.py info --source fanqie-requests-default --url "<一个真实书籍 URL>"
python cli.py search --source fanqie-requests-default "<关键词>"
python cli.py update
```

Expected: 三条命令行为与改造前一致，无 `TypeError`、无 `close()` 相关异常；`update` 结束后引擎正常释放

- [ ] **Step 7: 后端接口冒烟（spec §10.7；需网络）**

终端 A：

```bash
uvicorn backend.main:app --port 8000
```

终端 B：

```bash
curl "http://127.0.0.1:8000/api/v2/download/search?query=<关键词>&source=fanqie-requests-default"
curl -X POST "http://127.0.0.1:8000/api/v2/download/novel?source=fanqie-requests-default" \
     -H "Content-Type: application/json" -d '{"url":"<一个真实书籍 URL>"}'
```

Expected: 两个端点都返回 200 与 `{ok, message, data}` 形态；服务端日志无 `TypeError`；`sources` 缺省的搜索仍并发全部书源。

（本改动**不涉及前端代码**，前端搜索页 / URL 解析只需确认接口契约未破——如需人工确认，按 `docs/project/development.md` 的 UI 冒烟方式执行。）

- [ ] **Step 8: Commit**

```bash
printf 'docs: 同步引擎注入契约（engines 解析器 -> 单个 Engine 实例）\n\nsession-prompt 关键约定、project/sources、project/cli 三处同步新签名与\n「引擎由调用方按有效 mode 建好注入」的职责划分。\n' > "$TEMP/nld_c5.txt"
git add docs/session-prompt.md docs/project/sources.md docs/project/cli.md
git commit -F "$TEMP/nld_c5.txt"
```

---

## 完成后

`git rev-list --count origin/dev..dev` 给出的领先提交数会增加 5 条（Task 1~5 各一条）。合并 main、推送、构建 workflow 均需用户明确指示后才执行（main 例外原则）。
