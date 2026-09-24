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


def test_common_nonempty_without_capability_sections(tmp_path):
    """common 非空但 default_config 零能力段 → ManifestError（而非 TypeError）。"""
    m = {
        "source_name": "demo-empty",
        "enabled": True,
        "common": {"timeout": 30},
        "default_config": {},
    }
    d = _write(tmp_path, m)
    with pytest.raises(ManifestError, match="common"):
        load_manifest(d)

