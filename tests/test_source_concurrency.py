"""书源级 concurrency：用户层顶层覆盖 source.json 顶层，缺省 1；非法值回退默认。"""
import pytest

import shared.config as config_service

KNOWN = "92xs-requests-default"


@pytest.fixture
def isolated_sites(monkeypatch, tmp_path):
    monkeypatch.setattr(config_service, "CONFIG_DIR", tmp_path)
    sites = tmp_path / "sites"
    sites.mkdir(parents=True, exist_ok=True)
    return sites


def test_default_is_one(isolated_sites):
    assert config_service.SOURCE_CONCURRENCY_DEFAULT == 1
    assert config_service.source_concurrency(KNOWN) == 1


def test_manifest_top_level_declaration(monkeypatch, isolated_sites):
    """source.json 顶层声明生效（真实源未声明，用桩）。"""
    monkeypatch.setattr("novelbase.source.get_manifest",
                        lambda name: {"concurrency": 4})
    assert config_service.source_concurrency(KNOWN) == 4


def test_user_layer_overrides_manifest(monkeypatch, isolated_sites):
    monkeypatch.setattr("novelbase.source.get_manifest",
                        lambda name: {"concurrency": 4})
    (isolated_sites / f"{KNOWN}.yaml").write_text("concurrency: 7\n", encoding="utf-8")
    assert config_service.source_concurrency(KNOWN) == 7


@pytest.mark.parametrize("bad", [0, -1, "x"])
def test_invalid_user_value_falls_back(isolated_sites, bad):
    (isolated_sites / f"{KNOWN}.yaml").write_text(
        f"concurrency: {bad}\n", encoding="utf-8")
    assert config_service.source_concurrency(KNOWN) == 1


@pytest.mark.parametrize("bad", [0, -1, "x"])
def test_invalid_manifest_value_falls_back(monkeypatch, isolated_sites, bad):
    monkeypatch.setattr("novelbase.source.get_manifest",
                        lambda name: {"concurrency": bad})
    assert config_service.source_concurrency(KNOWN) == 1


def test_unknown_source_returns_default(isolated_sites):
    assert config_service.source_concurrency("no-such-source") == 1
