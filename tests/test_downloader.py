"""Downloader 层测试。"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from novelbase.core.downloader import resolve_meta, resolve_chapter_list, resolve_chapter, get_source
from novelbase.core.options import Options, StorageOptions
from novelbase.models.novel import Novel, Chapter, Chapters
from novelbase.utils.urls import canonical_book_url, make_novel_id


# ── 辅助 ───────────────────────────────────────────────────────

def _make_chapter(chapter_id: str = "ch1", order: int = 1,
                  content: str | None = None) -> Chapter:
    return Chapter(
        id=chapter_id,
        url=f"https://example.com/{chapter_id}",
        novel_id="novel-1", title=f"第{order}章",
        order=order,
        content=content,
    )


def _make_engine():
    eng = MagicMock()
    eng.mode = "browser"
    eng.options = MagicMock()
    eng.options.name = None
    return eng


# ── resolve_chapter ────────────────────────────────────────────

class TestResolveChapter:
    def test_returns_chapter_when_content_available(self):
        """resolve 返回填充后的 Chapter → resolve_chapter 原样返回"""
        engine = _make_engine()
        ch = _make_chapter()

        with patch("novelbase.core.downloader.get_source", return_value="fanqie"):
            with patch("novelbase.source.resolve") as mock_resolve:
                async def _fake(chapter, engine, **kw):
                    return ch

                mock_resolve.return_value = _fake

                result = asyncio.run(resolve_chapter(ch, engine))

        assert result is ch

    def test_returns_none_when_chapter_unavailable(self):
        """底层返回 None → resolve_chapter 透传 None"""
        engine = _make_engine()
        ch = _make_chapter()

        with patch("novelbase.core.downloader.get_source", return_value="fanqie"):
            with patch("novelbase.source.resolve") as mock_resolve:
                async def _fake(chapter, engine, **kw):
                    return None

                mock_resolve.return_value = _fake

                result = asyncio.run(resolve_chapter(ch, engine))

        assert result is None

    def test_raises_when_no_source_found(self):
        """get_source 返回 None → SourceNotFoundError"""
        from novelbase.core.exceptions import SourceNotFoundError

        engine = _make_engine()
        ch = _make_chapter()

        with patch("novelbase.core.downloader.get_source", return_value=None):
            with pytest.raises(SourceNotFoundError, match="source not found"):
                asyncio.run(resolve_chapter(ch, engine))


# ── resolve_meta ─────────────────────────────────────────────────

class TestResolveMeta:
    def test_delegates_to_resolve(self):
        """resolve_meta 通过 registry.resolve 调用底层 novel_info"""
        expected = Novel(
            id="n1", title="测试", url="https://fanqienovel.com/novel",
            author="作者", serial=1, description="",
        )
        engine = _make_engine()

        with patch("novelbase.core.downloader.get_source", return_value="fanqie"):
            with patch("novelbase.source.resolve") as mock_resolve:
                async def _fake(url, engine, **kw):
                    return expected

                mock_resolve.return_value = _fake

                result = asyncio.run(resolve_meta("https://fanqienovel.com/novel", engine))

        assert result is expected

    def test_sets_hash_id_and_platform(self):
        """resolve_meta 中心化生成 hash id 并冗余写入 extra.platform"""
        import re
        engine = _make_engine()
        novel = Novel(title="t", url="https://fanqienovel.com/page/7123456789012345678",
                      serial=1, author="a", description="d")

        with patch("novelbase.core.downloader.get_source", return_value="fanqie"):
            with patch("novelbase.source.resolve") as mock_resolve:
                async def _fake(url, engine, **kw):
                    return novel

                mock_resolve.return_value = _fake

                result = asyncio.run(resolve_meta("https://fanqienovel.com/page/7123456789012345678", engine))

        assert re.fullmatch(r"[0-9a-f]{32}", result.id)
        assert result.extra["platform"] == "fanqie"

    def test_hash_uses_preprocessed_novel_url_not_input(self):
        """hash 基于 resolve_meta 返回的 novel.url（source 预处理后），而非输入 url"""
        engine = _make_engine()
        novel = Novel(title="t", url="https://fanqienovel.com/page/7123456789012345678",
                      serial=1, author="a", description="d")

        with patch("novelbase.core.downloader.get_source", return_value="fanqie"):
            with patch("novelbase.source.resolve") as mock_resolve:
                async def _fake(url, engine, **kw):
                    return novel

                mock_resolve.return_value = _fake

                # 输入是 changdunovel 短链，source 返回标准化 fanqienovel url
                result = asyncio.run(resolve_meta("https://changdunovel.com/t/shortlink", engine))

        expected = make_novel_id(
            canonical_book_url("https://fanqienovel.com/page/7123456789012345678", "fanqie")
        )
        assert result.id == expected
