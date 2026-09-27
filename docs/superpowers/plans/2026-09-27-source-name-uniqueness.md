# source_name 唯一性检测 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让「`source_name` 全局唯一」成为实现层的硬约束——内置根与私有根里任何两个目录声明同一个 `source_name`，加载期立即抛 `DuplicateSourceNameError`，而不是静默选一个源继续跑。

**Architecture:** 在 `novelbase/sources/manifest.py` 加一个多根扫描函数 `scan_source_names(roots, *, strict=False)` 作为唯一检测点；`novelbase/source.py` 删掉按名字反查目录的 `_iter_source_dirs()`，收敛成「一张全局唯一表 + 单目录查询」；`novelbase/utils/build_manifest.py` 复用同一函数在构建期拦截（编译模式的 `SOURCE_DIRS` 撞名会静默覆盖 + 产出重复条目）。三处共用一份实现，测试兜底交叉验证。

**Tech Stack:** Python 3.10、pytest、`pathlib`、`importlib`。无新依赖。

**Spec:** `docs/superpowers/specs/2026-09-27-source-name-uniqueness-design.md`

## Global Constraints

- **口径：严格全局唯一。** 内置根 `novelbase/sources/` 与私有根 `NLD_PRIVATE_SOURCES` 是**同一命名空间**；任何两个目录声明同一个 `source_name` 一律报错，**包括私有源复用内置 id**。不留 `overrides` 之类的逃生舱。
- **被取消的机制**：`resolve()` 的「同名能力内置优先、内置缺失再用私有补齐」不再存在。私有源必须自带独立 `source_name`。
- **异常类型**：新增 `DuplicateSourceNameError`，必须是 `ManifestError` 的子类（`from .manifest import ...`，`class DuplicateSourceNameError(ManifestError)`），使既有 `pytest.raises(ManifestError)` 与 `except ManifestError` 仍然成立。
- **单一检测点**：唯一性检测只在 `scan_source_names()` 里实现；`source.py` 与 `build_manifest.py` 都调用它，不得各自复制判断逻辑。
- **不做**：不加加载缓存、不检测目录名与 `source_name` 的一致性、不检测 `sites/*.yaml` 孤儿、不改「单源 manifest 非法」的既有容错分工（运行时跳过 / `get_manifest()` 致命 / 构建期致命）。
- **提交**：中文消息，一个 task 一条 commit，**禁止 `git add -A`**（显式列出文件）。dev 分支，可直接提交（不要推送，等最后一起推）。
- **验证命令**：`python -m pytest tests -q`（本机基线 **484 passed**）；单文件用 `python -m pytest tests/<file>.py -q`。
- **环境**：Windows + Git Bash（`D:/Git/bin/bash.exe`）；shell 报 `could not find /tmp` 是既有噪声，忽略。

## File Structure

| 文件 | 职责 | 本计划中的改动 |
|------|------|----------------|
| `novelbase/sources/manifest.py` | 单源 `source.json` 加载校验 + **多目录级唯一性扫描** | Task 1 新增 `DuplicateSourceNameError`、`scan_source_names()` |
| `novelbase/source.py` | 公共 API（发现/分发） | Task 2 删 `_iter_source_dirs()`、加 `_source_dirs()`/`_source_dir()`/`_resolve_private()`、改 5 个公开函数的非编译分支 |
| `tests/test_source_names_unique.py` | 实现层唯一性检测的测试 | Task 1 新建（`scan_source_names` 单测）、Task 2 追加（入口级 raise） |
| `tests/test_source_contracts.py` | 既有 source 契约测试 | Task 2 改写 `test_builtin_wins_over_private`（该机制已取消） |
| `novelbase/utils/build_manifest.py` | 生成 `_manifest.py`（Nuitka 编译产物用） | Task 3 改用 `scan_source_names(..., strict=True)` + 撞名中止 |
| `tests/test_build_manifest_unique.py` | 构建期拦截测试 | Task 3 新建 |
| `docs/project/sources.md`、`docs/session-prompt.md`、`AGENTS.md` | 文档 | Task 4 同步 6 处口径（3 个文件） |

**任务依赖**：Task 1 → (Task 2 ∥ Task 3) → Task 4。Task 2 与 Task 3 写路径不重叠，可并行；Task 4 描述实现，放最后。

---

### Task 1: `manifest.scan_source_names()` —— 唯一检测点

**Files:**
- Modify: `novelbase/sources/manifest.py`
- Test: `tests/test_source_names_unique.py`（新建）

