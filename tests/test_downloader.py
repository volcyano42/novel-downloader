import asyncio

import pytest

from novelbase.core.downloader import (
    resolve_meta,
    resolve_chapter_list,
    resolve_chapter,
    search,
)
from novelbase.core.exceptions import SourceNotFoundError
from novelbase.models.novel import Novel, Chapter, Chapters, SearchResult
from novelbase.utils.urls import make_novel_id


class _Engine:
    def __init__(self, mode="requests"):
        self.mode = mode


def _engines(engine):
    return lambda mode: engine


def _make_chapter(chapter_id: str = "ch1", order: int = 1,
                  content: str | None = None) -> Chapter:
    return Chapter(
        id=chapter_id,
        url=f"https://example.com/{chapter_id}",
        novel_id="novel-1", title=f"第{order}章",
        order=order,
        content=content,
    )


def test_resolve_meta_returns_novel_with_id(monkeypatch):
    novel = Novel(title="t", url="https://fanqienovel.com/page/7123456789012345678",
                  serial=1, author="a", description="d")

    async def _fake(url, engine, **kw):
        return novel

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    result = asyncio.run(resolve_meta(novel.url, "fanqie-requests-default", _engines(_Engine())))
    assert result.id == make_novel_id(novel.url)
    # 来源元数据不再写入 Novel：resolve_meta 不再打 extra["platform"] 标签（Task 2）
    assert "platform" not in result.extra


def test_resolve_meta_unknown_source(monkeypatch):
    def _boom(name, cap):
        raise ValueError("unknown capability")

    monkeypatch.setattr("novelbase.source.resolve", _boom)
    with pytest.raises(SourceNotFoundError):
        asyncio.run(resolve_meta("https://x/y", "nope", _engines(_Engine())))


def test_hash_uses_preprocessed_novel_url_not_input(monkeypatch):
    """hash 基于 resolve_meta 返回的 novel.url（书源归一后），而非输入 url"""
    novel = Novel(title="t", url="https://fanqienovel.com/page/7123456789012345678",
                  serial=1, author="a", description="d")

    async def _fake(url, engine, **kw):
        return novel

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    # 输入是 changdunovel 短链，书源返回标准化 fanqienovel url
    shortlink = "https://changdunovel.com/t/shortlink"
    result = asyncio.run(resolve_meta(shortlink, "fanqie-requests-default", _engines(_Engine())))

    expected = make_novel_id("https://fanqienovel.com/page/7123456789012345678")
    assert result.id == expected
    # 强断言：id 不是输入短链的 hash（证明取的是归一后的 novel.url）
    assert result.id != make_novel_id(shortlink)


def test_search_tags_result_with_source(monkeypatch):
    async def _fake(query, engine, **kw):
        return (SearchResult(title="a", author="b", url="https://x/1"),)

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    res = asyncio.run(search("s1", "关键词", _engines(_Engine())))
    assert res is not None and res.source_name == "s1"


def test_search_returns_first_result_only(monkeypatch):
    """单源单结果：源内多条命中只返回第一条。"""
    async def _fake(query, engine, **kw):
        return (SearchResult(title="first", author="a", url="https://x/1"),
                SearchResult(title="second", author="b", url="https://x/2"))

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    res = asyncio.run(search("s1", "关键词", _engines(_Engine())))
    assert res is not None and res.title == "first"


def test_search_returns_none_when_source_has_no_result(monkeypatch):
    async def _fake(query, engine, **kw):
        return ()

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    assert asyncio.run(search("s1", "关键词", _engines(_Engine()))) is None


def test_search_propagates_source_error(monkeypatch):
    """源不可用不再被静默跳过：异常上抛，由调用方决定提示还是跳过。"""
    def _resolve(name, cap):
        raise ImportError("boom")

    monkeypatch.setattr("novelbase.source.resolve", _resolve)
    with pytest.raises(ImportError):
        asyncio.run(search("bad", "关键词", _engines(_Engine())))


def test_resolve_chapter_returns_chapter_when_content_available(monkeypatch):
    """底层 resolve 返回填充后的 Chapter → resolve_chapter 原样透传（identity）。"""
    ch = _make_chapter(content="正文")

    async def _fake(chapter, engine, **kw):
        return ch

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    result = asyncio.run(resolve_chapter(ch, "fanqie-requests-default", _engines(_Engine())))
    assert result is ch


def test_resolve_chapter_returns_none_when_chapter_unavailable(monkeypatch):
    """底层 resolve 返回 None → resolve_chapter 透传 None。"""
    ch = _make_chapter()

    async def _fake(chapter, engine, **kw):
        return None

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    result = asyncio.run(resolve_chapter(ch, "fanqie-requests-default", _engines(_Engine())))
    assert result is None


def test_resolve_chapter_list_uses_engine_for_resolved_mode(monkeypatch):
    """resolve_chapter_list 按 source_name 分发，用 resolve 返回的 mode 去 engines(mode) 取引擎。"""
    chapters = Chapters([_make_chapter("c1", 1), _make_chapter("c2", 2)])
    requests_engine = _Engine("requests")
    browser_engine = _Engine("browser")
    seen = {}

    async def _fake(url, engine, **kw):
        seen["url"] = url
        seen["engine"] = engine
        return chapters

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (_fake, "requests"))
    result = asyncio.run(
        resolve_chapter_list("https://example.com/book", "fanqie-requests-default",
                             lambda mode: {"requests": requests_engine, "browser": browser_engine}[mode])
    )
    assert result is chapters
    assert seen["url"] == "https://example.com/book"
    assert seen["engine"] is requests_engine
