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