**Interfaces:**
- Produces:
  - `class DuplicateSourceNameError(ManifestError)` —— 撞名专用异常，子类化 `ManifestError`
  - `scan_source_names(roots: Iterable[Path], *, strict: bool = False) -> dict[str, Path]`
    —— 扫多个根，返回 `{source_name: 目录}`；同名出现两次（含跨根）抛 `DuplicateSourceNameError`；`strict=False` 时 `load_manifest()` 抛错的目录跳过，`strict=True` 时冒泡；根不存在则跳过
- Consumes: 已有的 `load_manifest()`、`MANIFEST_NAME`、`ManifestError`（同文件）

- [ ] **Step 1: 写失败测试**

新建 `tests/test_source_names_unique.py`：

```python
"""`source_name` 全局唯一：实现层检测（spec: docs/superpowers/specs/2026-09-27-source-name-uniqueness-design.md）。"""
import json
from pathlib import Path

import pytest

from novelbase.sources.manifest import (
    DuplicateSourceNameError, ManifestError, scan_source_names,
)


def _source(root: Path, dirname: str, source_name: str) -> Path:
    """在 root 下造一个最小书源目录（source.json + search.py）。"""
    d = root / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "source.json").write_text(json.dumps({
        "source_name": source_name,
        "enabled": True,
        "default_config": {"search": {"mode": "requests"}},
    }, ensure_ascii=False), encoding="utf-8")
    (d / "search.py").write_text(
        "async def search(query, engine, **kwargs):\n    return ()\n", encoding="utf-8")
    return d


def _invalid_source(root: Path, dirname: str) -> Path:
    """坏 JSON 的 source.json（load_manifest 会抛 ManifestError）。"""
    d = root / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "source.json").write_text('{"source_name": ', encoding="utf-8")
    return d


def test_duplicate_in_same_root_raises(tmp_path):
    _source(tmp_path, "demo_a", "demo-requests-default")
    _source(tmp_path, "demo_b", "demo-requests-default")
    with pytest.raises(DuplicateSourceNameError, match="重复"):
        scan_source_names([tmp_path])


def test_duplicate_across_roots_raises(tmp_path):
    """全局唯一：第二个根里出现已见过的 source_name 也算重复。"""
    builtin, private = tmp_path / "builtin", tmp_path / "private"
    _source(builtin, "demo_a", "demo-requests-default")
    _source(private, "demo_b", "demo-requests-default")
    with pytest.raises(DuplicateSourceNameError, match="demo-requests-default"):
        scan_source_names([builtin, private])


def test_distinct_names_across_roots_ok(tmp_path):
    builtin, private = tmp_path / "builtin", tmp_path / "private"
    _source(builtin, "demo_a", "demo-requests-default")
    _source(private, "demo_b", "other-requests-default")
    assert sorted(scan_source_names([builtin, private])) == [
        "demo-requests-default", "other-requests-default"]


def test_invalid_manifest_skipped_when_not_strict(tmp_path):
    _source(tmp_path, "demo_a", "demo-requests-default")
    _invalid_source(tmp_path, "demo_bad")
    assert list(scan_source_names([tmp_path])) == ["demo-requests-default"]


def test_invalid_manifest_raises_when_strict(tmp_path):
    _invalid_source(tmp_path, "demo_bad")
    with pytest.raises(ManifestError):
        scan_source_names([tmp_path], strict=True)


def test_empty_and_missing_roots(tmp_path):
    assert scan_source_names([]) == {}
    assert scan_source_names([tmp_path / "nope"]) == {}


def test_underscore_and_manifestless_dirs_skipped(tmp_path):
    _source(tmp_path, "demo_a", "demo-requests-default")
    (tmp_path / "_private").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "no_manifest").mkdir()
    assert list(scan_source_names([tmp_path])) == ["demo-requests-default"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_source_names_unique.py -q`
Expected: FAIL / collection error —— `ImportError: cannot import name 'DuplicateSourceNameError'`

- [ ] **Step 3: 实现**

在 `novelbase/sources/manifest.py` 里改导入并新增代码。顶部现有：

```python
import json
from pathlib import Path
from typing import Any
```

改为：

```python
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any
```

`ManifestError` 定义（`class ManifestError(ValueError):`）之后紧接新增：

```python
class DuplicateSourceNameError(ManifestError):
    """同一个 `source_name` 被两个书源目录声明（全局唯一被破坏）。"""
```

在 `check_capability_files()` 之后（`_capability_names()` 之前）新增：

