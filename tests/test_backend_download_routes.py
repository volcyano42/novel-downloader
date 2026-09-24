"""backend download 路由的运行时契约：签名迁移后不再 500/TypeError。

不启 TestClient/lifespan（避免 Windows 下 lifespan 挂起），直接 `asyncio.run`
调 async 路由函数；monkeypatch 书源 `resolve` 与引擎工厂，验证：
- `/search`（关键字 / URL / all）走新签名 `search(sources, query, engines)` /
  `resolve_meta(url, source_name, engines)`。
- `/novel`、`/novel/{id}/chapters` 走新签名，且 URL 无法推断书源时要求显式 `source`。
- 请求里的 platform 标识被解析为确定 source_name，并以 (site, variant) 交给引擎工厂。
"""
import asyncio

import pytest
from fastapi import HTTPException

from backend.routers import download as dl
from backend.schemas import FetchMetaRequest
from novelbase.models.novel import Chapters, Novel, SearchResult


def _patch_engine_factory(monkeypatch):
    """替换 dl 模块内的引擎工厂，记录 (source_name, mode)，返回占位 engine。"""
    seen: list[tuple[str, str]] = []

    def fake(source_name, mode):
        seen.append((source_name, mode))
        return object()

    monkeypatch.setattr(dl, "get_cached_engine_for_source", fake)
    return seen


def test_search_keyword_uses_new_signature(monkeypatch):
    async def fake_search(query, engine, **kw):
        return (SearchResult(title="a", author="b", url="https://x/1"),)

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake_search, "requests"))
    seen = _patch_engine_factory(monkeypatch)

    out = asyncio.run(dl.search_novels(platform="fanqie-requests-default",
                                       query="关键词", mode="requests", variant=None))
    assert out[0].title == "a"
    assert seen == [("fanqie-requests-default", "requests")]


def test_search_url_uses_new_signature(monkeypatch):
    async def fake_novel(url, engine, **kw):
        return Novel(url=url, title="T", author="A", serial=1, description="d")

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake_novel, "requests"))
    seen = _patch_engine_factory(monkeypatch)

    out = asyncio.run(dl.search_novels(platform="92xs-requests-default",
                                       query="http://www.92xs.info/book/9999.html",
                                       mode="requests", variant=None))
    assert out[0].title == "T"
    assert seen == [("92xs-requests-default", "requests")]


def test_search_all_uses_all_sources(monkeypatch):
    calls = []

    async def fake_search(query, engine, **kw):
        calls.append(engine)
        return (SearchResult(title="a", author="b", url="https://x/1"),)

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake_search, "requests"))
    monkeypatch.setattr(dl, "get_cached_engine",
                        lambda p, m, variant=None: f"engine:{p}:{m}")

    out = asyncio.run(dl.search_novels(platform="all", query="x", mode="requests", variant=None))
    assert len(out) == len(dl.list_sources())
    assert calls and all(c == "engine:fanqie:requests" for c in calls)


def test_search_unknown_platform_is_400(monkeypatch):
    _patch_engine_factory(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.search_novels(platform="nope", query="x", mode="requests", variant=None))
    assert ei.value.status_code == 400


def test_resolve_meta_route_requires_source(monkeypatch):
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.resolve_meta_route(
            body=FetchMetaRequest(url="https://fanqienovel.com/page/7123456789012345678"),
            mode="requests", variant=None, source=None))
    assert ei.value.status_code == 400


def test_resolve_meta_route_with_source(monkeypatch):
    async def fake_novel(url, engine, **kw):
        return Novel(url=url, title="T", author="A", serial=2, description="d")

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake_novel, "requests"))
    seen = _patch_engine_factory(monkeypatch)

    body = FetchMetaRequest(url="https://fanqienovel.com/page/7123456789012345678")
    out = asyncio.run(dl.resolve_meta_route(body=body, mode="requests", variant=None,
                                            source="fanqie-requests-default"))
    assert out["title"] == "T"
    assert seen == [("fanqie-requests-default", "requests")]


def test_chapter_list_route_with_source(monkeypatch):
    async def fake_cl(url, engine, **kw):
        return Chapters([])

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake_cl, "requests"))
    seen = _patch_engine_factory(monkeypatch)

    out = asyncio.run(dl.resolve_chapter_list_route(
        novel_id="abc", url="http://www.92xs.info/book/9999.html",
        mode="requests", variant=None, source="92xs-requests-default"))
    assert out == []
    assert seen == [("92xs-requests-default", "requests")]


def test_get_cached_engine_for_source_parses_name(monkeypatch):
    from backend.services import engine_manager as em
    seen: dict = {}

    def fake_get_cached(platform, mode, variant=None):
        seen.update(platform=platform, mode=mode, variant=variant)
        return "E"

    monkeypatch.setattr(em, "get_cached_engine", fake_get_cached)

    assert em.get_cached_engine_for_source("qimao-api-rain", "api") == "E"
    assert seen == {"platform": "qimao", "mode": "api", "variant": "rain"}
    assert em.get_cached_engine_for_source("92xs-requests-default", "requests") == "E"
    assert seen == {"platform": "92xs", "mode": "requests", "variant": "default"}


def test_search_result_data_uses_source_name():
    from backend.schemas import SearchResultData
    r = SearchResultData(title="t", author="a", url="http://x", source_name="92xs-requests-default")
    assert r.source_name == "92xs-requests-default"
    assert not hasattr(r, "platform")
