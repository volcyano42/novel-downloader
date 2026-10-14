"""PUT/GET 的 common 契约（spec: 2026-10-14-source-common-config-design.md）。"""
import asyncio

import yaml

from backend.routers import config as cfg_router
from backend.services import source_guard


def _setup(tmp_path, monkeypatch, initial: dict | None = None):
    monkeypatch.setattr(cfg_router.config_service, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(source_guard, "list_sources", lambda: ["demo-api-default"])
    (tmp_path / "sites").mkdir(parents=True, exist_ok=True)
    if initial is not None:
        (tmp_path / "sites" / "demo-api-default.yaml").write_text(
            yaml.safe_dump(initial, allow_unicode=True), encoding="utf-8")
    return tmp_path / "sites" / "demo-api-default.yaml"


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_put_common_writes_and_clears_capability_keys(tmp_path, monkeypatch):
    """写 common.key 时，各能力段里的 key 被删除（否则旧值优先、改了不生效）。"""
    path = _setup(tmp_path, monkeypatch, {
        "search": {"mode": "api", "key": "old"},
        "novel_info": {"mode": "api", "key": "old"},
    })
    asyncio.run(cfg_router.save_source_config("demo-api-default", {"common": {"key": "new"}}))
    data = _load(path)
    assert data["common"]["key"] == "new"
    assert "key" not in data["search"]
    assert "key" not in data["novel_info"]
    assert data["search"]["mode"] == "api"          # 其它键不受影响


def test_put_common_null_deletes_key(tmp_path, monkeypatch):
    """{common: {k: null}} 删除该键。"""
    path = _setup(tmp_path, monkeypatch, {"common": {"timeout": 30, "key": "x"}})
    asyncio.run(cfg_router.save_source_config("demo-api-default", {"common": {"key": None}}))
    data = _load(path)
    assert "key" not in data["common"]
    assert data["common"]["timeout"] == 30


def test_get_reports_user_overrides(tmp_path, monkeypatch):
    """GET 返回各能力段在用户层实际出现的键。"""
    _setup(tmp_path, monkeypatch, {"common": {"key": "x"},
                                   "search": {"mode": "api", "delay": [1, 1]}})
    monkeypatch.setattr(cfg_router, "effective_capabilities", lambda n: {"search": "api"})
    monkeypatch.setattr(cfg_router, "capabilities", lambda n: {"search": "api"})
    monkeypatch.setattr(cfg_router.config_service, "merged_source_config",
                        lambda n: {"search": {"mode": "api"}})
    monkeypatch.setattr(cfg_router.config_service, "source_concurrency", lambda n: 1)
    monkeypatch.setattr(cfg_router.config_service, "source_group", lambda n: "")
    monkeypatch.setattr(cfg_router.config_service, "source_alias", lambda n: "")
    out = asyncio.run(cfg_router.get_source_config("demo-api-default"))
    assert out["user_overrides"]["search"] == ["delay", "mode"]
    assert out["user_overrides"].get("novel_info") in (None, [])