```python
def scan_source_names(roots: Iterable[Path], *, strict: bool = False) -> dict[str, Path]:
    """扫多个根下的书源目录，返回 `{source_name: 目录}`。

    `source_name` 是全局唯一 id：内置根与私有根是同一命名空间，同一个名字出现
    第二次（含跨根）即抛 `DuplicateSourceNameError`。

    - 非目录项、`_` 开头的目录、无 `source.json` 的目录 → 跳过
    - 单源 `load_manifest()` 抛 `ManifestError`：`strict=True` 冒泡，否则跳过该目录
      （沿用运行时容错；构建期用 `strict=True` 保证不漏）
    - 根不存在或不是目录 → 跳过该根
    - `roots` 有序，先出现的目录先占名（报错消息里是「先占者 vs 后来者」）
    """
    found: dict[str, Path] = {}
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            if not (entry / MANIFEST_NAME).is_file():
                continue
            try:
                manifest = load_manifest(entry)
            except ManifestError:
                if strict:
                    raise
                continue
            name = manifest["source_name"]
            if name in found:
                raise DuplicateSourceNameError(
                    f"source_name {name!r} 重复：{found[name]} 与 {entry} 都声明了它。"
                    f"请给其中一个书源换 source_name（目录名可不变，二者本就解耦）"
                )
            found[name] = entry
    return found
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_source_names_unique.py -q`
Expected: `7 passed`

- [ ] **Step 5: 回归**

Run: `python -m pytest tests -q`
Expected: `491 passed`（基线 484 + 新增 7）

- [ ] **Step 6: 提交**

```bash
git add novelbase/sources/manifest.py tests/test_source_names_unique.py
git commit -F <(printf 'feat: source_name 全局唯一检测（manifest.scan_source_names）\n')
```

（Windows Git Bash 下中文消息用 `-F`；也可先 `printf ... > "$LOCALAPPDATA/Temp/msg.txt"` 再 `git commit -F "$LOCALAPPDATA/Temp/msg.txt"`。）

---

### Task 2: `source.py` 收敛成单一扫描入口

**Files:**
- Modify: `novelbase/source.py`（模块 docstring、导入、`_iter_source_dirs()` 52-74、`list_sources()` 77-97、`get_manifest()` 100-113、`capabilities()` 116-122、`resolve()` 138-185）
- Modify: `tests/test_source_contracts.py:123-152`（改写 `test_builtin_wins_over_private`）
- Modify: `tests/test_source_names_unique.py`（追加入口级测试）

**Interfaces:**
- Consumes: Task 1 的 `scan_source_names(roots, *, strict=False) -> dict[str, Path]`、`DuplicateSourceNameError`
- Produces:
  - `_source_dirs() -> dict[str, Path]` —— 全局唯一表（内置根在前）
  - `_source_dir(source_name: str) -> tuple[Path, bool] | None` —— `(目录, 是否内置)`，内置判定 = `path.parent == _SOURCES_DIR`
  - `_resolve_private(d: Path, capability: str)` —— 私有源走 `spec_from_file_location` 加载
  - 公开行为变化：`list_sources()` / `get_manifest()` / `capabilities()` / `resolve()` 在撞名时都抛 `DuplicateSourceNameError`
- 删除：`_iter_source_dirs()`（已核实只有本文件内 3 处引用：定义 52、`get_manifest()` 107、`resolve()` 157；无测试或外部模块引用）

- [ ] **Step 1: 先跑既有私有源用例，记录基线**

Run: `python -m pytest tests/test_source_contracts.py tests/test_source_api.py -q`
Expected: 全绿（这是改动前的基线，含即将改写的 `test_builtin_wins_over_private`）

- [ ] **Step 2: 改写既有测试（机制已取消的那条）**

`tests/test_source_contracts.py` 里删掉 `test_builtin_wins_over_private`（123-152 行），替换为：

```python
def test_duplicate_source_name_across_roots_rejected(tmp_path, monkeypatch):
    """跨根同名 → DuplicateSourceNameError（全局唯一，2026-09-27）。

    这里原先是 test_builtin_wins_over_private：私有源复用内置 source_name 时
    「同名能力内置优先」。该机制已被全局唯一取消，机制本身不再存在——
    见 docs/superpowers/specs/2026-09-27-source-name-uniqueness-design.md。
    """
    import novelbase.source as s
    from novelbase.sources.manifest import DuplicateSourceNameError

    d = tmp_path / "92xs_requests_default"   # 与内置目录同名
    d.mkdir()
    (d / "source.json").write_text(json.dumps({
        "source_name": "92xs-requests-default",
        "enabled": True,
        "default_config": {"search": {"mode": "requests"}},
    }, ensure_ascii=False), encoding="utf-8")
    (d / "search.py").write_text(
        "async def search(query, engine, **kwargs):\n    return ('private',)\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", str(tmp_path))

    with pytest.raises(DuplicateSourceNameError):
        s.list_sources()
    with pytest.raises(DuplicateSourceNameError):
        s.resolve("92xs-requests-default", "search")
```

