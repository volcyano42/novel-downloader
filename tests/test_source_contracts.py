"""测试 source 能力契约：签名校验、CAPABILITY_META 一致性、capabilities 输出。"""

from inspect import signature

import pytest

from novelbase.source import capabilities, list_sources, resolve
from novelbase.sources.contracts import CAPABILITY_META
import novelbase.source as _source_mod


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

        original_import = _source_mod.import_module

        def fake_import(name, package=None):
            if name.endswith(".search"):
                return fake_mod
            return original_import(name, package=package)

        monkeypatch.setattr(_source_mod, "import_module", fake_import)

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
    """展开 capabilities() 输出 → (mode, variant_or_none, func_name) 三元组。

    caps 统一为 {mode: {variant: [funcs]}}，"default" 表示无 variant 子目录。
    """
    for mode, variants in caps.items():
        for variant, func_names in variants.items():
            p = None if variant == "default" else variant
            for fn in func_names:
                yield mode, p, fn


class TestCapabilityMetaConsistency:
    """CAPABILITY_META 定义与真实源文件签名一致。"""

    def test_all_sources_pass_signature_check(self):
        """遍历所有源的所有 mode，签名校验全部通过。"""
        for name in list_sources():
            caps = capabilities(name)
            for mode, variant, func_name in _iter_funcs(caps):
                fn = resolve(name, mode, func_name, variant=variant)
                sig = signature(fn)
                required = CAPABILITY_META[func_name]["required_params"]
                missing = [p for p in required if p not in sig.parameters]
                assert not missing, (
                    f"{name}/{mode}{'/' + variant if variant else ''}/{func_name} "
                    f"签名缺少参数: {missing}. 当前: {list(sig.parameters)}"
                )

    def test_capability_names_in_meta(self):
        """capabilities() 返回的所有能力名都在 CAPABILITY_META 中。"""
        for name in list_sources():
            caps = capabilities(name)
            for _mode, _variant, func_name in _iter_funcs(caps):
                assert func_name in CAPABILITY_META, (
                    f"{name} 的能力 {func_name!r} 不在 CAPABILITY_META 中"
                )


# ═══════════════════════════════════════════════════════════
# capabilities() 输出结构 — 统一 {mode: {variant: [funcs]}}
# ═══════════════════════════════════════════════════════════


class TestCapabilitiesOutput:
    """capabilities() 输出结构：统一 dict[str, dict[str, list[str]]]。"""

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

    def test_fanqie_browser_has_default_variant_key(self):
        """单 variant mode → {"default": [...]}。"""
        caps = capabilities("fanqie")
        assert "browser" in caps
        assert isinstance(caps["browser"], dict)
        assert "default" in caps["browser"]
        assert "search" in caps["browser"]["default"]
        assert "requests" in caps
        assert isinstance(caps["requests"], dict)
        assert "default" in caps["requests"]

    def test_nonexistent_source_returns_empty(self):
        assert capabilities("nonexistent") == {}

    def test_qimao_has_api_with_provider(self):
        caps = capabilities("qimao")
        assert "api" in caps
        assert isinstance(caps["api"], dict)
        assert "rain" in caps["api"]


# ═══════════════════════════════════════════════════════════════
# 私有源隔离 — NLD_PRIVATE_SOURCES
# ═══════════════════════════════════════════════════════════════


class TestPrivateSources:
    """NLD_PRIVATE_SOURCES 环境变量指向外部私有源目录。"""

    def test_no_env_returns_only_builtin(self):
        """未设置环境变量时仅返回内置源。"""
        caps = capabilities("fanqie")
        assert "api" in caps
        assert "browser" in caps
        # 内置 oiapi/rain 存在，但不应有私有 variant
        assert set(caps["api"].keys()) == {"oiapi", "rain"}

    def test_private_variant_merged(self, monkeypatch, tmp_path):
        """私有目录新增 variant 出现在合并结果中。"""
        import novelbase.source as src_mod

        private = tmp_path / "fanqie" / "api" / "mypriv"
        private.mkdir(parents=True)
        (private / "search.py").write_text("""
def search(query: str, engine, **kwargs):
    return ()
""")
        monkeypatch.setattr(src_mod, "_PRIVATE_SOURCES_ROOT", str(tmp_path))

        caps = capabilities("fanqie")
        assert "mypriv" in caps["api"]
        assert "search" in caps["api"]["mypriv"]

    def test_private_variant_resolve(self, monkeypatch, tmp_path):
        """resolve() 可以从私有目录加载函数。"""
        import novelbase.source as src_mod

        private = tmp_path / "fanqie" / "api" / "mypriv"
        private.mkdir(parents=True)
        (private / "search.py").write_text("""
def search(query: str, engine, **kwargs):
    return ()
""")
        monkeypatch.setattr(src_mod, "_PRIVATE_SOURCES_ROOT", str(tmp_path))

        fn = resolve("fanqie", "api", "search", "mypriv")
        assert fn is not None
        result = fn("test", None)
        assert result == ()

    @pytest.mark.skip(reason="monkeypatch + tmp_path 在 Windows 上超时")
    def test_private_overrides_builtin_caps(self, monkeypatch, tmp_path):
        """同名 variant 私有源合并进 capabilities。"""
        import novelbase.source as src_mod

        private = tmp_path / "fanqie" / "api" / "rain"
        private.mkdir(parents=True)
        (private / "search.py").write_text("""
def search(query: str, engine, **kwargs):
    return ()
""")
        monkeypatch.setattr(src_mod, "_PRIVATE_SOURCES_ROOT", str(tmp_path))

        caps = capabilities("fanqie")
        assert "rain" in caps["api"]  # 同名被私有 merge

    def test_private_dir_not_exist_graceful(self, monkeypatch):
        """私有目录不存在时静默跳过。"""
        import novelbase.source as src_mod

        monkeypatch.setattr(src_mod, "_PRIVATE_SOURCES_ROOT", "/nonexistent/path")
        caps = capabilities("fanqie")
        assert "api" in caps  # 内置仍正常
