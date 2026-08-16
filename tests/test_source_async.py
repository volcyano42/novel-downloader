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


# ═══════════════════════════════════════════════════════════
# Task 6: qidian / qimao / 92xs 能力函数 async 化
# ═══════════════════════════════════════════════════════════

_QIDIAN_NOVEL_HTML = (
    '<html><head><title>书名</title></head><body>'
    '<h1 id="bookName">书名</h1>'
    '<p class="book-desc">简介</p>'
    '<div class="author-information"><a class="writer-name">作者</a>'
    '<p class="book-attribute">玄幻·都市</p></div>'
    '<p class="count"><em>12万</em></p>'
    '<p id="book-intro-detail">详细介绍</p>'
    '<a id="bookImg"><img src="//cover.qidian.com/novel.jpg"/></a>'
    '<div class="catalog-all"><li>a</li></div>'
    "</body></html>"
)

_QIMAO_RAIN_NOVEL_JSON = {
    "code": 0,
    "data": {
        "book": {
            "title": "书名",
            "author": "作者",
            "chapters": "10",
            "words_num": "12345",
            "image_link": "http://img.qimao.com/cover.jpg",
            "intro": "简介",
            "is_over": "0",
            "category1_name": "都市",
            "score": "8.5",
        }
    },
}

_QIMAO_CHAPTER_LIST_HTML = (
    '<div class="qm-book-catalog-list-content">'
    '<li><a href="/shuku/123-456/"><span class="txt">第一章</span></a></li>'
    '<li><a href="/shuku/123-457/"><span class="txt">第二章</span></a></li>'
    "</div>"
)

_92XS_NOVEL_HTML = (
    '<div class="d_title"><h1>书名</h1></div>'
    '<div class="p_author">作者：张三</div>'
    '<div id="bookintro"><p>简介</p></div>'
    '<div id="count"><span>都市小说</span><span>123456</span></div>'
    '<div id="bookimg"><img src="/images/cover.jpg"/></div>'
)

_92XS_SEARCH_HTML = (
    '<table id="author"><tr><td>书名</td><td>最新章节</td><td>作者</td><td>字数</td></tr>'
    '<tr><td><a href="/book/9999.html">书名</a></td>'
    "<td>最新章节</td><td>作者</td><td>100万</td></tr></table>"
)


class TestQidianQimao92xsCapabilitiesAreAsync:
    """qidian/qimao/92xs 各 mode/variant 的四个能力函数全部 async def。"""

    _CAP_MODULES = {
        "qidian_requests": "novelbase.sources.qidian.requests",
        "qidian_browser": "novelbase.sources.qidian.browser",
        "qimao_requests": "novelbase.sources.qimao.requests",
        "qimao_browser": "novelbase.sources.qimao.browser",
        "qimao_rain": "novelbase.sources.qimao.api.rain",
        "92xs_requests": "novelbase.sources.92xs.requests",
    }

    def test_all_capabilities_are_async(self):
        import importlib
        for label, pkg in self._CAP_MODULES.items():
            for cap in ("search", "chapter_list", "chapter_content", "novel_info"):
                mod = importlib.import_module(f"{pkg}.{cap}")
                assert asyncio.iscoroutinefunction(getattr(mod, cap)), (
                    f"{label}/{cap} 不是 async 函数"
                )


class TestQidianCoverViaEngine:
    """qidian novel_info 封面下载走 engine.async_fetch_images。"""

    def test_requests_novel_info_downloads_cover_via_engine(self):
        from importlib import import_module
        mod = import_module("novelbase.sources.qidian.requests.novel_info")
        engine = MagicMock()
        engine.async_fetch_text = AsyncMock(return_value=_QIDIAN_NOVEL_HTML)
        engine.async_fetch_images = AsyncMock(return_value=[b"cover-bytes"])

        novel = asyncio.run(
            mod.novel_info("https://www.qidian.com/book/1234567890/", engine)
        )

        engine.async_fetch_images.assert_awaited_once_with(
            ["https://cover.qidian.com/novel.jpg"]
        )
        assert novel.title == "书名"
        assert novel.cover is not None
        assert novel.cover.raw_data == b"cover-bytes"
        assert novel.cover.url == "https://cover.qidian.com/novel.jpg"


