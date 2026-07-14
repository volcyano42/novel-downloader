"""异常测试：验证异常消息格式和属性"""
from __future__ import annotations

from novelbase.core.exceptions import (
    NovelDownloaderError,
    NetworkError,
    AuthenticationError,
    NovelNotFoundError,
    ChapterNotFoundError,
    ParseError,
    FetcherNotFoundError,
    FeatureNotSupportedError,
    StorageError,
    AntiCrawlError,
)


class TestNovelDownloaderError:
    def test_base_exception(self):
        e = NovelDownloaderError("出错了")
        assert str(e) == "出错了"
        assert isinstance(e, Exception)


class TestNetworkError:
    def test_default(self):
        e = NetworkError()
        assert str(e) == "Network request failed"
        assert e.url is None

    def test_with_url(self):
        e = NetworkError(url="http://example.com")
        assert "http://example.com" in str(e)
        assert e.url == "http://example.com"

    def test_custom_message(self):
        e = NetworkError("连接超时", url="http://x.com")
        assert "连接超时" in str(e)
        assert "http://x.com" in str(e)


class TestAuthenticationError:
    def test_default(self):
        e = AuthenticationError(platform="fanqie")
        assert "fanqie" in str(e)
        assert e.platform == "fanqie"

    def test_custom_message(self):
        e = AuthenticationError(platform="qidian", message="登录失败")
        assert "登录失败" in str(e)
        assert "qidian" in str(e)


class TestNovelNotFoundError:
    def test_default(self):
        e = NovelNotFoundError()
        assert str(e) == "Novel not found"

    def test_with_url(self):
        e = NovelNotFoundError(url="http://x.com/novel")
        assert "http://x.com/novel" in str(e)


class TestChapterNotFoundError:
    def test_default(self):
        e = ChapterNotFoundError()
        assert str(e) == "Chapter not found"

    def test_with_url(self):
        e = ChapterNotFoundError(url="http://x.com/ch1")
        assert "http://x.com/ch1" in str(e)


class TestParseError:
    def test_default(self):
        e = ParseError()
        assert str(e) == "Parse error"

    def test_with_detail(self):
        e = ParseError(detail="HTML 结构异常")
        assert "HTML 结构异常" in str(e)
        assert e.detail == "HTML 结构异常"


class TestFetcherNotFoundError:
    def test_default(self):
        e = FetcherNotFoundError()
        assert str(e) == "Fetcher not found"

    def test_custom(self):
        e = FetcherNotFoundError("未找到解析器")
        assert "未找到解析器" in str(e)


class TestFeatureNotSupportedError:
    def test_default(self):
        e = FeatureNotSupportedError()
        assert "Feature not supported" == str(e)

    def test_custom_message(self):
        e = FeatureNotSupportedError("不支持导出")
        assert "不支持导出" == str(e)


class TestStorageError:
    def test_default(self):
        e = StorageError()
        assert "Storage operation failed" in str(e)

    def test_with_path(self):
        e = StorageError(path="/data/novel.json")
        assert "/data/novel.json" in str(e)
        assert e.path == "/data/novel.json"


class TestAntiCrawlError:
    def test_default(self):
        e = AntiCrawlError()
        assert "Anti-crawl" in str(e)

    def test_with_url(self):
        e = AntiCrawlError(url="http://x.com/chapter/1")
        assert "http://x.com/chapter/1" in str(e)

    def test_with_retry_after(self):
        e = AntiCrawlError(retry_after=60.0)
        assert "retry_after" in str(e)
        assert e.retry_after == 60.0

    def test_with_all(self):
        e = AntiCrawlError(url="http://x.com", retry_after=30.5)
        assert "http://x.com" in str(e)
        assert "retry_after" in str(e)

    def test_retry_after_none(self):
        e = AntiCrawlError()
        assert e.retry_after is None

    def test_inheritance(self):
        assert issubclass(AntiCrawlError, NovelDownloaderError)
        assert issubclass(NetworkError, NovelDownloaderError)
        assert issubclass(StorageError, NovelDownloaderError)
