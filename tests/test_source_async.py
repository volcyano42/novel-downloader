"""fanqie 书源 async 化契约测试：能力函数是 async、图片下载归 engine.async_fetch_images。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from novelbase.models.novel import Chapter

# 最小 HTML 样例：必须含 window.__INITIAL_STATE__ 标记（extract_json 依赖），
# `)()` 是 extract_json 的结束锚点。
_PLAIN_HTML = (
    '<div class="muye-reader-content noselect"><p>正文</p></div>'
    '<script>window.__INITIAL_STATE__='
    '{"reader":{"chapterData":{"chapterWordNumber":123}}};X)()</script>'
)

_IMG_HTML = (
    '<div class="muye-reader-content noselect">'
    "<p>第一段</p>"
    '<p class="picture"><img src="http://img.example.com/a.jpg"/></p>'
    '<p class="pictureDesc" group-id="1">图注</p>'
    "<p>第二段</p>"
    "</div>"
    "<script>window.__INITIAL_STATE__="
    '{"reader":{"chapterData":{"chapterWordNumber":999}}};X)()</script>'
)

_NOVEL_HTML = (
    '<div class="book-info">'
    '<meta property="og:image" content="http://cover.example.com/c.jpg"/>'
    '<h1 class="info-name">书名</h1>'
    '<span class="author-name">作者</span>'
    "</div>"
    "<script>window.__INITIAL_STATE__="
    '{"page":{"bookId":"7123456789012345678","bookName":"书名",'
    '"author":"作者","categoryV2":"[]","creationStatus":2,'
    '"wordNumber":"123456","abstract":"简介",'
    '"thumbUri":"http://cover.example.com/c.jpg",'
    '"chapterListWithVolume":[[]]}};X)()</script>'
)


def _chapter() -> Chapter:
    return Chapter(
        id="7123456789012345678",
        url="https://fanqienovel.com/reader/7123456789012345678",
        novel_id="fanqie_7123456789012345678",
        title="第一章",
        order=1,
    )


# ═══════════════════════════════════════════════════════════
# 能力函数 async 化
# ═══════════════════════════════════════════════════════════

_FANQIE_CAP_MODULES = {
    "requests": "novelbase.sources.fanqie.requests",
    "browser": "novelbase.sources.fanqie.browser",
    "oiapi": "novelbase.sources.fanqie.api.oiapi",
    "rain": "novelbase.sources.fanqie.api.rain",
}


class TestFanqieCapabilitiesAreAsync:
    """fanqie 四个 mode/variant 的四个能力函数全部 async def。"""

    def test_chapter_content_is_async(self):
        import importlib
        for variant, pkg in _FANQIE_CAP_MODULES.items():
            mod = importlib.import_module(f"{pkg}.chapter_content")
            assert asyncio.iscoroutinefunction(mod.chapter_content), (
                f"fanqie/{variant}/chapter_content 不是 async 函数"
            )

    def test_chapter_list_is_async(self):
        import importlib
        for variant, pkg in _FANQIE_CAP_MODULES.items():
            mod = importlib.import_module(f"{pkg}.chapter_list")
            assert asyncio.iscoroutinefunction(mod.chapter_list), (
                f"fanqie/{variant}/chapter_list 不是 async 函数"
            )

    def test_novel_info_is_async(self):
        import importlib
        for variant, pkg in _FANQIE_CAP_MODULES.items():
            mod = importlib.import_module(f"{pkg}.novel_info")
            assert asyncio.iscoroutinefunction(mod.novel_info), (
                f"fanqie/{variant}/novel_info 不是 async 函数"
            )

    def test_search_is_async(self):
        import importlib
        for variant, pkg in _FANQIE_CAP_MODULES.items():
            mod = importlib.import_module(f"{pkg}.search")
            assert asyncio.iscoroutinefunction(mod.search), (
                f"fanqie/{variant}/search 不是 async 函数"
            )


# ═══════════════════════════════════════════════════════════
# parse_chapter_content 纯函数化（5a）
# ═══════════════════════════════════════════════════════════


class TestParseChapterContentReturnsTuple:
    """parse_chapter_content 返回 (Chapter, img_urls)，不下载字节。"""

    def test_returns_chapter_and_empty_urls(self):
        from novelbase.sources.fanqie._common import parse_chapter_content
        ch = _chapter()
        chapter, img_urls = parse_chapter_content(_PLAIN_HTML, ch)
        assert chapter is ch
        assert chapter.content == "正文"
        assert chapter.count == 123
        assert isinstance(img_urls, list)
        assert img_urls == []
        assert chapter.images == ()

    def test_collects_img_urls_without_bytes(self):
        from novelbase.sources.fanqie._common import parse_chapter_content
        ch = _chapter()
        chapter, img_urls = parse_chapter_content(_IMG_HTML, ch)
        assert len(img_urls) == 1
        assert img_urls[0]["url"] == "http://img.example.com/a.jpg"
        assert img_urls[0]["alt"] == "图注"
        assert img_urls[0]["insert"] == len("第一段")
        # 纯函数：不产生 Illustration、不下载字节
        assert chapter.images == ()
        assert all("raw_data" not in i for i in img_urls)


# ═══════════════════════════════════════════════════════════
# 能力函数：图片下载走 engine.async_fetch_images（5b）
# ═══════════════════════════════════════════════════════════


class TestFanqieImagesViaEngine:
    """chapter_content / novel_info 经 engine.async_fetch_images 下载图片。"""

    def test_chapter_content_assembles_illustrations_via_engine(self):
        from importlib import import_module
        mod = import_module("novelbase.sources.fanqie.requests.chapter_content")
        engine = MagicMock()
        engine.async_fetch_text = AsyncMock(return_value=_IMG_HTML)
        engine.async_fetch_images = AsyncMock(return_value=[b"\x89PNG\r\n\x1a\nfake"])

        result = asyncio.run(mod.chapter_content(_chapter(), engine))

        engine.async_fetch_text.assert_awaited_once()
        engine.async_fetch_images.assert_awaited_once_with(["http://img.example.com/a.jpg"])
        assert len(result.images) == 1
        img = result.images[0]
        assert img.raw_data == b"\x89PNG\r\n\x1a\nfake"
        assert img.url == "http://img.example.com/a.jpg"
        assert img.alt == "图注"
        assert img.insert == len("第一段")

    def test_novel_info_downloads_cover_via_engine(self):
        from importlib import import_module
        mod = import_module("novelbase.sources.fanqie.requests.novel_info")
        engine = MagicMock()
        engine.async_fetch_text = AsyncMock(return_value=_NOVEL_HTML)
        engine.async_fetch_images = AsyncMock(return_value=[b"cover-bytes"])

        novel = asyncio.run(
            mod.novel_info("https://fanqienovel.com/page/7123456789012345678", engine)
        )

        engine.async_fetch_images.assert_awaited_once_with(["http://cover.example.com/c.jpg"])
        assert novel.title == "书名"
        assert novel.cover is not None
        assert novel.cover.raw_data == b"cover-bytes"
        assert novel.cover.url == "http://cover.example.com/c.jpg"
