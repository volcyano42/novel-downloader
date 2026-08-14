import asyncio

from .._common import parse_search_result
from novelbase.models.novel import SearchResult


async def search(query: str, engine, **kwargs) -> list[SearchResult]:
    page = kwargs.pop("page", 1)
    search_url = f"https://www.qidian.com/so/{query}.html"

    if page > 1:
        # DrissionPage 是同步库，整段页面前进操作放到线程池
        def _sync():
            browser_page = engine.new_page()
            try:
                browser_page.get(search_url)
                next_page_xpath = f"/html/body/div[1]/div[3]/div[1]/div[4]/div[2]/div/div/ul/li[{page}]"
                browser_page.ele(f"xpath:{next_page_xpath}").click()
                return browser_page.html
            finally:
                browser_page.close()

        html = await asyncio.to_thread(_sync)
    else:
        html = await engine.async_fetch_text(search_url, **kwargs)

    return list(parse_search_result(html))
