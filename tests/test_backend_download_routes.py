"""backend download 路由的运行时契约（T7 定型后的新形状）。

不启 TestClient/lifespan（避免 Windows 下 lifespan 挂起），直接 `asyncio.run`
调 async 路由函数；monkeypatch 书源 `resolve`、引擎工厂、模块级依赖，验证：
- `/sources` 平铺形状 `{source_name: {capabilities: {cap: mode}, enabled: bool}}`。
- `/search`：`source` 空 → 并发全部启用书源（`enabled_source_names()`）；单书源 →
  引擎按 `source_name` 绑定；`query` 为 URL 时 `source` 必填（400）；URL 结果带 `source_name`。
- `/novel`、`/novel/{id}`、`/novel/{id}/chapters` 的 Query 仅 `source`（=source_name），
  URL 无法推断书源时要求显式 `source`。
- `/novel/{id}/chapter` 把 `source`/`novel_url` 透传给 `task_manager.create_task`。
- 旧 `platform`/`mode`/`variant` 面（`/platform`、`/detect`、`_pick_source`）已删除。
"""
import asyncio

import pytest
from fastapi import HTTPException

from backend.routers import download as dl
from backend.schemas import FetchMetaRequest, DownloadChapterRequest
from novelbase.models.novel import Chapters, Novel


def _patch_engine_factory(monkeypatch):
    """替换 dl 模块内的引擎工厂，记录 (source_name, mode)，返回占位 engine。"""
    seen: list[tuple[str, str]] = []

    def fake(source_name, mode):
        seen.append((source_name, mode))
        return object()

    monkeypatch.setattr(dl, "get_cached_engine", fake)
    return seen


def test_sources_shape_is_flat(monkeypatch):
    monkeypatch.setattr(dl, "list_sources", lambda: ["92xs-requests-default"])
    monkeypatch.setattr(dl, "capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr(dl, "is_source_enabled", lambda n: True)
    out = asyncio.run(dl.list_all_sources())
    assert out == {"92xs-requests-default": {"capabilities": {"search": "requests"}, "enabled": True}}


def test_sources_include_disabled(monkeypatch):
    """列全部书源（含未启用），enabled 走 is_source_enabled(name)。"""
    monkeypatch.setattr(dl, "list_sources", lambda: ["a-x-default", "b-y-default"])
    monkeypatch.setattr(dl, "capabilities", lambda n: {"search": "requests"})
    monkeypatch.setattr(dl, "is_source_enabled", lambda n: n == "a-x-default")
    out = asyncio.run(dl.list_all_sources())
    assert out["a-x-default"]["enabled"] is True
    assert out["b-y-default"]["enabled"] is False


def test_search_empty_source_uses_enabled(monkeypatch):
    monkeypatch.setattr(dl, "enabled_source_names", lambda: ["a-x-default", "b-y-default"])
    called = []

    async def fake_search(sources, query, engines, **kw):
        called.append(list(sources))
        return ()

    monkeypatch.setattr(dl, "search", fake_search)
    asyncio.run(dl.search_novels(query="关键词", source=""))
    assert called == [["a-x-default", "b-y-default"]]


def test_search_single_source_binds_engine(monkeypatch):
    seen = _patch_engine_factory(monkeypatch)
    captured = {}

    async def fake_search(sources, query, engines, **kw):
        captured["sources"] = list(sources)
        captured["engine"] = engines("requests")
        return ()

    monkeypatch.setattr(dl, "search", fake_search)
    asyncio.run(dl.search_novels(query="关键词", source="92xs-requests-default"))
    assert captured["sources"] == ["92xs-requests-default"]
    assert seen == [("92xs-requests-default", "requests")]


def test_url_search_requires_source(monkeypatch):
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.search_novels(query="https://x/1", source=""))
    assert ei.value.status_code == 400


def test_url_search_returns_source_name(monkeypatch):
    async def fake_novel(url, engine, **kw):
        return Novel(url=url, title="T", author="A", serial=1, description="d")

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake_novel, "requests"))
    seen = _patch_engine_factory(monkeypatch)
    out = asyncio.run(dl.search_novels(query="http://www.92xs.info/book/9999.html",
                                       source="92xs-requests-default"))
    assert out[0].title == "T"
    assert out[0].source_name == "92xs-requests-default"
    assert seen == [("92xs-requests-default", "requests")]


def test_resolve_meta_route_requires_source(monkeypatch):
    with pytest.raises(HTTPException) as ei:
        asyncio.run(dl.resolve_meta_route(
            body=FetchMetaRequest(url="https://fanqienovel.com/page/7123456789012345678"),
            source=""))
    assert ei.value.status_code == 400


def test_resolve_meta_route_with_source(monkeypatch):
    async def fake_novel(url, engine, **kw):
        return Novel(url=url, title="T", author="A", serial=2, description="d")

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake_novel, "requests"))
    seen = _patch_engine_factory(monkeypatch)
    body = FetchMetaRequest(url="https://fanqienovel.com/page/7123456789012345678")
    out = asyncio.run(dl.resolve_meta_route(body=body, source="fanqie-requests-default"))
    assert out["title"] == "T"
    assert seen == [("fanqie-requests-default", "requests")]


def test_chapter_list_route_with_source(monkeypatch):
    async def fake_cl(url, engine, **kw):
        return Chapters([])

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake_cl, "requests"))
    seen = _patch_engine_factory(monkeypatch)
    out = asyncio.run(dl.resolve_chapter_list_route(
        novel_id="abc", url="http://www.92xs.info/book/9999.html",
        source="92xs-requests-default"))
    assert out == []
    assert seen == [("92xs-requests-default", "requests")]


def test_download_chapters_passes_source(monkeypatch):
    recorded = {}

    def fake_create_task(novel_id, chapters, title, source_name, novel_url):
        recorded.update(novel_id=novel_id, chapters=chapters, title=title,
                        source_name=source_name, novel_url=novel_url)
        return {"task_id": "x", "total": len(chapters)}

    monkeypatch.setattr(dl.task_manager, "create_task", fake_create_task)
    body = [DownloadChapterRequest(id="c1", url="u", novel_id="n1", title="t", order=1)]
    out = asyncio.run(dl.download_chapters(novel_id="n1", body=body, title="T",
                                           source="92xs-requests-default",
                                           novel_url="http://x/1"))
    assert out == {"task_id": "x", "total": 1}
    assert recorded["source_name"] == "92xs-requests-default"
    assert recorded["novel_url"] == "http://x/1"


def test_platform_and_detect_gone():
    assert not hasattr(dl, "detect_platform")
    assert not hasattr(dl, "list_platforms")
    assert not hasattr(dl, "_pick_source")


def test_search_result_data_uses_source_name():
    from backend.schemas import SearchResultData
    r = SearchResultData(title="t", author="a", url="http://x", source_name="92xs-requests-default")
    assert r.source_name == "92xs-requests-default"
    assert not hasattr(r, "platform")
