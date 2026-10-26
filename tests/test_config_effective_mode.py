"""有效 mode：用户层 sources/{name}.yaml 的**顶层** `mode` 覆盖 source.json 声明。

2026-10-25 起一个书源只有一个 mode，所有能力共享（不再逐能力覆盖）。
"""
import pytest

import shared.config as config_service

KNOWN = "92xs-requests-default"          # 出厂声明：requests


@pytest.fixture
def isolated_sources(monkeypatch, tmp_path):
    monkeypatch.setattr(config_service, "CONFIG_DIR", tmp_path)
    sources = tmp_path / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    return sources


def _write(sources, mode):
    (sources / f"{KNOWN}.yaml").write_text(f"mode: {mode}\n", encoding="utf-8")


def test_effective_capabilities_defaults_to_declared(isolated_sources):
    caps = config_service.effective_capabilities(KNOWN)
    assert caps["search"] == "requests"
    assert caps["chapter_content"] == "requests"


def test_user_override_applies_to_all_capabilities(isolated_sources):
    """顶层 mode 覆盖对**所有**能力生效（不再逐能力覆盖）。"""
    _write(isolated_sources, "browser")

    caps = config_service.effective_capabilities(KNOWN)

    assert set(caps.values()) == {"browser"}


def test_effective_capabilities_ignores_invalid_mode(isolated_sources):
    _write(isolated_sources, "nonsense")

    assert config_service.effective_capabilities(KNOWN)["search"] == "requests"


def test_effective_capabilities_unknown_source(isolated_sources):
    assert config_service.effective_capabilities("no-such-source") == {}


def test_merged_source_config_uses_effective_mode(isolated_sources):
    _write(isolated_sources, "browser")

    merged = config_service.merged_source_config(KNOWN)

    assert merged["search"]["mode"] == "browser"          # 表单要回显有效 mode
    assert "browser_type" in merged["search"]             # 取 browser 引擎默认字段
    # 各能力拿到的是同一套参数
    assert merged["chapter_content"]["mode"] == "browser"
    assert "browser_type" in merged["chapter_content"]


def test_build_options_follows_effective_mode(isolated_sources):
    _write(isolated_sources, "browser")

    opts = config_service.build_options(KNOWN, "browser")

    assert opts.mode == "browser"


def test_merged_source_config_invalid_mode_falls_back_in_output(isolated_sources):
    """用户层非法 mode：输出回退为声明值，字段集按有效 mode 构建。"""
    _write(isolated_sources, "nonsense")

    merged = config_service.merged_source_config(KNOWN)

    assert merged["search"]["mode"] == "requests"        # 不变量：mode 恒等于有效 mode
    assert "headers" in merged["search"]                 # 字段集取自有效 mode（requests）
    assert "browser_type" not in merged["search"]


def test_merged_source_config_null_mode_falls_back_in_output(isolated_sources):
    """用户层 YAML `mode:`（None）：输出回退为声明值，不残留 None。"""
    (isolated_sources / f"{KNOWN}.yaml").write_text("mode:\n", encoding="utf-8")

    merged = config_service.merged_source_config(KNOWN)

    assert merged["search"]["mode"] == "requests"
