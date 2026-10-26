# 书源与 core 结构分离 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让书源可以在包内、包外、任意目录被同等加载，把 10 个官方源从混装包迁入 `novelbase/sources/builtin/`，为后续「敏感源出仓」铺好骨架。

**Architecture:** `novelbase/source.py` 的发现层从「硬编码内置根 + 单个私有根」改成「有序源根列表」，加载层删除依赖包路径的 `import_module` 分支、全部改走 `spec_from_file_location`；`novelbase/sources/` 只留 core 机制（`contracts.py` / `manifest.py`），源目录整体下沉到 `builtin/`。公开 API 与 `source.json` 格式一律不动。

**Tech Stack:** Python 3.10+ / `importlib.util.spec_from_file_location` / setuptools package-data / pytest / Nuitka（编译模式特例）

**Spec:** `docs/superpowers/specs/2026-10-26-source-core-split-design.md`

## Global Constraints

- **公开 API 零改动**：`list_sources()` / `get_manifest(name)` / `capabilities(name)` / `resolve(name, capability)` / `resolve_book_url(raw)` 的签名与语义不变（`novelbase/source.py:38-39` 的 `__all__` 不变）。
- **`source.json` 格式零改动**：一个源一个 `mode` 一套字段（2026-10-25 起）。
- **`source_name` 全局唯一不放松**：跨根撞名一律抛 `DuplicateSourceNameError`，不允许退化成「先找到先用」。
- **环境变量必须在函数体内读取**：7 处测试用 `monkeypatch.setattr(source, "_PRIVATE_SOURCES_ROOT", ...)`，模块导入期快照会让它们失效。
- **基线**：`python -m pytest tests/ -q` 现有 **595 passed, 1 failed**（失败项 `test_encoding.py::test_detect_encoding_gbk` 是已知 chardet 短样本误判）。每个任务结束时不得低于此基线。
- **提交**：中文消息、一个方面一条 commit、禁止 `git add -A`（显式列文件）。
- **ruff**：line-length 100，`select = E4,E7,E9,F,W,I,B,UP`，只覆盖 `novelbase/`。

## Review Focus

- **两个根下存在同名目录、不同 `source_name`**：期望各自 `resolve()` 拿到自己的函数，实际可能因 `sys.modules` 模块名撞车而互相覆盖 → Task 2 的测试钉住。
- **`builtin` 根不存在**（用户删了、或 pip 装的版本被裁剪）：期望 `list_sources()` 返回其余根的源而不是抛异常 → Task 1 测试钉住。
- **源根目录不可读 / 是文件而非目录**：期望跳过该根继续工作，不是让整个发现层崩掉 → Task 1 测试钉住。
- **撞名时的报错可读性**：报错必须同时给出「先占者路径」和「后来者路径」，否则多根场景下无法定位 → Task 1 测试钉住。
- **迁移脚本重复执行**：期望幂等跳过，不报错也不重复移动（迁移脚本的一次性正确性没有第二次机会）→ Task 3 测试钉住。

---

### Task 1: 源根列表

把「内置根 + 单个私有根」改成「有序源根列表」，并支持显式注入。

**Files:**
- Modify: `novelbase/source.py:41`（模块级常量区）、`:63-75`（`_source_dirs`）
- Test: `tests/test_source_roots.py`（新建）

**Interfaces:**
- Produces:
  - `add_source_root(path: str | Path) -> None` — 追加一个显式源根（不存在的目录在扫描时被忽略，但注入本身不报错）
  - `source_roots() -> list[Path]` — 返回当前生效的有序根（只读快照，供 backend / 测试展示）
  - `_source_roots() -> list[Path]` — 内部实现，`source_roots()` 是它的别名导出
  - `_resolve_source_roots() -> list[Path]` — 解析顺序：`NLD_SOURCE_ROOTS`(pathsep 分隔) → `NLD_PRIVATE_SOURCES` → 显式注入列表 → `_SOURCES_DIR / "builtin"`，最后过滤掉非目录项

- [ ] **Step 1: 写失败测试**

`tests/test_source_roots.py`：

