import asyncio
from importlib import import_module

# 注：browser/__init__.py 的 `from .search import search` 会让包属性 search
# 被函数覆盖，`from ...browser import search` 拿到的是函数而非子模块，
# 故用 import_module 直接加载子模块。
qidian_search = import_module("novelbase.sources.qidian_browser_default.search")
qimao_chapter_list = import_module("novelbase.sources.qimao_browser_default.chapter_list")


class FakePage:
    """mock Playwright page：记录交互调用。"""

    def __init__(self, html="<html></html>"):
        self.html = html
        self.gotos = []
        self.clicks = []
        self.waits = []
        self.counts = []
        self.closed = False

    async def goto(self, url, timeout=None):
        self.gotos.append(url)

    async def content(self):
        return self.html

    def locator(self, selector):
        self.last_selector = selector
        return self

    async def click(self):
        self.clicks.append(self.last_selector)

    async def count(self):
        self.counts.append(self.last_selector)
        return 1  # 默认存在元素

    async def wait_for_timeout(self, ms):
        self.waits.append(ms)

    async def close(self):
        self.closed = True


class FakeEngine:
    """最小 engine：只实现书源用到的 new_page 和 async_fetch_text。"""

    def __init__(self, page):
        self._page = page
        self.new_page_calls = 0
        self.async_fetch_urls = []

    async def new_page(self):
        self.new_page_calls += 1
        return self._page

    async def async_fetch_text(self, url, skip_delay=False, **kwargs):
        self.async_fetch_urls.append(url)
        return self._page.html


def test_qidian_search_page1_uses_async_fetch_text():
    """page=1 不 new_page，直接 async_fetch_text。"""
    page = FakePage("<html>r1</html>")
    engine = FakeEngine(page)
    result = asyncio.run(qidian_search.search("斗罗", engine, page=1))
    assert engine.new_page_calls == 0  # 不 new_page
    assert engine.async_fetch_urls != []  # 走了 async_fetch_text
    assert isinstance(result, list)  # parse 对空 html 返回空列表


def test_qidian_search_page2_uses_new_page_and_click():
    """page>1 用 new_page + locator(click)，不再 to_thread。"""
    page = FakePage("<html>r2</html>")
    engine = FakeEngine(page)
    result = asyncio.run(qidian_search.search("斗罗", engine, page=2))
    assert engine.new_page_calls == 1
    assert page.clicks != []  # 点击了下一页
    assert page.closed is True
    assert isinstance(result, list)


def test_qimao_chapter_list_clicks_catalog_tab():
    """qimao 点击 .tab-inner 触发目录加载，不再 to_thread。"""
    page = FakePage("<html>catalog</html>")
    engine = FakeEngine(page)
    result = asyncio.run(qimao_chapter_list.chapter_list(
        "https://www.qimao.com/shuku/12345/", engine))
    assert engine.new_page_calls == 1
    assert page.clicks == [".tab-inner"]
    assert page.waits == [3000]
    assert page.closed is True
    assert isinstance(result, list)