- [ ] **Step 3: 追加入口级测试**

在 `tests/test_source_names_unique.py` 末尾追加（导入行改成
`from novelbase.sources.manifest import (DuplicateSourceNameError, ManifestError, scan_source_names)`）：

```python
def _builtin_root(tmp_path: Path, *names: str) -> Path:
    """造一个「内置根」：每个名字一个目录。"""
    root = tmp_path / "builtin_sources"
    for i, name in enumerate(names):
        _source(root, f"demo_{i}", name)
    return root


def test_list_sources_raises_on_duplicate_builtin(tmp_path, monkeypatch):
    import novelbase.source as s

    monkeypatch.setattr(s, "_SOURCES_DIR",
                        _builtin_root(tmp_path, "demo-requests-default", "demo-requests-default"))
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", None)
    with pytest.raises(DuplicateSourceNameError):
        s.list_sources()


def test_get_manifest_and_capabilities_raise_on_duplicate_builtin(tmp_path, monkeypatch):
    """get_manifest 与 capabilities 都不得把撞名吞成空/第一个。"""
    import novelbase.source as s

    monkeypatch.setattr(s, "_SOURCES_DIR",
                        _builtin_root(tmp_path, "demo-requests-default", "demo-requests-default"))
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", None)
    with pytest.raises(DuplicateSourceNameError):
        s.get_manifest("demo-requests-default")
    with pytest.raises(DuplicateSourceNameError):
        s.capabilities("demo-requests-default")
    with pytest.raises(DuplicateSourceNameError):
        s.resolve("demo-requests-default", "search")


def test_private_dir_same_name_as_builtin_rejected(tmp_path, monkeypatch):
    """全局唯一（真实内置根 + tmp 私有根）：私有源复用内置 source_name → 报错。"""
    import novelbase.source as s

    _source(tmp_path, "92xs_requests_default", "92xs-requests-default")
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", str(tmp_path))
    with pytest.raises(DuplicateSourceNameError):
        s.list_sources()
```

- [ ] **Step 4: 跑测试确认失败**

Run: `python -m pytest tests/test_source_names_unique.py tests/test_source_contracts.py -q`
Expected: FAIL —— 追加的入口级用例全挂（当前 `list_sources()` 用 `set` 静默去重、`get_manifest()` 静默取第一个）；`test_duplicate_source_name_across_roots_rejected` 也挂（当前不抛）

- [ ] **Step 5: 实现 `novelbase/source.py`**

导入块改为：

```python
import os
from importlib import import_module, util as importlib_util
from inspect import signature
from pathlib import Path
from .sources.contracts import CAPABILITY_META
from .sources.manifest import (
    DuplicateSourceNameError, ManifestError, check_capability_files,
    load_manifest, scan_source_names,
)
```

模块 docstring 末尾（`私有源：…` 那段）替换为：

```
`source_name` **全局唯一**：内置根与私有根（`NLD_PRIVATE_SOURCES`）是同一命名空间，
任何两个目录声明同一个 `source_name` 都会在加载期抛 `DuplicateSourceNameError`
（`ManifestError` 的子类，见 `sources/manifest.py::scan_source_names()`）——宁可
整个加载失败，也不静默选一个源继续跑。私有源因此必须自带独立 `source_name`，
不能作为内置源的替代实现。
```

删除 `_iter_source_dirs()`（整个函数 52-74 行），替换为：

```python
def _source_dirs() -> dict[str, Path]:
    """全局唯一书源表 `{source_name: 目录}`（内置根在前，私有根在后）。

    任一 `source_name` 重复（含跨根）→ `DuplicateSourceNameError`。
    """
    roots: list[Path] = []
    if _SOURCES_DIR.is_dir():
        roots.append(_SOURCES_DIR)
    if _PRIVATE_SOURCES_ROOT:
        p = Path(_PRIVATE_SOURCES_ROOT)
        if p.is_dir():
            roots.append(p)
    return scan_source_names(roots)


def _source_dir(source_name: str) -> tuple[Path, bool] | None:
    """`(目录, 是否内置)`；未知 `source_name` 返回 `None`。"""
    path = _source_dirs().get(source_name)
    if path is None:
        return None
    return path, path.parent == _SOURCES_DIR
```

