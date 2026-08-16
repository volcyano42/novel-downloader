import asyncio

from .._common import parse_search_result
from novelbase.models.novel import SearchResult


async def search(query: str, engine, **kwargs) -> list[SearchResult]:
    page = kwargs.pop("page", 1)
    search_url = f"https://www.qidian.com/so/{query}.html"

    if page > 1:
        # Playwright 原生 async：直接 await，不再 to_thread
        browser_page = await engine.new_page()
        try:
            await browser_page.goto(search_url)
            next_page_xpath = f"/html/body/div[1]/div[3]/div[1]/div[4]/div[2]/div/div/ul/li[{page}]"
            await browser_page.locator(f"xpath={next_page_xpath}").click()
            html = await browser_page.content()
        finally:
            await browser_page.close()
    else:
        html = await engine.async_fetch_text(search_url, **kwargs)

    return list(parse_search_result(html))
