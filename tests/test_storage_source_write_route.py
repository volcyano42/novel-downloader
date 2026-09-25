"""换源写端点：PUT /novel/{novel_id}/source 的持久化与 404 语义。

- 换源成功 → 落库到 user_data.novel_sources，响应回显新书源
- UPSERT：连续两次换源取后者（一书一源）
- 未知书源 → 404（source_guard.require_known_source 是 HTTP 边界唯一校验点）
- 小说不存在 → 404
"""
import asyncio

import pytest
from fastapi import HTTPException

from backend.routers import storage as storage_router
from backend.schemas import SetSourceRequest
from backend.services import source_guard
from shared import user_data

_KNOWN = "fanqie-api-rain"
_KNOWN2 = "92xs-requests-default"


@pytest.fixture
def isolated_user_db(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")
    return user_data


def _only_known(monkeypatch, *names):
    """把校验用的 list_sources 收窄为给定的已知源（见 test_backend_source_guard.py）。"""
    monkeypatch.setattr(source_guard, "list_sources", lambda: list(names))


class FakeStore:
    def __init__(self, novel_ids):
        self._ids = set(novel_ids)

    def load_meta(self, novel_id):
        return object() if novel_id in self._ids else None


def _patch_store(monkeypatch, *novel_ids):
    monkeypatch.setattr(storage_router, "_get_storage", lambda: FakeStore(novel_ids))


def test_switch_source_persists(monkeypatch, isolated_user_db):
    _only_known(monkeypatch, _KNOWN, _KNOWN2)
    _patch_store(monkeypatch, "n1")

    resp = asyncio.run(storage_router.set_novel_source_route(
        "n1", SetSourceRequest(source_name=_KNOWN)))

    assert resp == {"status": "ok", "novel_id": "n1", "source_name": _KNOWN}
    assert isolated_user_db.get_novel_source("n1") == _KNOWN


def test_switch_source_upserts(monkeypatch, isolated_user_db):
    _only_known(monkeypatch, _KNOWN, _KNOWN2)
    _patch_store(monkeypatch, "n1")

    asyncio.run(storage_router.set_novel_source_route(
        "n1", SetSourceRequest(source_name=_KNOWN)))
    resp = asyncio.run(storage_router.set_novel_source_route(
        "n1", SetSourceRequest(source_name=_KNOWN2)))

    assert resp["source_name"] == _KNOWN2
    assert isolated_user_db.get_novel_source("n1") == _KNOWN2


def test_switch_unknown_source_404(monkeypatch, isolated_user_db):
    _only_known(monkeypatch, _KNOWN)
    _patch_store(monkeypatch, "n1")

    with pytest.raises(HTTPException) as ei:
        asyncio.run(storage_router.set_novel_source_route(
            "n1", SetSourceRequest(source_name="nope-default")))

    assert ei.value.status_code == 404
    assert isolated_user_db.get_novel_source("n1") is None


def test_switch_missing_novel_404(monkeypatch, isolated_user_db):
    _only_known(monkeypatch, _KNOWN)
    _patch_store(monkeypatch, "n1")

    with pytest.raises(HTTPException) as ei:
        asyncio.run(storage_router.set_novel_source_route(
            "nope", SetSourceRequest(source_name=_KNOWN)))

    assert ei.value.status_code == 404
