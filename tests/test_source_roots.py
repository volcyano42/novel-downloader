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
