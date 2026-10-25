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
    "mode": "requests",
    "timeout": 30,
    "retry_times": 3,
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
    bad = {k: v for k, v in BASE.items() if k != "source_name"}
    d = _write(tmp_path, bad)
    with pytest.raises(ManifestError, match="source_name"):
        load_manifest(d)


def test_load_manifest_unknown_mode(tmp_path):
    bad = json.loads(json.dumps(BASE))
    bad["mode"] = "openapi"
    d = _write(tmp_path, bad)
    with pytest.raises(ManifestError, match="mode"):
        load_manifest(d)


def test_load_manifest_field_not_allowed_for_mode(tmp_path):
    bad = json.loads(json.dumps(BASE))
    bad["key"] = "xxx"        # key 只属于 api mode
    d = _write(tmp_path, bad)
    with pytest.raises(ManifestError, match="key"):
        load_manifest(d)


def test_variant_is_not_a_valid_field(tmp_path):
    """variant 字段已取消（2026-09-24）：同一 mode 下的不同实现各自是一个书源。"""
    bad = json.loads(json.dumps(BASE))
    bad["variant"] = "rain"
    d = _write(tmp_path, bad)
    with pytest.raises(ManifestError, match="variant"):
        load_manifest(d)


def test_allowed_fields_are_kept_and_normalized(tmp_path):
    """允许的字段原样保留，并归一化成 {能力: 完整字段}（下游形状不变）。"""
    d = _write(tmp_path, BASE, ("search.py",))
    got = load_manifest(d)
    assert got["default_config"]["search"]["timeout"] == 30
    assert got["default_config"]["search"]["mode"] == "requests"


def test_mode_override_replaces_declared(tmp_path):
    """顶层 mode 是唯一 mode 来源（不再有能力级 mode）。"""
    m = dict(BASE); m["mode"] = "api"; m["key"] = "k"
    d = _write(tmp_path, m, ("search.py",))
    got = load_manifest(d)
    assert got["default_config"]["search"]["mode"] == "api"


def test_no_capability_files_is_rejected_at_check(tmp_path):
    """能力由文件系统发现：一个能力文件都没有时，check_capability_files 报错。

    不在 load_manifest 里报 —— 否则 scan_source_names() 会在扫描期静默跳过该目录。
    """
    d = _write(tmp_path, BASE, ())
    m = load_manifest(d)
    assert m["default_config"] == {}
    with pytest.raises(ManifestError, match="没有任何能力文件"):
        check_capability_files(d, m)


def test_capabilities_follow_files(tmp_path):
    """只实现部分能力时，归一化结果只含那一项（不再由 manifest 声明能力）。"""
    d = _write(tmp_path, BASE, ("search.py", "novel_info.py"))
    m = load_manifest(d)
    assert set(m["default_config"]) == {"search", "novel_info"}
    check_capability_files(d, m)   # 不抛