class TestQimaoCoverAndBrowserChapterList:
    """qimao rain novel_info 封面走 engine；browser chapter_list 走 Playwright new_page。"""

    def test_rain_novel_info_downloads_cover_via_engine(self):
        from importlib import import_module
        mod = import_module("novelbase.sources.qimao.api.rain.novel_info")
        engine = MagicMock()
        engine.options.key = "test-key"
        engine.async_fetch_json = AsyncMock(return_value=_QIMAO_RAIN_NOVEL_JSON)
        engine.async_fetch_images = AsyncMock(return_value=[b"cover-bytes"])

        novel = asyncio.run(
            mod.novel_info("https://www.qimao.com/shuku/123/", engine)
        )

        engine.async_fetch_images.assert_awaited_once_with(
            ["http://img.qimao.com/cover.jpg"]
        )
        assert novel.title == "书名"
        assert novel.cover.raw_data == b"cover-bytes"
        assert novel.cover.url == "http://img.qimao.com/cover.jpg"

    def test_browser_chapter_list_clicks_catalog_tab(self):
        from importlib import import_module
        mod = import_module("novelbase.sources.qimao.browser.chapter_list")
        engine = MagicMock()
        page = MagicMock()
        page.goto = AsyncMock()
        page.content = AsyncMock(return_value=_QIMAO_CHAPTER_LIST_HTML)
        page.locator.return_value.count = AsyncMock(return_value=1)
        page.locator.return_value.click = AsyncMock()
        page.wait_for_timeout = AsyncMock()
        page.close = AsyncMock()
        engine.new_page = AsyncMock(return_value=page)

        chapters = asyncio.run(
            mod.chapter_list("https://www.qimao.com/shuku/123-456/", engine)
        )

        engine.new_page.assert_awaited_once()
        page.goto.assert_awaited_once()
        page.locator.assert_called_once_with(".tab-inner")
        page.wait_for_timeout.assert_awaited_once_with(3000)
        page.close.assert_awaited_once()
        assert len(chapters) == 2
        assert chapters[0].title == "第一章"


class Test92xsCapabilities:
    """92xs search 走 engine async client POST；novel_info 封面归 engine。"""

    def test_search_posts_to_search_endpoint(self):
        from importlib import import_module
        mod = import_module("novelbase.sources.92xs.requests.search")
        engine = MagicMock()
        engine.async_fetch_text = AsyncMock(return_value=_92XS_SEARCH_HTML)

        results = asyncio.run(mod.search("书名", engine))

        engine.async_fetch_text.assert_awaited_once_with(
            "http://www.92xs.info/modules/article/search.php",
            post_data={
                "searchtype": "articlename",
                "searchkey": "书名",
                "searchtype2": "author",
            },
            skip_delay=False,
        )
        assert len(results) == 1
        assert results[0].title == "书名"
        assert results[0].url == "http://www.92xs.info/book/9999.html"

    def test_search_returns_empty_on_http_error(self):
        from importlib import import_module
        mod = import_module("novelbase.sources.92xs.requests.search")
        from novelbase.core.exceptions import NetworkError
        engine = MagicMock()
        engine.async_fetch_text = AsyncMock(side_effect=NetworkError("boom"))

        results = asyncio.run(mod.search("书名", engine))

        assert results == []

    def test_novel_info_downloads_cover_via_engine(self):
        from importlib import import_module
        mod = import_module("novelbase.sources.92xs.requests.novel_info")
        engine = MagicMock()
        engine.async_fetch_text = AsyncMock(return_value=_92XS_NOVEL_HTML)
        engine.async_fetch_images = AsyncMock(return_value=[b"cover-bytes"])

        novel = asyncio.run(
            mod.novel_info("http://www.92xs.info/book/9999.html", engine)
        )

        engine.async_fetch_images.assert_awaited_once_with(
            ["http://www.92xs.info/images/cover.jpg"]
        )
        assert novel.title == "书名"
        assert novel.author == "张三"
        assert novel.id == "92xs_9999"
        assert novel.cover.raw_data == b"cover-bytes"
