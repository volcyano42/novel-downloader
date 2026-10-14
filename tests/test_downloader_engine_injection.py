"""分发层注入单个 Engine 实例：core 原样交给书源能力函数，不再解析 mode。"""
import asyncio

import pytest

from novelbase.core import downloader
from novelbase.models.novel import Chapter, Novel, SearchResult
from novelbase.utils.urls import make_novel_id


def _patch_resolve(monkeypatch, result, seen: dict):
    """替换 novelbase.source.resolve：返回记录 kwargs 的假能力函数。"""

    async def fake(**kwargs):
        seen.update(kwargs)
        return result

    monkeypatch.setattr("novelbase.source.resolve", lambda name, cap: (fake, "requests"))


def test_search_passes_injected_engine(monkeypatch):
    engine = object()
    seen: dict = {}
    _patch_resolve(monkeypatch, [], seen)

    assert asyncio.run(downloader.search("src", "q", engine)) is None
    assert seen["engine"] is engine
    assert seen["skip_delay"] is False


def test_search_stamps_source_name(monkeypatch):
    engine = object()
    seen: dict = {}
    _patch_resolve(monkeypatch, [SearchResult(title="t", author="a", url="https://x/1")], seen)

    hit = asyncio.run(downloader.search("src", "q", engine))
    assert hit.source_name == "src"      # 统一打标（书源侧不写死）


def test_resolve_meta_passes_injected_engine(monkeypatch):
    engine = object()
    seen: dict = {}
    _patch_resolve(monkeypatch, Novel(title="t", url="https://x/n1", author="a",
                                      serial=1, description="d"), seen)

    novel = asyncio.run(downloader.resolve_meta("https://x/n1", "src", engine))
    assert seen["engine"] is engine
    assert novel.id == make_novel_id("https://x/n1")     # 中心赋值仍生效


def test_resolve_chapter_list_passes_injected_engine(monkeypatch):
    engine = object()
    seen: dict = {}
    _patch_resolve(monkeypatch, [], seen)

    asyncio.run(downloader.resolve_chapter_list("https://x/n1", "src", engine))
    assert seen["engine"] is engine


def test_resolve_chapter_passes_injected_engine(monkeypatch):
    engine = object()
    seen: dict = {}
    _patch_resolve(monkeypatch, None, seen)
    chapter = Chapter(id="c1", url="https://x/1", novel_id="n1", title="t", order=1)

    asyncio.run(downloader.resolve_chapter(chapter, "src", engine))
    assert seen["engine"] is engine
    assert seen["chapter"] is chapter


def test_rejects_legacy_engines_resolver(monkeypatch):
    """旧的 `engines(mode) -> engine` 解析器必须响亮报错（第三方迁移指引）。

    防呆优先于书源解析：连假的 resolve 都不该被用到（否则错误源会先抛无关异常）。
    """
    _patch_resolve(monkeypatch, [], {})
    with pytest.raises(TypeError) as ei:
        asyncio.run(downloader.search("src", "q", lambda mode: object()))
    assert "Engine 实例" in str(ei.value)
