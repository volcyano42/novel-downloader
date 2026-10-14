"""用户层 common 段的合并优先级（spec: 2026-10-14-source-common-config-design.md）。"""
import novelbase.source  # noqa: F401  —— patch 目标模块需先加载
import shared.config as config

CAPS = ("search", "novel_info", "chapter_list", "chapter_content")


def _patch_source(monkeypatch, user_cfg, caps=None, defaults=None):
    """把书源解析的外部依赖替换为固定值。

    ⚠️ `merged_source_config` 内部用的是 `from novelbase.source import get_manifest`
    （**函数内导入**），所以必须 patch `novelbase.source.get_manifest`；
    patch `config.get_manifest` 不会生效（那份属性不存在，函数也不会去读）。
    """
    monkeypatch.setattr(config, "effective_capabilities", lambda name: caps or {c: "api" for c in CAPS})
    monkeypatch.setattr(config, "_user_site_cfg", lambda name: user_cfg)
    monkeypatch.setattr("novelbase.source.get_manifest",
                        lambda name: {"default_config": defaults or {c: {} for c in CAPS}})


def test_common_applies_to_every_capability(monkeypatch):
    """common 里的键出现在每个能力段。"""
    _patch_source(monkeypatch, {"common": {"timeout": 42, "key": "k1"}})
    out = config.merged_source_config("x")
    for cap in CAPS:
        assert out[cap]["timeout"] == 42
        assert out[cap]["key"] == "k1"


def test_capability_overrides_common(monkeypatch):
    """能力段的值压过 common（逐能力覆盖仍然有效）。"""
    _patch_source(monkeypatch, {"common": {"delay": [1, 1]}, "chapter_content": {"delay": [9, 9]}})
    out = config.merged_source_config("x")
    assert out["chapter_content"]["delay"] == [9, 9]
    assert out["search"]["delay"] == [1, 1]


def test_absent_common_is_noop(monkeypatch):
    """没有 common 段时，结果与旧行为一致（回归）。"""
    _patch_source(monkeypatch, {"search": {"timeout": 7}})
    out = config.merged_source_config("x")
    assert out["search"]["timeout"] == 7
    assert out["search"]["mode"] == "api"


def test_common_does_not_override_mode(monkeypatch):
    """common 里的 mode 不参与覆盖（有效 mode 不变量）。"""
    _patch_source(monkeypatch, {"common": {"mode": "browser"}})
    out = config.merged_source_config("x")
    assert out["search"]["mode"] == "api"
