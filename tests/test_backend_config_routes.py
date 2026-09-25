"""书源配置端点的 mode 契约：有效 mode + 声明 mode 双出，PUT 支持删除覆盖。"""
import asyncio

import pytest

import shared.config as config_service
from backend.routers import config as cfg
from backend.routers import download as dl
from backend.services import source_guard

KNOWN = "92xs-requests-default"          # 声明 mode = requests


@pytest.fixture
def isolated_sites(monkeypatch, tmp_path):
    monkeypatch.setattr(config_service, "CONFIG_DIR", tmp_path)
    sites = tmp_path / "sites"
    sites.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(source_guard, "list_sources", lambda: [KNOWN])
    return sites


def test_get_source_config_returns_effective_and_declared(isolated_sites):
    (isolated_sites / f"{KNOWN}.yaml").write_text("search:\n  mode: browser\n", encoding="utf-8")

    data = asyncio.run(cfg.get_source_config(KNOWN))

    assert data["capabilities"]["search"] == "browser"
    assert data["declared_capabilities"]["search"] == "requests"
    assert data["config"]["search"]["mode"] == "browser"


def test_put_source_config_writes_mode_override(isolated_sites):
    asyncio.run(cfg.save_source_config(KNOWN, {"config": {"search": {"mode": "browser"}}}))

    saved = config_service.load_yaml(isolated_sites / f"{KNOWN}.yaml")

    assert saved["search"]["mode"] == "browser"
    assert config_service.effective_capabilities(KNOWN)["search"] == "browser"


def test_put_source_config_mode_null_removes_override(isolated_sites):
    (isolated_sites / f"{KNOWN}.yaml").write_text("search:\n  mode: browser\n", encoding="utf-8")

    asyncio.run(cfg.save_source_config(KNOWN, {"config": {"search": {"mode": None}}}))

    saved = config_service.load_yaml(isolated_sites / f"{KNOWN}.yaml")
    assert "mode" not in (saved.get("search") or {})
    assert config_service.effective_capabilities(KNOWN)["search"] == "requests"


def test_download_sources_returns_effective_mode(isolated_sites):
    (isolated_sites / f"{KNOWN}.yaml").write_text("search:\n  mode: browser\n", encoding="utf-8")

    data = asyncio.run(dl.list_all_sources())

    assert data[KNOWN]["capabilities"]["search"] == "browser"
