"""测试 source 能力契约：签名校验、CAPABILITY_META 一致性、capabilities 输出、私有源。"""
import json
from inspect import signature
from pathlib import Path

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
        """source_name 唯一性（spec:254）。

        注意：不能直接对 `list_sources()` 去重后再断言 len 相等——该函数内部用
        set 收集，返回值恒已去重，那样断言恒真。这里绕过它，直接扫目录读
        `source.json['source_name']` 再查重复。
        """
        roots = [_source_mod._SOURCES_DIR]
        if _source_mod._PRIVATE_SOURCES_ROOT:
            roots.append(Path(_source_mod._PRIVATE_SOURCES_ROOT))
        names: list[str] = []
        for root in roots:
            root = Path(root)
            if not root.is_dir():
                continue
            for entry in sorted(root.iterdir()):
                if not entry.is_dir() or entry.name.startswith("_"):
                    continue
                manifest = entry / "source.json"
                if not manifest.is_file():
                    continue
                names.append(json.loads(manifest.read_text(encoding="utf-8"))["source_name"])
        duplicated = sorted({n for n in names if names.count(n) > 1})
        assert not duplicated, f"重复的 source_name: {duplicated}"


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
    """同名书源的同名能力文件：内置优先于私有。

    必须在私有侧真的放一个**同名目录 + 可区分的 search 实现**，否则「私有优先」
    与「内置优先」结果相同，测试无区分力。
    """
    import novelbase.source as s

    d = tmp_path / "92xs_requests_default"   # 与内置目录同名
    d.mkdir()
    (d / "source.json").write_text(json.dumps({
        "source_name": "92xs-requests-default",
        "enabled": True,
        "default_config": {"search": {"mode": "requests"}},
    }, ensure_ascii=False), encoding="utf-8")
    (d / "search.py").write_text(
        "PRIVATE_MARKER = 'private'\n"
        "async def search(query, engine, **kwargs):\n"
        "    return ('private',)\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", str(tmp_path))
    fn, mode = s.resolve("92xs-requests-default", "search")

    # 拿到的是内置模块的实现，而非刚写入的私有文件（私有模块名形如
    # novelbase_private.sources.92xs_requests_default.search）
    assert fn.__module__ == "novelbase.sources.92xs_requests_default.search"
    assert fn.__module__ != "novelbase_private.sources.92xs_requests_default.search"
    assert mode == "requests"


def test_private_dir_not_exist_graceful(monkeypatch):
    """私有目录不存在时静默跳过：内置源仍正常。"""
    import novelbase.source as s
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", "/nonexistent/path")
    assert s.capabilities("92xs-requests-default") == {
        "search": "requests", "novel_info": "requests",
        "chapter_list": "requests", "chapter_content": "requests",
    }


def test_no_env_returns_only_builtin(monkeypatch):
    """未设置 NLD_PRIVATE_SOURCES 时只列出内置 10 个书源。"""
    import novelbase.source as s
    monkeypatch.setattr(s, "_PRIVATE_SOURCES_ROOT", None)
    names = s.list_sources()
    assert len(names) == 10
    assert set(names) == {
        "92xs-requests-default", "fanqie-api-oiapi", "fanqie-api-rain",
        "fanqie-browser-default", "fanqie-requests-default",
        "qidian-browser-default", "qidian-requests-default",
        "qimao-api-rain", "qimao-browser-default", "qimao-requests-default",
    }


def test_capability_meta_keys_are_file_stems():
    """能力名 = 文件名 = 函数名；meta 里不再有 file_stem 字段。"""
    assert set(CAPABILITY_META) == {"search", "novel_info", "chapter_list", "chapter_content"}
    for name, meta in CAPABILITY_META.items():
        assert "file_stem" not in meta
        assert "required_params" in meta


def test_required_params_unchanged():
    assert CAPABILITY_META["search"]["required_params"] == ("query", "engine")
    assert CAPABILITY_META["novel_info"]["required_params"] == ("url", "engine")
    assert CAPABILITY_META["chapter_list"]["required_params"] == ("url", "engine")
    assert CAPABILITY_META["chapter_content"]["required_params"] == ("chapter", "engine")