`list_sources()` 替换为：

```python
def list_sources() -> list[str]:
    """列出内置 + 私有书源的 source_name（排序；重名 → DuplicateSourceNameError）。"""
    if _is_compiled():
        return sorted(m["source_name"] for m in _compiled_sources().values())
    return sorted(_source_dirs())
```

`get_manifest()` 替换为：

```python
def get_manifest(source_name: str) -> dict:
    """返回书源的 `source.json` 内容（非编译模式校验能力段 ⇔ .py 文件）。"""
    if _is_compiled():
        dirname = _compiled_dir_by_source().get(source_name)
        if dirname is None or dirname not in _compiled_sources():
            raise KeyError(f"unknown source: {source_name}")
        return _compiled_sources()[dirname]
    entry = _source_dir(source_name)
    if entry is None:
        raise KeyError(f"unknown source: {source_name}")
    d, _ = entry
    manifest = load_manifest(d)
    check_capability_files(d, manifest)  # spec 规则 1：能力段 ⇔ .py 文件双向一致
    return manifest
```

`capabilities()` 替换为：

```python
def capabilities(source_name: str) -> dict[str, str]:
    """返回 `{capability: mode}`；书源不存在或声明非法时返回 `{}`。

    唯一例外：`source_name` 重复（撞名）直接抛——那是环境级错误，不该被静默
    吞成「未声明能力」（否则后端 `GET /config/sources/{name}` 会显示空能力）。
    """
    try:
        manifest = get_manifest(source_name)
    except DuplicateSourceNameError:
        raise
    except (KeyError, ManifestError):
        return {}
    return {cap: section["mode"] for cap, section in manifest.get("default_config", {}).items()}
```

在 `_resolve_import()` 之后新增：

```python
def _resolve_private(d: Path, capability: str):
    """私有源在包外（`NLD_PRIVATE_SOURCES`），必须走 spec_from_file_location（spec:163）。"""
    candidate = d / f"{capability}.py"
    if not candidate.is_file():
        raise ImportError(f"{d} 缺少能力文件 {candidate.name}")
    module_name = f"novelbase_private.sources.{d.name}.{capability}"
    spec = importlib_util.spec_from_file_location(module_name, str(candidate))
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load spec from {candidate}")
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, capability, None)
    if fn is None:
        raise ImportError(f"{candidate} 里没有名为 {capability} 的函数")
    return fn
```

`resolve()` 的加载部分替换为（保留前面的能力/mode 校验与末尾的签名校验）：

```python
    if _is_compiled():
        # 编译模式：能力模块已被 --include-package=novelbase.sources 打进产物，
        # 文件系统里没有 .py 可查，直接按目录名 import
        dirname = _compiled_dir_by_source().get(source_name)
        if dirname is None:
            raise ImportError(f"unknown source: {source_name}")
        fn = _resolve_import(source_name, capability, dirname)
    else:
        entry = _source_dir(source_name)
        if entry is None:
            raise ImportError(f"unknown source: {source_name}")
        d, is_builtin = entry
        # 全局唯一：每个 source_name 至多一个目录 → 无需「内置优先、私有补齐」循环
        fn = (_resolve_import(source_name, capability, d.name) if is_builtin
              else _resolve_private(d, capability))
```

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/test_source_names_unique.py tests/test_source_contracts.py tests/test_source_api.py -q`
Expected: 全绿

- [ ] **Step 7: 全量回归**

Run: `python -m pytest tests -q`
Expected: **全绿**（`tests/test_source_contracts.py::test_private_source_merged` 等私有源用例必须仍通过——不同名私有源依旧合法）

- [ ] **Step 8: 提交**

```bash
git add novelbase/source.py tests/test_source_contracts.py tests/test_source_names_unique.py
git commit -F <(printf 'refactor: source.py 收敛为单一扫描入口并强制 source_name 全局唯一\n')
```

---

### Task 3: `build_manifest.build()` 构建期拦截

**Files:**
- Modify: `novelbase/utils/build_manifest.py`
- Test: `tests/test_build_manifest_unique.py`（新建）

**Interfaces:**
- Consumes: Task 1 的 `scan_source_names(roots, *, strict=False) -> dict[str, Path]`、`DuplicateSourceNameError`
- Produces: `build()` 在撞名时 `raise SystemExit(1)`（消息含「重复」），且**不写出** `OUT`；正常路径行为不变（生成的 `_manifest.py` 形状与现在一致）
- 调用方（不改动）：`scripts/build-nuitka.sh:72`、`scripts/build-nuitka.ps1:42` 的 `python -m novelbase.utils.build_manifest`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_build_manifest_unique.py`：

