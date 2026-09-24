"""测试 source 能力契约：签名校验、CAPABILITY_META 一致性、capabilities 输出、私有源。"""
import json
from inspect import signature

import pytest

import novelbase.source as _source_mod
from novelbase.source import capabilities, list_sources, resolve
from novelbase.sources.contracts import CAPABILITY_META


class TestSignatureValidation:
    """运行时签名校验：缺参数拒绝 / 未知能力拒绝。"""

    def test_rejects_missing_params(self, monkeypatch):
        def bad_search(q, engine):  # 用 q 而非 query
            pass

        class FakeMod:
            pass

        fake_mod = FakeMod()
        setattr(fake_mod, "search", bad_search)
        original_import = _source_mod.import_module

        def fake_import(name, package=None):
            if name.endswith(".search"):
                return fake_mod
            return original_import(name, package=package)

        monkeypatch.setattr(_source_mod, "import_module", fake_import)
        with pytest.raises(ValueError, match="query"):
            resolve("92xs-requests-default", "search")

    def test_unknown_capability_raises(self):
        with pytest.raises(ValueError, match="unknown capability"):
            resolve("92xs-requests-default", "nonexistent")


class TestCapabilityMetaConsistency:
    """CAPABILITY_META 定义与真实源文件签名一致。"""

    def test_all_sources_pass_signature_check(self):
        for name in list_sources():
            caps = capabilities(name)
            for cap in caps:
                fn, _mode = resolve(name, cap)
                sig = signature(fn)
                required = CAPABILITY_META[cap]["required_params"]
                missing = [p for p in required if p not in sig.parameters]
                assert not missing, f"{name}/{cap} 签名缺少参数: {missing}"

    def test_capability_names_in_meta(self):
        for name in list_sources():
            for cap in capabilities(name):
                assert cap in CAPABILITY_META, f"{name} 的能力 {cap!r} 不在 CAPABILITY_META 中"


class TestCapabilitiesOutput:
    """capabilities() 输出结构：dict[str, str]（{capability: mode}）。"""

    def test_92xs_all_requests(self):
        assert capabilities("92xs-requests-default") == {
            "search": "requests", "novel_info": "requests",
            "chapter_list": "requests", "chapter_content": "requests",
        }

    def test_nonexistent_source_returns_empty(self):
        assert capabilities("nonexistent") == {}

    def test_ten_sources_listed(self):
        names = list_sources()
        assert len(names) == 10
        assert "fanqie-api-rain" in names and "fanqie" not in names

    def test_source_names_unique(self):
        """source_name 唯一性（spec:254）：所有书源的 source_name 互不重复。"""
        names = list_sources()
        assert len(names) == len(set(names))


def test_private_source_merged(tmp_path, monkeypatch):
    d = tmp_path / "demo_requests_default"   # 目录名：下划线（合法标识符）
    d.mkdir()
    (d / "source.json").write_text(json.dumps({
        "source_name": "demo-requests-default",   # source_name：连字符（与目录名解耦）
        "enabled": True,
        "default_config": {"search": {"mode": "requests"}},
    }, ensure_ascii=False), encoding="utf-8")
    (d / "search.py").write_text(
        "async def search(query, engine, **kwargs):\n    return ()\n", encoding="utf-8")

    import novelbase.source as s
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", str(tmp_path))

    assert "demo-requests-default" in s.list_sources()
    assert s.capabilities("demo-requests-default") == {"search": "requests"}
    fn, mode = s.resolve("demo-requests-default", "search")
    assert callable(fn) and mode == "requests"


def test_builtin_wins_over_private(tmp_path, monkeypatch):
    """同名书源的同名能力文件：内置优先于私有。"""
    import novelbase.source as s
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", str(tmp_path))
    fn, _ = s.resolve("92xs-requests-default", "search")
    assert fn.__module__ == "novelbase.sources.92xs_requests_default.search"
