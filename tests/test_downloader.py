"""Downloader 层测试：resolve_chapter 返回类型 + fetch_meta 委托"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nldlder.core.downloader import NovelDownloader
from nldlder.core.options import Options, StorageOptions
from nldlder.models.novel import Novel, Chapter, Chapters


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


def _make_downloader(engine=None, options=None) -> NovelDownloader:
    if engine is None:
        engine = MagicMock()
    if options is None:
        options = Options()
    return NovelDownloader(engine=engine, options=options)


# ── resolve_chapter ────────────────────────────────────────────

class TestResolveChapter:
    def test_returns_chapter_when_content_available(self):
        """fetcher 返回 Chapter → resolve_chapter 原样返回"""
        dl = _make_downloader()
        ch = _make_chapter()
        fetcher = MagicMock()
        fetcher.fetch_chapter_content.return_value = ch

        result = dl.resolve_chapter(ch, fetcher=fetcher)

        assert result is ch
        fetcher.fetch_chapter_content.assert_called_once_with(
            chapter=ch, engine=dl.engine,
        )

    def test_returns_none_when_chapter_unavailable(self):
        """fetcher 返回 None → resolve_chapter 透传 None"""
        dl = _make_downloader()
        ch = _make_chapter()
        fetcher = MagicMock()
        fetcher.fetch_chapter_content.return_value = None

        result = dl.resolve_chapter(ch, fetcher=fetcher)

        assert result is None
        fetcher.fetch_chapter_content.assert_called_once()

    def test_raises_when_no_fetcher_found(self):
        """fetcher 参数为 None 且 registry 找不到 → FetcherNotFoundError"""
        from nldlder.core.downloader import FetcherNotFoundError

        dl = _make_downloader()
        ch = _make_chapter()

        with patch("nldlder.core.downloader.get_fetcher_for_id", return_value=None):
            with pytest.raises(FetcherNotFoundError, match="fetcher not found"):
                dl.resolve_chapter(ch)


# ── fetch_meta ─────────────────────────────────────────────────

class TestFetchMeta:
    def test_delegates_to_fetcher(self):
        """fetch_meta 调用 fetcher.fetch_novel_info 并返回 Novel"""
        expected = Novel(
            id="n1", title="测试", url="https://example.com",
            author="作者", serial=1, description="",
        )
        dl = _make_downloader()
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_novel_info.return_value = expected

        with patch.object(dl, "_resolve_fetcher", return_value=mock_fetcher):
            result = dl.fetch_meta("https://example.com/novel")

        assert result is expected
        mock_fetcher.fetch_novel_info.assert_called_once_with(
            url="https://example.com/novel", engine=dl.engine,
        )


# ── fetch_chapter_list ─────────────────────────────────────────

class TestFetchChapterList:
    def test_delegates_to_fetcher(self):
        """fetch_chapter_list 调用 fetcher.fetch_chapter_list 并返回 Chapters"""
        ch1 = _make_chapter("ch1", 1)
        ch2 = _make_chapter("ch2", 2)
        expected = Chapters([ch1, ch2])
        dl = _make_downloader()
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_chapter_list.return_value = expected

        with patch.object(dl, "_resolve_fetcher", return_value=mock_fetcher):
            result = dl.fetch_chapter_list("https://example.com/novel")

        assert result is expected
        assert len(result) == 2


# ── storage 属性 ───────────────────────────────────────────────

class TestStorageProperty:
    def test_lazy_init_creates_storage(self):
        """首次访问 storage 属性时惰性创建 SQLiteStorage"""
        opts = Options()
        opts.set_storage_options(StorageOptions(database_url="sqlite:///:memory:"))
        dl = _make_downloader(options=opts)

        store = dl.storage
        assert store is not None
        # 再次访问返回同一实例
        assert dl.storage is store

    def test_raises_when_not_configured(self):
        """未配置 StorageOptions 时访问 storage 抛 RuntimeError"""
        dl = _make_downloader()  # 没有 set_storage_options
        with pytest.raises(RuntimeError, match="StorageOptions not configured"):
            _ = dl.storage