```python
"""构建期拦截：sources/ 下 source_name 撞名时 build_manifest 必须中止（非零退出）。"""
import json
from pathlib import Path

import pytest

from novelbase.utils import build_manifest as bm


def _source(root: Path, dirname: str, source_name: str) -> Path:
    d = root / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "source.json").write_text(json.dumps({
        "source_name": source_name,
        "enabled": True,
        "default_config": {"search": {"mode": "requests"}},
    }, ensure_ascii=False), encoding="utf-8")
    (d / "search.py").write_text(
        "async def search(query, engine, **kwargs):\n    return ()\n", encoding="utf-8")
    return d


def test_build_aborts_on_duplicate(tmp_path, monkeypatch):
    src = tmp_path / "sources"
    _source(src, "demo_a", "demo-requests-default")
    _source(src, "demo_b", "demo-requests-default")
    out = tmp_path / "_manifest.py"
    monkeypatch.setattr(bm, "SRC", src)
    monkeypatch.setattr(bm, "OUT", out)

    with pytest.raises(SystemExit) as ei:
        bm.build()

    assert "重复" in str(ei.value)
    assert not out.exists(), "撞名时不得写出 half-baked 的 _manifest.py"


def test_build_generates_when_unique(tmp_path, monkeypatch):
    src = tmp_path / "sources"
    _source(src, "demo_a", "demo-requests-default")
    out = tmp_path / "_manifest.py"
    monkeypatch.setattr(bm, "SRC", src)
    monkeypatch.setattr(bm, "OUT", out)

    bm.build()

    text = out.read_text(encoding="utf-8")
    assert "'demo-requests-default': 'demo_a'" in text
    assert "SOURCES: dict[str, dict] = {" in text
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_build_manifest_unique.py -q`
Expected: `test_build_aborts_on_duplicate` FAIL（当前撞名会静默覆盖 `SOURCE_DIRS` 并正常写出文件）

- [ ] **Step 3: 实现**

`novelbase/utils/build_manifest.py` 的导入改为（删掉 `import os`，改用扫描函数）：

```python
from pathlib import Path

from ..sources.manifest import ManifestError, load_manifest, scan_source_names
```

`build()` 里替换现在的遍历循环：

```python
    sources: dict[str, dict] = {}
    source_dirs: dict[str, str] = {}
    for entry in sorted(os.listdir(SRC)):
        if entry.startswith("_") or entry == "__pycache__":
            continue
        d = SRC / entry
        if not d.is_dir() or not (d / "source.json").is_file():
            continue
        manifest = load_manifest(d)
        sources[entry] = manifest
        source_dirs[manifest["source_name"]] = entry
```

为：

```python
    try:
        # 撞名 → DuplicateSourceNameError；strict=True 让坏 manifest 也直接中止
        # （编译模式的 SOURCE_DIRS 撞名会静默覆盖，且编译分支 list_sources()
        # 不去重、会把同一个名字返回两次——必须在构建期拦住）
        by_name = scan_source_names([SRC], strict=True)
    except ManifestError as e:
        raise SystemExit(f"ERROR: source_name 重复，构建中止：{e}")

    sources: dict[str, dict] = {}
    source_dirs: dict[str, str] = {}
    for source_name, path in sorted(by_name.items()):
        sources[path.name] = load_manifest(path)
        source_dirs[source_name] = path.name
```

同时把模块 docstring 第 2 段补一句（紧跟在 `onefile 产物无法扫描文件系统…` 之后）：

```
`sources/` 下 `source_name` 撞名时直接非零退出（编译模式的 `SOURCE_DIRS` 会静默
覆盖、`list_sources()` 会返回重复条目）。
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_build_manifest_unique.py -q`
Expected: `2 passed`

- [ ] **Step 5: 真实构建路径冒烟**

Run: `python -m novelbase.utils.build_manifest`
Expected: `Generated ...\_manifest.py (10 sources)`；随后 `git status --short` 不得出现 `novelbase/utils/_manifest.py`（该文件是生成物、未入库）

- [ ] **Step 6: 全量回归**

Run: `python -m pytest tests -q`
Expected: 全绿

- [ ] **Step 7: 提交**

