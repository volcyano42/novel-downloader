import json

from bs4 import BeautifulSoup

from novelbase.models.novel import SearchResult


def parse_search_result(html: str) -> tuple[SearchResult, ...]:
    soup = BeautifulSoup(html, 'lxml')
    script_list = soup.select('script')
    results: list[SearchResult] = []
    for script in script_list:
        if "g_data.listInfo=" in str(script):
            script_str = script.get_text()
            start_index = script_str.find('g_data.listInfo=') + len('g_data.listInfo=')
            end_index = script_str.find(",g_data.page=")
            json_str = script_str[start_index:end_index]
            json_data = json.loads(json_str)
            for book_data in json_data:
                book_name = book_data.get('bookName')
                description = book_data.get('bookInfo')
                book_url = "https:" + book_data.get('bookUrl')
                author_name = book_data.get('authorName')
                results.append(SearchResult(
                    title=book_name,
                    author=author_name,
                    url=book_url,
                    description=description,
                    cover_url=("https:" + img) if (img := book_data.get('imgUrl')) and img.startswith("//") else (img or None),
                ))
    return tuple(results)

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
