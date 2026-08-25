"""site 配置 variant 感知辅助函数测试。"""
import pytest

from shared.config import (
    get_mode_variant_config, mode_variants, load_mode_config,
)


def _site():
    return {
        "browser": {"default": {"headless": False, "timeout": 30}},
        "requests": {"default": {"timeout": 30}},
        "api": {"oiapi": {"key": ""}, "rain": {"key": ""}},
    }


def test_get_mode_variant_config_default():
    assert get_mode_variant_config(_site(), "browser") == {"headless": False, "timeout": 30}


def test_get_mode_variant_config_named():
    assert get_mode_variant_config(_site(), "api", "rain") == {"key": ""}


def test_get_mode_variant_config_first_when_no_default():
    site = {"browser": {"alpha": {"a": 1}, "beta": {"b": 2}}}
    assert get_mode_variant_config(site, "browser") == {"a": 1}


def test_get_mode_variant_config_non_dict_returns_empty():
    assert get_mode_variant_config({"browser": {"default": "scalar"}}, "browser") == {}
    assert get_mode_variant_config({"browser": None}, "browser") == {}
    assert get_mode_variant_config({}, "browser") == {}


def test_mode_variants_lists_dict_keys_only():
    assert mode_variants(_site(), "browser") == ["default"]
    assert mode_variants(_site(), "api") == ["oiapi", "rain"]
    assert mode_variants({"browser": {"default": "scalar"}}, "browser") == []


def test_load_mode_config(tmp_path, monkeypatch):
    import shared.config as sc
    site_file = tmp_path / "sites" / "fanqie.yaml"
    site_file.parent.mkdir(parents=True)
    site_file.write_text(
        "browser:\n  default:\n    timeout: 42\n", encoding="utf-8")
    monkeypatch.setattr(sc, "CONFIG_DIR", tmp_path)
    assert load_mode_config("fanqie", "browser") == {"timeout": 42}
