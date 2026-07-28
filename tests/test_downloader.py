"""Downloader 层测试 — Note: tests need rewriting for pure functions."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from novelbase.core.downloader import fetch_meta, fetch_chapter_list, resolve_chapter
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
    return MagicMock()


# ── resolve_chapter ────────────────────────────────────────────

class TestResolveChapter:
    def test_returns_chapter_when_content_available(self):
        """fetcher 返回 Chapter → resolve_chapter 原样返回"""
        engine = _make_engine()
        ch = _make_chapter()
        fetcher = MagicMock()
        fetcher.fetch_chapter_content.return_value = ch

        result = resolve_chapter(ch, engine, fetcher=fetcher)

        assert result is ch
        fetcher.fetch_chapter_content.assert_called_once_with(
            chapter=ch, engine=engine, skip_delay=False,
        )

    def test_returns_none_when_chapter_unavailable(self):
        """fetcher 返回 None → resolve_chapter 透传 None"""
        engine = _make_engine()
        ch = _make_chapter()
        fetcher = MagicMock()
        fetcher.fetch_chapter_content.return_value = None

        result = resolve_chapter(ch, engine, fetcher=fetcher)

        assert result is None
        fetcher.fetch_chapter_content.assert_called_once()

    def test_raises_when_no_fetcher_found(self):
        """fetcher 参数为 None 且 registry 找不到 → FetcherNotFoundError"""
        from novelbase.core.downloader import FetcherNotFoundError

        engine = _make_engine()
        ch = _make_chapter()

        with patch("novelbase.core.downloader.get_fetcher_for_id", return_value=None):
            with pytest.raises(FetcherNotFoundError, match="fetcher not found"):
                resolve_chapter(ch, engine)


# ── fetch_meta ─────────────────────────────────────────────────

class TestFetchMeta:
    def test_delegates_to_fetcher(self):
        """fetch_meta 调用 fetcher.fetch_novel_info 并返回 Novel"""
        expected = Novel(
            id="n1", title="测试", url="https://example.com",
            author="作者", serial=1, description="",
        )
        engine = _make_engine()

        with patch("novelbase.core.downloader.get_fetcher_for_url") as mock_get:
            mock_fetcher = MagicMock()
            mock_fetcher.fetch_novel_info.return_value = expected
            mock_get.return_value = MagicMock(return_value=mock_fetcher)

            result = fetch_meta("https://example.com/novel", engine)

        assert result is expected
        mock_fetcher.fetch_novel_info.assert_called_once_with(
            url="https://example.com/novel", engine=engine, skip_delay=False,
        )