```bash
git add novelbase/utils/build_manifest.py tests/test_build_manifest_unique.py
git commit -F <(printf 'feat: build_manifest 撞名即中止（编译模式 SOURCE_DIRS 静默覆盖）\n')
```

---

### Task 4: 文档同步（6 处口径）

**Files:**
- Modify: `docs/project/sources.md`（书源结构节 22-25 附近、私有源隔离节 141-158）
- Modify: `docs/session-prompt.md:51`、`docs/session-prompt.md:56`
- Modify: `AGENTS.md:34-37`

**Interfaces:**
- Consumes: Task 1-3 的实现（函数名 `scan_source_names`、异常名 `DuplicateSourceNameError`）
- Produces: 文档与实现一致；无代码影响

- [ ] **Step 1: `docs/project/sources.md` 书源结构节**

在「**`source_name`**：`source.json` 里的唯一 id（连字符）……两者解耦。」这一条之后、「**不设 `_common.py`**」之前插入：

```
- **`source_name` 全局唯一**（2026-09-27）：内置根与私有根（`NLD_PRIVATE_SOURCES`）
  是**同一命名空间**，任何两个目录声明同一个 `source_name` 都会在加载期抛
  `DuplicateSourceNameError`（`ManifestError` 子类），检测点唯一：
  `novelbase/sources/manifest.py::scan_source_names()`。私有源必须自带独立
  `source_name`，**不能**作为内置源的替代实现（「同名能力内置优先、内置缺失再用
  私有补齐」的旧机制已取消）。
```

- [ ] **Step 2: `docs/project/sources.md` 私有源隔离节（141-145 行）**

把：

```
环境变量 `NLD_PRIVATE_SOURCES` 指向外部目录，镜像 `sources/{dir}/` 结构。
`list_sources()` / `capabilities()` 合并内置与私有书源；`resolve()` 中**同名能力内置优先**，
内置缺失再用私有补齐（私有目录在包外，走 `importlib.util.spec_from_file_location` 加载）。
```

改为：

```
环境变量 `NLD_PRIVATE_SOURCES` 指向外部目录，镜像 `sources/{dir}/` 结构。
`list_sources()` / `capabilities()` 合并内置与私有书源（私有目录在包外，走
`importlib.util.spec_from_file_location` 加载）。
**私有源须自带独立 `source_name`**：内置根与私有根是同一命名空间，任何重名（含私有源
复用内置 id）都会在加载期抛 `DuplicateSourceNameError`——原「同名能力内置优先、
内置缺失再用私有补齐」的机制已于 **2026-09-27 取消**。已有复用内置 id 的私有目录，
升级后需改其 `source.json` 的 `source_name`（目录名可不变）并同步
`app_data/config/sites/{新名}.yaml`。
```

- [ ] **Step 3: `docs/session-prompt.md:51`**

把行尾的：

```
与内置书源合并，**同名能力内置优先**。公开仓库不包含敏感实现
```

改为：

```
与内置书源合并；**`source_name` 全局唯一**（2026-09-27 收紧）——内置根与私有根同一命名空间，任何重名（含私有源复用内置 id）加载期抛 `DuplicateSourceNameError`，原「同名能力内置优先」机制已取消，私有源须自带独立 `source_name`。公开仓库不包含敏感实现
```

（在该行行首的 `（2026-08-05，2026-09-25 适配新结构）` 里补成 `（2026-08-05，2026-09-25 适配新结构，2026-09-27 收紧为全局唯一）`。）

- [ ] **Step 4: `docs/session-prompt.md:56` 删掉已补齐的已知限制**

把该行末尾的：

```
；重复 `source_name` 无实现层检测（`novel.extra["platform"]` 已于 2026-09-25 剥离）
```

改为：

```
（`source_name` 全局唯一已有实现层检测，2026-09-27）
```

结果该行以「**仍缺**（后续增强，非缺陷）：前端 URL **自动**匹配书源（core 无 `platform_from_url`，`source` 由用户手选）（`source_name` 全局唯一已有实现层检测，2026-09-27）」结束。

- [ ] **Step 5: `AGENTS.md` 书源契约条目**

在 `- **书源契约** …` 条目的「`source_name`（source.json 里）与目录名解耦；目录名是合法 Python 标识符，能力通过 `import_module("novelbase.sources.{dir}.{capability}")` 加载。」之后插入一行：

```
  `source_name` **全局唯一**（内置根 + 私有根同一命名空间）：撞名在加载期抛 `DuplicateSourceNameError`（`ManifestError` 子类），检测点 `novelbase/sources/manifest.py::scan_source_names()`；私有源须自带独立 `source_name`。
```