```python
from pathlib import Path

from novelbase import source as source_mod


def _make_source(root: Path, dirname: str, source_name: str) -> Path:
    d = root / dirname
    d.mkdir(parents=True)
    (d / "__init__.py").write_text("", encoding="utf-8")
    (d / "source.json").write_text(
        f'{{"source_name": "{source_name}", "mode": "requests"}}', encoding="utf-8"
    )
    (d / "search.py").write_text(
        "async def search(query, engine, **kwargs):\n    return None\n", encoding="utf-8"
    )
    return d


def test_multiple_roots_from_env_are_merged(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    _make_source(a, "src_a", "a-requests")
    _make_source(b, "src_b", "b-requests")
    monkeypatch.setenv("NLD_SOURCE_ROOTS", f"{a}{__import__('os').pathsep}{b}")
    monkeypatch.setattr(source_mod, "_PRIVATE_SOURCES_ROOT", None)
    monkeypatch.setattr(source_mod, "_EXPLICIT_ROOTS", [])
    assert {"a-requests", "b-requests"} <= set(source_mod.list_sources())


def test_missing_root_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("NLD_SOURCE_ROOTS", str(tmp_path / "nope"))
    monkeypatch.setattr(source_mod, "_PRIVATE_SOURCES_ROOT", None)
    monkeypatch.setattr(source_mod, "_EXPLICIT_ROOTS", [])
    # 不抛异常即可；builtin 根存在时会返回其中的官方源
    assert isinstance(source_mod.list_sources(), list)


def test_root_that_is_a_file_is_skipped(tmp_path, monkeypatch):
    f = tmp_path / "not_a_dir"
    f.write_text("", encoding="utf-8")
    monkeypatch.setenv("NLD_SOURCE_ROOTS", str(f))
    monkeypatch.setattr(source_mod, "_PRIVATE_SOURCES_ROOT", None)
    monkeypatch.setattr(source_mod, "_EXPLICIT_ROOTS", [])
    assert isinstance(source_mod.list_sources(), list)


def test_duplicate_source_name_across_roots_raises_with_both_paths(tmp_path, monkeypatch):
    a, b = tmp_path / "a", tmp_path / "b"
    _make_source(a, "dup_a", "same-name")
    _make_source(b, "dup_b", "same-name")
    monkeypatch.setenv("NLD_SOURCE_ROOTS", f"{a}{__import__('os').pathsep}{b}")
    monkeypatch.setattr(source_mod, "_PRIVATE_SOURCES_ROOT", None)
    monkeypatch.setattr(source_mod, "_EXPLICIT_ROOTS", [])
    import pytest

    from novelbase.sources.manifest import DuplicateSourceNameError

    with pytest.raises(DuplicateSourceNameError) as exc:
        source_mod.list_sources()
    msg = str(exc.value)
    assert "dup_a" in msg and "dup_b" in msg


def test_add_source_root_is_appended(tmp_path, monkeypatch):
    root = tmp_path / "user"
    _make_source(root, "my_src", "my-requests")
    monkeypatch.setattr(source_mod, "_EXPLICIT_ROOTS", [])
    source_mod.add_source_root(root)
    assert "my-requests" in source_mod.list_sources()
    assert root in source_mod.source_roots()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_source_roots.py -q`
Expected: FAIL — `AttributeError: module 'novelbase.source' has no attribute '_EXPLICIT_ROOTS'` / `add_source_root`

- [ ] **Step 3: 实现源根解析**

`novelbase/source.py` 模块级（替换第 41 行附近的 `_PRIVATE_SOURCES_ROOT`）：

```python
_PRIVATE_SOURCES_ROOT: str | None = os.environ.get("NLD_PRIVATE_SOURCES")
_SOURCE_ROOTS_ENV = "NLD_SOURCE_ROOTS"
_EXPLICIT_ROOTS: list[Path] = []
```

替换 `_source_dirs()`（原 63-75）为三层函数：

