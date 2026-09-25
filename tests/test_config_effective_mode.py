"""有效 mode：用户层 sites/{name}.yaml 的 {cap}.mode 覆盖 source.json 声明。"""
import pytest

import shared.config as config_service

KNOWN = "92xs-requests-default"          # 出厂声明：四个能力均为 requests


@pytest.fixture
def isolated_sites(monkeypatch, tmp_path):
    monkeypatch.setattr(config_service, "CONFIG_DIR", tmp_path)
    sites = tmp_path / "sites"
    sites.mkdir(parents=True, exist_ok=True)
    return sites


def _write(sites, cap: str, mode: str):
    (sites / f"{KNOWN}.yaml").write_text(f"{cap}:\n  mode: {mode}\n", encoding="utf-8")


def test_effective_capabilities_defaults_to_declared(isolated_sites):
    caps = config_service.effective_capabilities(KNOWN)
    assert caps["search"] == "requests"
    assert caps["chapter_content"] == "requests"


def test_effective_capabilities_user_override(isolated_sites):
    _write(isolated_sites, "search", "browser")

    caps = config_service.effective_capabilities(KNOWN)

    assert caps["search"] == "browser"
    assert caps["chapter_content"] == "requests"      # 未覆盖的能力仍取声明


def test_effective_capabilities_ignores_invalid_mode(isolated_sites):
    _write(isolated_sites, "search", "nonsense")

    assert config_service.effective_capabilities(KNOWN)["search"] == "requests"


def test_effective_capabilities_unknown_source(isolated_sites):
    assert config_service.effective_capabilities("no-such-source") == {}


def test_merged_source_config_uses_effective_mode_and_keeps_mode_key(isolated_sites):
    _write(isolated_sites, "search", "browser")

    merged = config_service.merged_source_config(KNOWN)

    assert merged["search"]["mode"] == "browser"          # 表单要回显有效 mode
    assert "browser_type" in merged["search"]             # 取 browser 引擎默认字段
    assert merged["chapter_content"]["mode"] == "requests"
    assert "headers" in merged["chapter_content"]         # 未覆盖段取 requests 默认字段


def test_build_options_follows_effective_mode(isolated_sites):
    _write(isolated_sites, "search", "browser")

    opts = config_service.build_options(KNOWN, "browser")

    assert opts.mode == "browser"


def test_merged_source_config_invalid_mode_falls_back_in_output(isolated_sites):
    """用户层非法 mode：输出的 mode 回退为声明值，字段集仍按有效 mode 构建。"""
    _write(isolated_sites, "search", "nonsense")

    merged = config_service.merged_source_config(KNOWN)

    assert merged["search"]["mode"] == "requests"        # 不变量：mode 恒等于有效 mode
    assert "headers" in merged["search"]                 # 字段集取自有效 mode（requests）
    assert "browser_type" not in merged["search"]


def test_merged_source_config_null_mode_falls_back_in_output(isolated_sites):
    """用户层 YAML `mode:`（None）：输出的 mode 回退为声明值，不残留 None。"""
    (isolated_sites / f"{KNOWN}.yaml").write_text("search:\n  mode:\n", encoding="utf-8")

    merged = config_service.merged_source_config(KNOWN)

    assert merged["search"]["mode"] == "requests"
