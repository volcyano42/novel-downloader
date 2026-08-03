"""测试 source 能力契约：签名校验、CAPABILITY_META 一致性、capabilities 输出。"""

from inspect import signature
from unittest.mock import Mock

import pytest

from novelbase.sources.contracts import CAPABILITY_META
from novelbase.utils import registry
from novelbase.utils.registry import capabilities, list_sources, resolve


# ═══════════════════════════════════════════════════════════
# 签名校验
# ═══════════════════════════════════════════════════════════


class TestSignatureValidation:
    """运行时签名校验：缺参数拒绝 / 未知能力拒绝。"""

    def test_rejects_missing_params(self, monkeypatch):
        """伪造缺参数函数 → resolve() 抛 ValueError 含缺失参数名。"""

        def bad_search(q, engine):  # 用 q 而非 query
            pass

        class FakeMod:
            pass

        fake_mod = FakeMod()
        setattr(fake_mod, "search", bad_search)

        original_import = registry.import_module

        def fake_import(name, package=None):
            if name.endswith(".search"):
                return fake_mod
            return original_import(name, package=package)

        monkeypatch.setattr(registry, "import_module", fake_import)

        with pytest.raises(ValueError, match="query"):
            resolve("fanqie", "browser", "search")

    def test_unknown_function_raises(self):
        """未知能力名 → ValueError。"""
        with pytest.raises(ValueError, match="unknown function"):
            resolve("fanqie", "browser", "nonexistent")


# ═══════════════════════════════════════════════════════════
# CAPABILITY_META 与实际源文件一致性
# ═══════════════════════════════════════════════════════════


def _iter_funcs(caps: dict):
    """展开 capabilities() 输出 → (mode, provider_or_none, func_name) 三元组。"""
    for mode, mode_caps in caps.items():
        if isinstance(mode_caps, dict):
            for provider, func_names in mode_caps.items():
                for fn in func_names:
                    yield mode, provider, fn
        else:
            for fn in mode_caps:
                yield mode, None, fn


class TestCapabilityMetaConsistency:
    """CAPABILITY_META 定义与真实源文件签名一致。"""

    def test_all_sources_pass_signature_check(self):
        """遍历所有源的所有 mode，签名校验全部通过。"""
        for name in list_sources():
            caps = capabilities(name)
            for mode, provider, func_name in _iter_funcs(caps):
                fn = resolve(name, mode, func_name, provider=provider)
                sig = signature(fn)
                required = CAPABILITY_META[func_name]["required_params"]
                missing = [p for p in required if p not in sig.parameters]
                assert not missing, (
                    f"{name}/{mode}{'/' + provider if provider else ''}/{func_name} "
                    f"签名缺少参数: {missing}. 当前: {list(sig.parameters)}"
                )

    def test_capability_names_in_meta(self):
        """capabilities() 返回的所有能力名都在 CAPABILITY_META 中。"""
        for name in list_sources():
            caps = capabilities(name)
            for _mode, _provider, func_name in _iter_funcs(caps):
                assert func_name in CAPABILITY_META, (
                    f"{name} 的能力 {func_name!r} 不在 CAPABILITY_META 中"
                )


# ═══════════════════════════════════════════════════════════
# capabilities() 输出结构
# ═══════════════════════════════════════════════════════════


class TestCapabilitiesOutput:
    """capabilities() 输出结构保持不变。"""

    def test_fanqie_has_api_with_providers(self):
        caps = capabilities("fanqie")
        assert "api" in caps
        assert isinstance(caps["api"], dict)
        assert "oiapi" in caps["api"]
        assert "rain" in caps["api"]
        for funcs in caps["api"].values():
            assert "search" in funcs
            assert "novel_info" in funcs
            assert "chapter_list" in funcs
            assert "chapter_content" in funcs

    def test_fanqie_has_browser_and_requests(self):
        caps = capabilities("fanqie")
        assert "browser" in caps
        assert isinstance(caps["browser"], list)
        assert "search" in caps["browser"]
        assert "requests" in caps
        assert isinstance(caps["requests"], list)

    def test_nonexistent_source_returns_empty(self):
        assert capabilities("nonexistent") == {}

    def test_qimao_has_api_with_provider(self):
        caps = capabilities("qimao")
        assert "api" in caps
        assert isinstance(caps["api"], dict)
        assert "rain" in caps["api"]
