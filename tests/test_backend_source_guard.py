"""未知 source_name 的 HTTP 边界校验：所有按 source_name 取参的入口一律 404。

core 层（`capabilities()` / `merged_source_config()`）对未知源返回空值是宽容语义，
404 只在 HTTP 边界产生——本文件锁定该边界。
"""
import asyncio

import pytest
from fastapi import HTTPException

from backend.routers import config as cfg
from backend.routers import download as dl
from backend.schemas import FetchMetaRequest
from backend.services import source_guard

_KNOWN = "92xs-requests-default"


def _only_known(monkeypatch):
    """把校验用的 list_sources 收窄为单一已知源。"""
    monkeypatch.setattr(source_guard, "list_sources", lambda: [_KNOWN])


def test_known_source_passes(monkeypatch):
    _only_known(monkeypatch)
    assert source_guard.require_known_source(_KNOWN) == _KNOWN


def test_unknown_source_raises_404(monkeypatch):
    _only_known(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        source_guard.require_known_source("nope-default")
    assert ei.value.status_code == 404
    assert "nope-default" in ei.value.detail


def test_config_get_unknown_source_404(monkeypatch):
    _only_known(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(cfg.get_source_config("nope-default"))
    assert ei.value.status_code == 404


def test_config_put_unknown_source_404(monkeypatch):
    """PUT 不得凭空创建 sites/unknown.yaml。"""
    _only_known(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(cfg.save_source_config("nope-default", {}))
    assert ei.value.status_code == 404


def test_search_single_unknown_source_404(monkeypatch):
    _only_known(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.search_novels(query="关键字", source="nope-default"))
    assert ei.value.status_code == 404


def test_search_url_unknown_source_404(monkeypatch):
    _only_known(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.search_novels(query="https://example.com/book/1", source="nope-default"))
    assert ei.value.status_code == 404


def test_novel_unknown_source_404(monkeypatch):
    _only_known(monkeypatch)
    body = FetchMetaRequest(url="https://example.com/book/1")
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.resolve_meta_route(body, source="nope-default"))
    assert ei.value.status_code == 404
