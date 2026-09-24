# tests/test_downloader.py（重写）
import asyncio

import pytest

from novelbase.core.downloader import resolve_meta, search
from novelbase.core.exceptions import SourceNotFoundError
from novelbase.models.novel import Novel, SearchResult
from novelbase.utils.urls import make_novel_id


class _Engine:
    def __init__(self, mode="requests"):
        self.mode = mode


def _engines(engine):
    return lambda mode: engine


def test_resolve_meta_returns_novel_with_id(monkeypatch):
    novel = Novel(title="t", url="https://fanqienovel.com/page/7123456789012345678",
                  serial=1, author="a", description="d")

    async def _fake(url, engine, **kw):
        return novel

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    result = asyncio.run(resolve_meta(novel.url, "fanqie-requests-default", _engines(_Engine())))
    assert result.id == make_novel_id(novel.url)
    assert result.extra["platform"] == "fanqie-requests-default"


def test_resolve_meta_unknown_source(monkeypatch):
    def _boom(name, cap):
        raise ValueError("unknown capability")

    monkeypatch.setattr("novelbase.source.resolve", _boom)
    with pytest.raises(SourceNotFoundError):
        asyncio.run(resolve_meta("https://x/y", "nope", _engines(_Engine())))


def test_search_tags_each_result_with_source(monkeypatch):
    async def _fake(query, engine, **kw):
        return (SearchResult(title="a", author="b", url="https://x/1"),)

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    res = asyncio.run(search(["s1", "s2"], "关键词", _engines(_Engine())))
    assert {r.source_name for r in res} == {"s1", "s2"}


def test_search_skips_failing_source(monkeypatch):
    async def _ok(query, engine, **kw):
        return (SearchResult(title="a", author="b", url="https://x/1"),)

    def _resolve(name, cap):
        if name == "bad":
            raise ImportError("boom")
        return _ok, "requests"

    monkeypatch.setattr("novelbase.source.resolve", _resolve)
    res = asyncio.run(search(["bad", "good"], "关键词", _engines(_Engine())))
    assert len(res) == 1 and res[0].source_name == "good"