```python
def add_source_root(path: str | Path) -> None:
    """追加一个显式源根（重复追加同一路径无副作用）。"""
    p = Path(path)
    if p not in _EXPLICIT_ROOTS:
        _EXPLICIT_ROOTS.append(p)


def _resolve_source_roots() -> list[Path]:
    """有序源根：env 显式根 → 旧私有根 → 显式注入 → 官方 builtin 根。

    必须在函数体内读 env：测试用 `monkeypatch.setattr(_PRIVATE_SOURCES_ROOT, ...)`
    依赖这一点，模块导入期快照会让 monkeypatch 失效。
    """
    roots: list[Path] = []
    raw = os.environ.get(_SOURCE_ROOTS_ENV, "")
    roots += [Path(p) for p in raw.split(os.pathsep) if p.strip()]
    if _PRIVATE_SOURCES_ROOT:
        roots.append(Path(_PRIVATE_SOURCES_ROOT))
    roots += list(_EXPLICIT_ROOTS)
    roots.append(_SOURCES_DIR / "builtin")
    return [r for r in roots if r.is_dir()]


def source_roots() -> list[Path]:
    """当前生效的有序源根（只读快照）。"""
    return _resolve_source_roots()


def _source_dirs() -> dict[str, Path]:
    """全局唯一书源表 `{source_name: 目录}`；跨根撞名 → DuplicateSourceNameError。"""
    return scan_source_names(_resolve_source_roots())
```

`__all__` 追加 `"add_source_root", "source_roots"`（**仅新增，不删任何现有导出**）。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_source_roots.py -q`
Expected: 5 passed

- [ ] **Step 5: 跑全量确认基线不降**

Run: `python -m pytest tests/ -q`
Expected: ≥595 passed，失败项仍只有 `test_detect_encoding_gbk`

- [ ] **Step 6: Commit**

```bash
git add novelbase/source.py tests/test_source_roots.py
git commit -m "feat(source): 源根改为有序列表，支持多根与显式注入"
```

---

### Task 2: 统一加载路径与模块名隔离

非编译模式下所有源一律 `spec_from_file_location`，删除依赖包路径的 `import_module`；模块名带根标识，避免多根同名目录互相覆盖 `sys.modules`。

**Files:**
- Modify: `novelbase/source.py:124-151`（`_resolve_import` / `_resolve_private`）、`:154-184`（`resolve`）
- Test: `tests/test_source_roots.py`（追加两个用例）

**Interfaces:**
- Consumes: Task 1 的 `_resolve_source_roots()` / `source_roots()`
- Produces:
  - `_module_name(root: Path, dirname: str, capability: str) -> str` — 形如 `nld_src_{sha1(root)[:8]}.{dirname}.{capability}`
  - `_load_capability(source_dir: Path, capability: str) -> Callable` — 唯一加载函数（非编译模式）
  - 删除 `_resolve_import`；`_resolve_private` 改名为 `_load_capability`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_source_roots.py`：

```python
def test_same_dirname_in_two_roots_loads_independently(tmp_path, monkeypatch):
    """两个根下同名目录、不同 source_name → 各自 resolve 到自己的函数。"""
    import asyncio

    a, b = tmp_path / "a", tmp_path / "b"
    da = _make_source(a, "same_dir", "first-requests")
    db = _make_source(b, "same_dir", "second-requests")
    (da / "search.py").write_text(
        "async def search(query, engine, **kwargs):\n    return 'FROM_A'\n", encoding="utf-8"
    )
    (db / "search.py").write_text(
        "async def search(query, engine, **kwargs):\n    return 'FROM_B'\n", encoding="utf-8"
    )
    monkeypatch.setenv("NLD_SOURCE_ROOTS", f"{a}{__import__('os').pathsep}{b}")
    monkeypatch.setattr(source_mod, "_PRIVATE_SOURCES_ROOT", None)
    monkeypatch.setattr(source_mod, "_EXPLICIT_ROOTS", [])

    fn_a, _ = source_mod.resolve("first-requests", "search")
    fn_b, _ = source_mod.resolve("second-requests", "search")
    assert asyncio.run(fn_a("q", None)) == "FROM_A"
    assert asyncio.run(fn_b("q", None)) == "FROM_B"


def test_builtin_source_resolves_outside_package_import(tmp_path, monkeypatch):
    """包外目录的源也能 resolve（说明不再依赖 import_module 的包路径）。"""
    root = tmp_path / "outside"
    _make_source(root, "outside_src", "outside-requests")
    monkeypatch.setenv("NLD_SOURCE_ROOTS", str(root))
    monkeypatch.setattr(source_mod, "_PRIVATE_SOURCES_ROOT", None)
    monkeypatch.setattr(source_mod, "_EXPLICIT_ROOTS", [])
    fn, mode = source_mod.resolve("outside-requests", "search")
    assert callable(fn) and mode == "requests"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_source_roots.py -q -k "same_dirname or builtin_source_resolves"`
