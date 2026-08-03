"""测试 source 能力契约：签名校验、CAPABILITY_META 一致性、capabilities 输出。"""

import importlib
from inspect import signature
from unittest.mock import Mock

import pytest

from novelbase.sources.contracts import CAPABILITY_META
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

        import importlib as _il
        original_import = _il.import_module

        def fake_import(name, package=None):
            if name.endswith(".search"):
                return fake_mod
            return original_import(name, package=package)

        monkeypatch.setattr("novelbase.utils.registry.import_module", fake_import)
        # 也要 patch capabilities() 中扫描时用到的 import_module
        monkeypatch.setattr(_il, "import_module", original_import)

        with pytest.raises(ValueError, match="query"):
            resolve("fanqie", "browser", "search")

    def test_unknown_function_raises(self):
        """未知能力名 → ValueError。"""
        with pytest.raises(ValueError, match="unknown function"):
            resolve("fanqie", "browser", "nonexistent")


# ═══════════════════════════════════════════════════════════
# CAPABILITY_META 与实际源文件一致性
# ═══════════════════════════════════════════════════════════


class TestCapabilityMetaConsistency:
    """CAPABILITY_META 定义与真实源文件签名一致。"""

    def test_all_sources_pass_signature_check(self):
        """遍历所有源的所有 mode，签名校验全部通过。"""
        for name in list_sources():
            caps = capabilities(name)
            for mode, mode_caps in caps.items():
                if isinstance(mode_caps, dict):
                    # 多 provider：{provider: [func_names]}
                    for provider, func_names in mode_caps.items():
                        for func_name in func_names:
                            fn = resolve(name, mode, func_name, provider=provider)
                            sig = signature(fn)
                            required = CAPABILITY_META[func_name]["required_params"]
                            missing = [p for p in required if p not in sig.parameters]
                            assert not missing, (
                                f"{name}/{mode}/{provider}/{func_name} 签名缺少参数: {missing}. "
                                f"当前: {list(sig.parameters)}"
                            )
                else:
                    # 单 provider：[func_names]
                    for func_name in mode_caps:
                        fn = resolve(name, mode, func_name)
                        sig = signature(fn)
                        required = CAPABILITY_META[func_name]["required_params"]
                        missing = [p for p in required if p not in sig.parameters]
                        assert not missing, (
                            f"{name}/{mode}/{func_name} 签名缺少参数: {missing}. "
                            f"当前: {list(sig.parameters)}"
                        )

    def test_capability_names_in_meta(self):
        """capabilities() 返回的所有能力名都在 CAPABILITY_META 中。"""
        for name in list_sources():
            caps = capabilities(name)
            for mode_caps in caps.values():
                if isinstance(mode_caps, dict):
                    # 多 provider：{provider: [func_names]}
                    for func_names in mode_caps.values():
                        for n in func_names:
                            assert n in CAPABILITY_META, (
                                f"{name} 的能力 {n!r} 不在 CAPABILITY_META 中"
                            )
                else:
                    for n in mode_caps:
                        assert n in CAPABILITY_META, (
                            f"{name} 的能力 {n!r} 不在 CAPABILITY_META 中"
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
