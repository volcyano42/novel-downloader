"""Downloader 层测试。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from novelbase.core.downloader import resolve_meta, resolve_chapter_list, resolve_chapter, get_source, get_source_for_id
from novelbase.core.options import Options, StorageOptions
from novelbase.models.novel import Novel, Chapter, Chapters


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

        with patch("novelbase.core.downloader.get_source_for_id", return_value="fanqie"):
            with patch("novelbase.utils.registry.resolve") as mock_resolve:
                mock_resolve.return_value = lambda chapter, engine, **kw: ch

                result = resolve_chapter(ch, engine)

        assert result is ch

    def test_returns_none_when_chapter_unavailable(self):
        """底层返回 None → resolve_chapter 透传 None"""
        engine = _make_engine()
        ch = _make_chapter()

        with patch("novelbase.core.downloader.get_source_for_id", return_value="fanqie"):
            with patch("novelbase.utils.registry.resolve") as mock_resolve:
                mock_resolve.return_value = lambda chapter, engine, **kw: None

                result = resolve_chapter(ch, engine)

        assert result is None

    def test_raises_when_no_source_found(self):
        """get_source_for_id 返回 None → SourceNotFoundError"""
        from novelbase.core.exceptions import SourceNotFoundError

        engine = _make_engine()
        ch = _make_chapter()

        with patch("novelbase.core.downloader.get_source_for_id", return_value=None):
            with pytest.raises(SourceNotFoundError, match="source not found"):
                resolve_chapter(ch, engine)


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
            with patch("novelbase.utils.registry.resolve") as mock_resolve:
                mock_resolve.return_value = lambda url, engine, **kw: expected

                result = resolve_meta("https://fanqienovel.com/novel", engine)

        assert result is expected