- [ ] **Step 6: 校验术语与实现一致**

Run: `grep -rn "同名能力内置优先\|内置缺失再用私有补齐\|内置优先" docs/project/sources.md docs/session-prompt.md AGENTS.md`
Expected: 只剩 Task 4 新写入的「原……机制已取消」这类**引用旧机制**的句子；不得再有把旧机制当现状陈述的句子

- [ ] **Step 7: 提交**

```bash
git add docs/project/sources.md docs/session-prompt.md AGENTS.md
git commit -F <(printf 'docs: 私有源隔离改为 source_name 全局唯一口径\n')
```

---

## Self-Review

**1. Spec coverage（逐节对照）**

| Spec 节 | 落实在 |
|---------|--------|
| §1 命名空间规则（严格全局唯一，不留逃生舱） | Task 1 `scan_source_names()` 跨根检测；Task 2 `test_private_dir_same_name_as_builtin_rejected` |
| §2 `manifest.scan_source_names()`（含 `strict` 双语义、消息格式） | Task 1 Step 3 完整代码 + Step 1 的 7 条单测 |
| §3 `source.py` 收敛（删 `_iter_source_dirs`、`list_sources`/`get_manifest`/`resolve`、不加缓存） | Task 2 Step 5（含 `_source_dirs()`/`_source_dir()`/`_resolve_private()`） |
| §4 `build_manifest` 构建期拦截 + `SystemExit(1)` | Task 3 Step 3 + Step 1 的两条测试 |
| §5 新增测试 + 既有测试处置 | Task 1 Step 1、Task 2 Step 2/3、Task 3 Step 1 |
| §6 已知边界（不改容错分工、不加缓存） | Global Constraints；Task 1 `strict` 双语义测试 |
| §7 文档同步 6 处 | Task 4 Step 1-5 |
| §8 不做（逃生舱/缓存等） | Global Constraints「不做」 |

**spec 之外的收口细化（本计划新增，已标注）**：spec 只写了「抛 `ManifestError`」，但 `capabilities()` 现有 `except (KeyError, ManifestError): return {}` 会把撞名**静默吞成空能力**（后端 `GET /api/v2/config/sources/{name}` 会显示「无能力」）。故 Task 1 引入 `DuplicateSourceNameError(ManifestError)` 子类，Task 2 让 `capabilities()` 对它 `raise` 而非 `return {}`。对外仍满足「抛 `ManifestError`」（子类），是 spec 意图（fail-fast、不许静默）的落实。

**2. Placeholder scan**：无 TBD/TODO；每个代码步骤都有完整可粘贴代码；测试步骤都有期望输出。

**3. Type consistency 核对**

- `scan_source_names(roots: Iterable[Path], *, strict: bool = False) -> dict[str, Path]` —— Task 1 定义，Task 2（`_source_dirs()`）、Task 3（`[SRC]`, `strict=True`）调用，签名一致。
- `DuplicateSourceNameError(ManifestError)` —— Task 1 定义，Task 2（`capabilities()` 的 `except`、两处测试）、Task 3（`except ManifestError` 捕获到它）使用，父子关系一致。
- `_source_dir()` 返回 `tuple[Path, bool] | None` —— Task 2 内部三处使用（`get_manifest()`、`resolve()`、`test_*`），解包形状一致。
- `_resolve_private(d: Path, capability: str)` —— Task 2 定义与调用一致。
- 测试助手 `_source(root, dirname, source_name)` 在 Task 1 定义；Task 2 复用同文件内的它；Task 3 在新文件里**重新定义**（不跨文件导入私有助手）。

## Execution Handoff

已确认：**Subagent-Driven**（用户 2026-09-27 指示「使用 subagent」）。

- REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`
- 依赖图：Task 1 → (Task 2 ∥ Task 3) → Task 4；每个 task 一个全新 subagent，写路径互不重叠（Task 2 与 Task 3 已用不同测试文件隔开）
- 每个 subagent 收到**只含自己那节**的 brief（`### Task N` 起、到下一个 `###` 前），加上本文档的 header 与 Global Constraints
- 每个 task 完成后：跑该 task 的验证命令 → 核对期望输出 → 再进入下一个 task；Task 2/3 完成后跑一次 `python -m pytest tests -q` 全量确认
- 全部完成后：跑 `python -m pytest tests -q` 与 `npx tsc -b`（`frontend/`）作为收尾验证；**不推送**，等用户确认后再 `git push origin dev`