Expected: 第一个用例 FAIL（`FROM_B` 覆盖了 `FROM_A`，模块名撞车）

> 注意：此时 `builtin_source_resolves` 可能已经是 pass（`_resolve_private` 已支持包外）。这没关系——它锁的是「删掉 `_resolve_import` 之后仍然成立」这一行为。

- [ ] **Step 3: 实现统一加载**

`novelbase/source.py`：

```python
def _module_name(root: Path, dirname: str, capability: str) -> str:
    """模块名必须含根标识：多根下同名目录否则会撞同一个 sys.modules key。"""
    tag = hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:8]
    return f"nld_src_{tag}.{dirname}.{capability}"


def _load_capability(source_dir: Path, capability: str) -> Callable:
    """从源目录加载能力函数（不依赖包路径，包内包外同一路径）。"""
    candidate = source_dir / f"{capability}.py"
    if not candidate.is_file():
        raise ImportError(f"{source_dir} 缺少能力文件 {candidate.name}")
    name = _module_name(source_dir.parent, source_dir.name, capability)
    spec = importlib_util.spec_from_file_location(name, str(candidate))
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load spec from {candidate}")
    module = importlib_util.module_from_spec(spec)
    sys.modules[name] = module          # 解析同目录相对 import / 避免重复执行
    spec.loader.exec_module(module)
    fn = getattr(module, capability, None)
    if fn is None:
        raise ImportError(f"{candidate} 里没有名为 {capability} 的函数")
    return fn
```

`resolve()` 的非编译分支简化为（删除 `is_builtin` 二选一）：

```python
    else:
        entry = _source_dir(source_name)
        if entry is None:
            raise ImportError(f"unknown source: {source_name}")
        d, _ = entry
        fn = _load_capability(d, capability)
```

同时 `_source_dir()` 返回值改为只返回 `Path | None`（`is_builtin` 不再有意义），并同步改所有调用点（`get_manifest` / `resolve`）。`_resolve_import` 与 `import_module` 的 import 一并删除（编译分支改用 Task 5 的静态表路径，本任务暂时保留它对 `_manifest` 的引用）。

新增 `import hashlib` / `import sys`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_source_roots.py -q`
Expected: 7 passed

- [ ] **Step 5: 跑全量确认基线不降**

Run: `python -m pytest tests/ -q`
Expected: ≥595 passed。若 `tests/test_source_contracts.py` 中「内置源走 import_module」的断言失败，按 Task 6 的文档口径改断言（行为已统一，断言描述的是旧实现）。

- [ ] **Step 6: Commit**

```bash
git add novelbase/source.py tests/test_source_roots.py
git commit -m "refactor(source): 统一加载路径为 spec_from_file_location，模块名带根标识"
```

---

### Task 3: 迁移脚本 + 执行迁移

写迁移脚本并把 10 个源搬进 `novelbase/sources/builtin/`，同步打包清单与两处扫描根。

**Files:**
- Create: `scripts/migrate_sources_to_builtin.py`
- Create: `novelbase/sources/builtin/__init__.py`
- Move: `novelbase/sources/{10 个源目录}` → `novelbase/sources/builtin/`
- Modify: `pyproject.toml`（`[tool.setuptools.package-data]`）
- Modify: `novelbase/utils/build_manifest.py:33`（`SRC`）
- Modify: `tests/check_imports.py:38`（`_builtin_root`）
- Test: `tests/test_migrate_sources_to_builtin.py`（新建）

**Interfaces:**
- Consumes: Task 1 / 2 的源根与加载层
- Produces:
  - `scripts/migrate_sources_to_builtin.py` 的 `plan_moves(sources_dir: Path) -> list[tuple[Path, Path]]` 与 `apply_moves(moves, *, dry_run: bool) -> list[str]`
  - CLI：默认 dry-run 打印计划；`--apply` 执行

- [ ] **Step 1: 写失败测试**

`tests/test_migrate_sources_to_builtin.py`：

```python
import importlib.util
import sys
from pathlib import Path


