"""源根列表：多根合并、显式注入、撞名检测、包外加载。

对应 docs/superpowers/specs/2026-10-26-source-core-split-design.md §4 / §5。
"""

import asyncio
import os
from pathlib import Path

import pytest

from novelbase import source as source_mod
from novelbase.sources.manifest import DuplicateSourceNameError


def _make_source(root: Path, dirname: str, source_name: str) -> Path:
    """在 root/dirname 下造一个最小可用书源（只有 search 能力）。"""
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


def _set_roots(monkeypatch, *roots: Path) -> None:
    """把 env 源根设为 roots，并清掉旧私有根与显式注入，避免受宿主环境影响。"""
    monkeypatch.setenv("NLD_SOURCE_ROOTS", os.pathsep.join(str(r) for r in roots))
    monkeypatch.setattr(source_mod, "_PRIVATE_SOURCES_ROOT", None)
    monkeypatch.setattr(source_mod, "_EXPLICIT_ROOTS", [])


def test_multiple_roots_from_env_are_merged(tmp_path, monkeypatch):
    _make_source(tmp_path / "a", "src_a", "a-requests")
    _make_source(tmp_path / "b", "src_b", "b-requests")
    _set_roots(monkeypatch, tmp_path / "a", tmp_path / "b")
    names = set(source_mod.list_sources())
    assert {"a-requests", "b-requests"} <= names


def test_missing_root_is_skipped(tmp_path, monkeypatch):
    _set_roots(monkeypatch, tmp_path / "nope")
    assert isinstance(source_mod.list_sources(), list)


def test_root_that_is_a_file_is_skipped(tmp_path, monkeypatch):
    f = tmp_path / "not_a_dir"
    f.write_text("", encoding="utf-8")
    _set_roots(monkeypatch, f)
    assert isinstance(source_mod.list_sources(), list)


def test_duplicate_source_name_across_roots_raises_with_both_paths(tmp_path, monkeypatch):
    _make_source(tmp_path / "a", "dup_a", "same-name")
    _make_source(tmp_path / "b", "dup_b", "same-name")
    _set_roots(monkeypatch, tmp_path / "a", tmp_path / "b")
    with pytest.raises(DuplicateSourceNameError) as exc:
        source_mod.list_sources()
    msg = str(exc.value)
    assert "dup_a" in msg and "dup_b" in msg


def test_add_source_root_is_appended(tmp_path, monkeypatch):
    root = tmp_path / "user"
    _make_source(root, "my_src", "my-requests")
    _set_roots(monkeypatch)
    source_mod.add_source_root(root)
    assert "my-requests" in source_mod.list_sources()
    assert root in source_mod.source_roots()


def test_same_dirname_in_two_roots_loads_independently(tmp_path, monkeypatch):
    """两个根下同名目录、不同 source_name → 各自 resolve 到自己的函数（模块名不撞车）。"""
    da = _make_source(tmp_path / "a", "same_dir", "first-requests")
    db = _make_source(tmp_path / "b", "same_dir", "second-requests")
    (da / "search.py").write_text(
        "async def search(query, engine, **kwargs):\n    return 'FROM_A'\n", encoding="utf-8"
    )
    (db / "search.py").write_text(
        "async def search(query, engine, **kwargs):\n    return 'FROM_B'\n", encoding="utf-8"
    )
    _set_roots(monkeypatch, tmp_path / "a", tmp_path / "b")

    fn_a, _ = source_mod.resolve("first-requests", "search")
    fn_b, _ = source_mod.resolve("second-requests", "search")
    assert asyncio.run(fn_a("q", None)) == "FROM_A"
    assert asyncio.run(fn_b("q", None)) == "FROM_B"


def test_source_outside_package_resolves(tmp_path, monkeypatch):
    """包外目录的源也能 resolve（不再依赖 import_module 的包路径）。"""
    _make_source(tmp_path / "outside", "outside_src", "outside-requests")
    _set_roots(monkeypatch, tmp_path / "outside")
    fn, mode = source_mod.resolve("outside-requests", "search")
    assert callable(fn) and mode == "requests"


