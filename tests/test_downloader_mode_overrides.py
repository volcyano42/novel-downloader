"""分发层 mode_overrides：覆盖能力 mode 后，engines 收到覆盖后的 mode。"""
import asyncio

from novelbase.core import downloader
from novelbase.models.novel import Chapter


def _patch_resolve(monkeypatch, declared_mode: str, calls: list[str]):
    """替换 novelbase.source.resolve，返回声明 mode 的假实现。"""

    def fake_resolve(source_name, capability):
        calls.append(capability)

        async def fn(**kwargs):
            return None

        return fn, declared_mode

    monkeypatch.setattr("novelbase.source.resolve", fake_resolve)


def test_resolve_chapter_uses_override_mode(monkeypatch):
    calls: list[str] = []
    _patch_resolve(monkeypatch, "requests", calls)
    seen: list[str] = []

    def engines(mode):
        seen.append(mode)
        return object()

    chapter = Chapter(id="c1", url="https://x/1", novel_id="n1", title="t", order=1)
    asyncio.run(downloader.resolve_chapter(
        chapter, "src", engines, mode_overrides={"chapter_content": "browser"}))

    assert calls == ["chapter_content"]
    assert seen == ["browser"]


def test_resolve_chapter_without_override_uses_declared_mode(monkeypatch):
    calls: list[str] = []
    _patch_resolve(monkeypatch, "requests", calls)
    seen: list[str] = []

    def engines(mode):
        seen.append(mode)
        return object()

    chapter = Chapter(id="c1", url="https://x/1", novel_id="n1", title="t", order=1)
    asyncio.run(downloader.resolve_chapter(chapter, "src", engines))

    assert seen == ["requests"]


def test_search_uses_override_mode(monkeypatch):
    seen: list[str] = []
    _patch_resolve(monkeypatch, "requests", [])

    async def fake_search(**kwargs):
        return ()

    def fake_resolve(source_name, capability):
        return fake_search, "requests"

    monkeypatch.setattr("novelbase.source.resolve", fake_resolve)

    def engines(mode):
        seen.append(mode)
        return object()

    asyncio.run(downloader.search("src", "q", engines,
                                  mode_overrides={"search": "api"}))

    assert seen == ["api"]
