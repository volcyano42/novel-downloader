"""`source_name` 全局唯一：实现层检测（spec: docs/superpowers/specs/2026-09-27-source-name-uniqueness-design.md）。"""
import json
from pathlib import Path

import pytest

from novelbase.sources.manifest import (DuplicateSourceNameError, ManifestError, scan_source_names)


def _source(root: Path, dirname: str, source_name: str) -> Path:
    """在 root 下造一个最小书源目录（source.json + search.py）。"""
    d = root / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "source.json").write_text(json.dumps({
        "source_name": source_name,
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


def test_duplicate_message_names_both_dirs(tmp_path):
    """报错消息必须同时给出「先占者」与「后来者」两个目录，才可操作。"""
    first = _source(tmp_path, "demo_a", "demo-requests-default")
    second = _source(tmp_path, "demo_b", "demo-requests-default")
    with pytest.raises(DuplicateSourceNameError) as ei:
        scan_source_names([tmp_path])
    msg = str(ei.value)
    assert str(first) in msg
    assert str(second) in msg


def test_distinct_names_across_roots_ok(tmp_path):
    builtin, private = tmp_path / "builtin", tmp_path / "private"
    _source(builtin, "demo_a", "demo-requests-default")
    _source(private, "demo_b", "other-requests-default")
    result = scan_source_names([builtin, private])
    assert sorted(result) == ["demo-requests-default", "other-requests-default"]
    assert result["demo-requests-default"] == builtin / "demo_a"
    assert result["other-requests-default"] == private / "demo_b"


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


def test_duplicate_is_manifest_error_subclass(tmp_path):
    """`DuplicateSourceNameError` ⊂ `ManifestError`：既有 `except ManifestError` 依赖它。"""
    assert issubclass(DuplicateSourceNameError, ManifestError)
    _source(tmp_path, "demo_a", "demo-requests-default")
    _source(tmp_path, "demo_b", "demo-requests-default")
    with pytest.raises(ManifestError):
        scan_source_names([tmp_path])