def test_capability_module_executed_once_per_root(tmp_path, monkeypatch):
    """同一源多次 resolve 不应重复执行能力模块的顶层代码（模块按根标识缓存）。"""
    d = _make_source(tmp_path / "a", "once_src", "once-requests")
    marker = tmp_path / "exec_count.txt"
    (d / "search.py").write_text(
        "from pathlib import Path\n"
        f"_p = Path({str(marker)!r})\n"
        "_p.write_text(str(int(_p.read_text()) + 1) if _p.exists() else '1')\n"
        "async def search(query, engine, **kwargs):\n    return None\n",
        encoding="utf-8",
    )
    _set_roots(monkeypatch, tmp_path / "a")
    source_mod.resolve("once-requests", "search")
    source_mod.resolve("once-requests", "search")
    assert marker.read_text(encoding="utf-8") == "1"


def test_shared_registers_user_sources_root(monkeypatch):
    """shared 层 import 时把 <APP_DATA>/sources 注册为显式源根（novelbase 不认识 app_data）。"""
    import importlib

    monkeypatch.setattr(source_mod, "_EXPLICIT_ROOTS", [])
    import shared.config as shared_config

    importlib.reload(shared_config)
    assert shared_config.user_sources_dir() == shared_config.APP_DATA / "sources"
    assert shared_config.user_sources_dir() in source_mod._EXPLICIT_ROOTS


def test_compiled_mode_merges_static_table_with_filesystem_roots(tmp_path, monkeypatch):
    """编译产物里官方源在静态表、用户源在文件系统 —— 两张表必须合并后一起可见。"""
    _make_source(tmp_path / "user", "user_src", "user-requests")
    _set_roots(monkeypatch, tmp_path / "user")
    monkeypatch.setattr(source_mod, "_is_compiled", lambda: True)
    monkeypatch.setattr(
        source_mod,
        "_compiled_sources",
        lambda: {"bdir": {"source_name": "builtin-requests", "mode": "requests",
                          "default_config": {"search": {"mode": "requests"}}}},
    )
    monkeypatch.setattr(
        source_mod, "_compiled_dir_by_source", lambda: {"builtin-requests": "bdir"}
    )
    assert {"builtin-requests", "user-requests"} <= set(source_mod.list_sources())
    assert source_mod.capabilities("user-requests") == {"search": "requests"}


def test_compiled_mode_detects_duplicate_between_table_and_filesystem(tmp_path, monkeypatch):
    """静态表与文件系统根撞名 → 同样抛 DuplicateSourceNameError（不静默取一个）。"""
    _make_source(tmp_path / "user", "user_src", "clash-requests")
    _set_roots(monkeypatch, tmp_path / "user")
    monkeypatch.setattr(source_mod, "_is_compiled", lambda: True)
    monkeypatch.setattr(
        source_mod,
        "_compiled_sources",
        lambda: {"bdir": {"source_name": "clash-requests", "mode": "requests",
                          "default_config": {"search": {"mode": "requests"}}}},
    )
    monkeypatch.setattr(
        source_mod, "_compiled_dir_by_source", lambda: {"clash-requests": "bdir"}
    )
    with pytest.raises(DuplicateSourceNameError):
        source_mod.list_sources()


def test_scaffold_writes_into_user_sources_root(tmp_path, monkeypatch):
    """`cli dev new-source` 必须写进用户源根，不能写进已不是源根的 novelbase/sources/。"""
    import importlib

    monkeypatch.setenv("NLD_APP_DATA", str(tmp_path))
    import shared.config as shared_config

    importlib.reload(shared_config)
    import cli.main as cli_main

    importlib.reload(cli_main)
    cli_main._scaffold_source("demo-requests", ["requests"], write_config=False)
    assert (shared_config.user_sources_dir() / "demo_requests" / "source.json").is_file()


def test_compiled_table_missing_dir_mapping_raises(monkeypatch):
    """静态表与目录映射不一致（构建产物损坏）→ 显式报错，而非一个能用一个不能用。"""
    from novelbase.sources.manifest import ManifestError

    _set_roots(monkeypatch)
    monkeypatch.setattr(source_mod, "_is_compiled", lambda: True)
    monkeypatch.setattr(
        source_mod,
        "_compiled_sources",
        lambda: {"bdir": {"source_name": "orphan-requests", "mode": "requests",
                          "default_config": {"search": {"mode": "requests"}}}},
    )
    monkeypatch.setattr(source_mod, "_compiled_dir_by_source", lambda: {})
    with pytest.raises(ManifestError):
        source_mod.list_sources()