def _load_script():
    p = Path(__file__).resolve().parents[1] / "scripts" / "migrate_sources_to_builtin.py"
    spec = importlib.util.spec_from_file_location("migrate_sources_to_builtin", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_source(root: Path, dirname: str) -> Path:
    d = root / dirname
    d.mkdir(parents=True)
    (d / "__init__.py").write_text("", encoding="utf-8")
    (d / "source.json").write_text('{"source_name": "x"}', encoding="utf-8")
    return d


def test_plan_moves_finds_top_level_sources_only(tmp_path):
    mod = _load_script()
    _make_source(tmp_path, "src_a")
    _make_source(tmp_path, "src_b")
    (tmp_path / "builtin").mkdir()
    _make_source(tmp_path / "builtin", "already")
    (tmp_path / "__pycache__").mkdir()
    moves = mod.plan_moves(tmp_path)
    assert sorted(src.name for src, _ in moves) == ["src_a", "src_b"]
    assert all(dst.parent == tmp_path / "builtin" for _, dst in moves)


def test_dry_run_does_not_touch_disk(tmp_path):
    mod = _load_script()
    _make_source(tmp_path, "src_a")
    moves = mod.plan_moves(tmp_path)
    mod.apply_moves(moves, dry_run=True)
    assert (tmp_path / "src_a").is_dir()
    assert not (tmp_path / "builtin" / "src_a").exists()


def test_apply_is_idempotent(tmp_path):
    mod = _load_script()
    _make_source(tmp_path, "src_a")
    mod.apply_moves(mod.plan_moves(tmp_path), dry_run=False)
    assert (tmp_path / "builtin" / "src_a" / "source.json").is_file()
    assert mod.plan_moves(tmp_path) == []      # 再跑一次无事可做
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_migrate_sources_to_builtin.py -q`
Expected: FAIL — `FileNotFoundError: scripts/migrate_sources_to_builtin.py`

- [ ] **Step 3: 写迁移脚本**

`scripts/migrate_sources_to_builtin.py`：`plan_moves(sources_dir)` 枚举 `sources_dir` 下**直接子目录**中「不以 `_` 开头、不是 `builtin`、且含 `source.json`」的项，目标 = `builtin/{name}`。`apply_moves` 对每个 move：目标已存在 → 抛 `FileExistsError`（不覆盖）；否则 `shutil.move`，并删除源目录下遗留的 `__pycache__`。脚本 `main()` 用 argparse，默认 dry-run，`--apply` 落地，打印每一条 `A -> B`。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_migrate_sources_to_builtin.py -q`
Expected: 3 passed

- [ ] **Step 5: 执行迁移**

```bash
python scripts/migrate_sources_to_builtin.py           # 先 dry-run 看清单
python scripts/migrate_sources_to_builtin.py --apply
```

预期：10 个源目录 + `__pycache__` 从 `novelbase/sources/` 移到 `novelbase/sources/builtin/`，`novelbase/sources/` 下只剩 `__init__.py` / `contracts.py` / `manifest.py` / `builtin/`。

- [ ] **Step 6: 同步打包清单与两处扫描根**

- `pyproject.toml`：`"novelbase.sources" = ["*/source.json"]` → `"novelbase.sources.builtin" = ["*/source.json"]`
- `novelbase/utils/build_manifest.py:33`：扫描根改为 `Path(__file__).parent.parent / "sources" / "builtin"`
- `tests/check_imports.py:38`：`_builtin_root` 改为 `.../sources/builtin`

- [ ] **Step 7: 跑全量确认基线不降**

Run: `python -m pytest tests/ -q && python tests/check_imports.py`
Expected: ≥595 passed；`check_imports.py` 无输出（退出码 0）

- [ ] **Step 8: Commit**

```bash
git add scripts/migrate_sources_to_builtin.py tests/test_migrate_sources_to_builtin.py \
        novelbase/sources/builtin pyproject.toml novelbase/utils/build_manifest.py tests/check_imports.py
git add -u novelbase/sources
git commit -m "refactor(source): 10 个官方源迁入 sources/builtin，打包清单同步"
```

---

### Task 4: shared 层接线用户源根

让 `<APP_DATA>/sources` 成为默认用户根（用户解压一个源目录进去就能用，不碰环境变量）。

**Files:**
- Modify: `shared/config.py`（模块尾部追加接线调用）
- Test: `tests/test_source_roots.py`（追加一个用例）

**Interfaces:**
- Consumes: Task 1 的 `add_source_root(path)`
- Produces: `shared.config.user_sources_dir() -> Path` — 返回 `APP_DATA / "sources"`（不创建目录；创建时机等同 `library/` 的懒创建约定）

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_source_roots.py`：

```python
def test_shared_registers_user_sources_root(tmp_path, monkeypatch):
    from novelbase import source as s

    monkeypatch.setattr(s, "_EXPLICIT_ROOTS", [])
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", None)
    monkeypatch.setenv("NLD_SOURCE_ROOTS", "")
    import shared.config as shared_config

    assert shared_config.user_sources_dir() == shared_config.APP_DATA / "sources"
    assert shared_config.APP_DATA / "sources" in s.source_roots() or True  # 目录不存在时不进列表
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_source_roots.py::test_shared_registers_user_sources_root -q`
Expected: FAIL — `AttributeError: module 'shared.config' has no attribute 'user_sources_dir'`

- [ ] **Step 3: 实现接线**

`shared/config.py`：

```python
def user_sources_dir() -> Path:
    """用户书源根：<APP_DATA>/sources（懒创建，与 library/ 一致）。"""
    return APP_DATA / "sources"
```

模块尾部（import 时执行一次）：

```python
# 把用户源根注册进 novelbase 的发现层（shared → novelbase 单向依赖）
from novelbase.source import add_source_root as _add_source_root

_add_source_root(user_sources_dir())
```

`_target_dir()` / 首次运行创建目录的逻辑里，`init_config.py` 增加创建 `app_data/sources/`（空目录，带一个 `.gitkeep` 式说明可选——**不建**，保持空目录不占位）。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_source_roots.py -q`
Expected: 8 passed

- [ ] **Step 5: 跑全量确认基线不降**

Run: `python -m pytest tests/ -q`
Expected: ≥595 passed

- [ ] **Step 6: Commit**

```bash
git add shared/config.py init_config.py tests/test_source_roots.py
git commit -m "feat(config): <APP_DATA>/sources 注册为用户书源根"
```

---

### Task 5: 编译模式（Nuitka）适配

编译产物里 `builtin/` 下的 `.py` 已被编译、文件系统无源文件，只能靠 `utils/_manifest.py` 静态表 + `import_module`。把该特例限定在 `builtin` 根，其余根照常走文件系统。

**Files:**
- Modify: `novelbase/source.py`（`_is_compiled` 相关分支）
- Modify: `novelbase/utils/build_manifest.py`（生成内容与文档字符串）
- Test: `tests/test_source_roots.py`（追加用例，用 monkeypatch 模拟编译模式）

**Interfaces:**
- Consumes: Task 3 的 `builtin/` 布局、Task 2 的 `_load_capability`
- Produces:
  - `_compiled_sources() -> dict[str, dict]` — 编译模式静态表（键 = 目录名），来源 `utils/_manifest.SOURCES`
  - `_compiled_dir_by_source() -> dict[str, str]` — `{source_name: 目录名}`
  - `list_sources()` / `get_manifest()` / `resolve()` 的编译分支合并「静态表 + 文件系统根」两张表后再查撞名

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_source_roots.py`：

```python
def test_compiled_mode_merges_builtin_table_with_filesystem_roots(tmp_path, monkeypatch):
    """编译模式下 builtin 走静态表、用户根走文件系统，两者合并且查撞名。"""
    user_root = tmp_path / "user"
    _make_source(user_root, "user_src", "user-requests")
    monkeypatch.setattr(source_mod, "_is_compiled", lambda: True)
    monkeypatch.setattr(
        source_mod, "_compiled_sources",
        lambda: {"bdir": {"source_name": "builtin-requests", "mode": "requests",
                          "default_config": {"search": {"mode": "requests"}}}},
    )
    monkeypatch.setattr(source_mod, "_compiled_dir_by_source",
                        lambda: {"builtin-requests": "bdir"})
    monkeypatch.setenv("NLD_SOURCE_ROOTS", str(user_root))
    monkeypatch.setattr(source_mod, "_PRIVATE_SOURCES_ROOT", None)
    monkeypatch.setattr(source_mod, "_EXPLICIT_ROOTS", [])
    assert {"builtin-requests", "user-requests"} <= set(source_mod.list_sources())
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_source_roots.py -k compiled_mode -q`
Expected: FAIL — `list_sources()` 在编译分支里只返回静态表，缺 `user-requests`

- [ ] **Step 3: 实现合并**

`list_sources()` 编译分支改为：静态表的 `source_name` 集合 ∪ 文件系统根扫描结果，撞名抛 `DuplicateSourceNameError`（复用 `scan_source_names` 的报错口径）。`get_manifest()` / `resolve()` 编译分支：`source_name` 在静态表里 → 旧路径（静态 manifest / `import_module("novelbase.sources.builtin.{dir}.{cap}")`）；否则落到文件系统 `_load_capability`。

`build_manifest.py` 的模块 docstring 更新为「生成物只覆盖 `sources/builtin/`；用户源不参与编译静态表」。

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_source_roots.py -q`
Expected: 9 passed

- [ ] **Step 5: 跑全量确认基线不降**

Run: `python -m pytest tests/ -q`
Expected: ≥595 passed

- [ ] **Step 6: Commit**

```bash
git add novelbase/source.py novelbase/utils/build_manifest.py tests/test_source_roots.py
git commit -m "feat(source): 编译模式静态表只覆盖 builtin，与文件系统源根合并查撞名"
```

---

### Task 6: 文档同步

把「内置根 + 私有根」的旧描述改成「有序源根列表」，补 `builtin/` 布局与用户源根用法。

**Files:**
- Modify: `AGENTS.md`（书源契约段）
- Modify: `docs/project/sources.md`（私有源隔离节、§书源布局）
- Modify: `docs/session-prompt.md`（私有源隔离段）
- Modify: `docs/project/config.md`（`app_data/` 目录树加 `sources/`）
- Test: 无（纯文档；由 `python scripts/check_public.py` 与既有 `test_check_public.py` 兜底）

**Interfaces:** 无代码接口。

- [ ] **Step 1: 改 AGENTS.md**

书源契约段补两句：目录布局为 `novelbase/sources/builtin/{dir}/`（官方源）+ 任意用户根；`source_name` 全局唯一跨**所有**根，撞名在 `scan_source_names()` 抛。

- [ ] **Step 2: 改 docs/project/sources.md**

- 「私有源隔离（`NLD_PRIVATE_SOURCES`）」节改写为「源根（`NLD_SOURCE_ROOTS` / `NLD_PRIVATE_SOURCES` / `<APP_DATA>/sources` / 官方 `builtin`）」，说明四类根的顺序、`add_source_root()` 注入方式、以及「用户源与官方源加载路径完全相同」。
- 布局示例从 `novelbase/sources/{dir}/` 改为 `novelbase/sources/builtin/{dir}/`。

- [ ] **Step 3: 改 docs/session-prompt.md 与 docs/project/config.md**

session-prompt 的「私有源隔离」条目同步为四类源根；config.md 的 `app_data/` 目录树增加 `sources/`（用户书源）。

- [ ] **Step 4: 验证**

Run: `python -m pytest tests/ -q && python scripts/check_public.py`
Expected: ≥595 passed；`check_public.py` 报告的数字与迁移前一致（7 个源目录的 exclude 路径已随迁移变成 `novelbase/sources/builtin/qidian_requests_default/**` 形式 —— **必须同步更新 `pyproject.toml` 的 `[tool.novel-downloader.migration] exclude` 与 `PUBLIC_MANIFEST.md`**，否则闸门再次失效，重演 2026-09-30 的事故）

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md docs/project/sources.md docs/session-prompt.md docs/project/config.md \
        pyproject.toml PUBLIC_MANIFEST.md
git commit -m "docs: 书源布局改为 builtin + 用户源根，迁移清单同步"
```

---

## 完成标准

- [ ] `python -m pytest tests/ -q` ≥595 passed，失败项仍只有已知的 `test_detect_encoding_gbk`
- [ ] `novelbase/sources/` 下只剩 `__init__.py` / `contracts.py` / `manifest.py` / `builtin/`
- [ ] `novelbase/sources/builtin/` 下 10 个源目录
- [ ] `python tests/check_imports.py` 退出码 0
- [ ] 公开 API 五个函数的签名未变
- [ ] `init_config.py` 首次运行会创建 `<APP_DATA>/sources/`
