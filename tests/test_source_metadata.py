# -*- coding: utf-8 -*-
"""书源元信息（分组/别名）、默认参与集与出厂 manifest 契约。"""
import pytest

from shared import config as sc

BROWSER_CAPS = {"search": "browser", "novel_info": "browser",
                "chapter_list": "browser", "chapter_content": "browser"}
REQUESTS_CAPS = {"search": "requests", "novel_info": "requests",
                 "chapter_list": "requests", "chapter_content": "requests"}


def _patch_sources(monkeypatch, capabilities_map, manifest_extra=None):
    """钉住书源清单 / 声明能力 / 出厂 manifest（manifest_extra: {name: {顶层字段}}）。"""
    extra = manifest_extra or {}
    monkeypatch.setattr("novelbase.source.list_sources", lambda: sorted(capabilities_map))
    monkeypatch.setattr("novelbase.source.capabilities", lambda n: dict(capabilities_map.get(n, {})))
    monkeypatch.setattr("novelbase.source.get_manifest",
                        lambda n: {"source_name": n, "default_config": {}, **extra.get(n, {})})


def test_meta_defaults_when_nothing_set(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    _patch_sources(monkeypatch, {"demo-requests-default": REQUESTS_CAPS})
    assert sc.source_alias("demo-requests-default") == ""
    assert sc.source_group("demo-requests-default") == ""
    assert sc.display_name("demo-requests-default") == "demo-requests-default"


def test_meta_declared_then_user_override(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    _patch_sources(monkeypatch, {"demo-requests-default": REQUESTS_CAPS},
                   {"demo-requests-default": {"source_alias": "出厂别名", "source_group": "出厂组"}})
    assert sc.display_name("demo-requests-default") == "出厂别名"
    assert sc.source_group("demo-requests-default") == "出厂组"

    sc.save_site_config("demo-requests-default", {"source_alias": "用户别名", "source_group": "用户组"})
    assert sc.display_name("demo-requests-default") == "用户别名"
    assert sc.source_group("demo-requests-default") == "用户组"


def test_meta_blank_user_value_falls_back(tmp_path, monkeypatch):
    """用户层键被删除（空串即清除）后回落到出厂值。"""
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    _patch_sources(monkeypatch, {"demo-requests-default": REQUESTS_CAPS},
                   {"demo-requests-default": {"source_alias": "出厂别名"}})
    sc.save_site_config("demo-requests-default", {"source_alias": "用户别名"})
    assert sc.display_name("demo-requests-default") == "用户别名"
    sc.save_site_config("demo-requests-default", {"source_alias": ""})
    assert sc.display_name("demo-requests-default") == "出厂别名"


def test_meta_unknown_source_is_tolerant(tmp_path, monkeypatch):
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    _patch_sources(monkeypatch, {})
    assert sc.source_alias("nope-default") == ""
    assert sc.source_group("nope-default") == ""
    assert sc.display_name("nope-default") == "nope-default"


def test_default_source_names_lists_all_sources(tmp_path, monkeypatch):
    """默认参与集 = 全部书源（无任何环境相关过滤）。"""
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    _patch_sources(monkeypatch, {"b-requests-default": REQUESTS_CAPS,
                                 "a-browser-default": BROWSER_CAPS})
    assert sc.default_source_names() == ["a-browser-default", "b-requests-default"]


def test_manifest_rejects_blank_optional_meta(tmp_path, monkeypatch):
    """出厂 manifest 的 source_alias / source_group 必须是非空字符串。"""
    import json
    from novelbase.sources import manifest as mf

    src = tmp_path / "demo"
    src.mkdir()
    (src / "source.json").write_text(json.dumps({
        "source_name": "demo-requests-default",
        "source_group": "   ",
        "default_config": {},
    }), encoding="utf-8")
    with pytest.raises(mf.ManifestError):
        mf.load_manifest(src)


def test_manifest_without_enabled_is_valid(tmp_path):
    """source.json 不再需要 enabled。"""
    import json
    from novelbase.sources import manifest as mf

    src = tmp_path / "demo2"
    src.mkdir()
    (src / "source.json").write_text(json.dumps({
        "source_name": "demo2-requests-default",
        "source_group": "演示",
        "default_config": {},
    }), encoding="utf-8")
    assert mf.load_manifest(src)["source_name"] == "demo2-requests-default"


def test_merged_source_config_three_layers(tmp_path, monkeypatch):
    """三层合并（自 test_source_enabled.py 迁移）：系统默认 → 出厂 manifest → 用户层。"""
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr("novelbase.source.capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr("novelbase.source.get_manifest", lambda n: {
        "source_name": n,
        "default_config": {"search": {"mode": "requests", "timeout": 30, "retry_times": 3}},
    })
    merged = sc.merged_source_config("demo-requests-default")
    assert merged["search"]["mode"] == "requests"
    assert merged["search"]["timeout"] == 30          # 第 2 层
    sc.save_site_config("demo-requests-default", {"search": {"timeout": 99}})
    assert sc.merged_source_config("demo-requests-default")["search"]["timeout"] == 99
