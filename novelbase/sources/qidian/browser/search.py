from .._common import parse_search_result
from novelbase.models.novel import SearchResult


def search(query: str, engine, **kwargs) -> list[SearchResult]:
    page = kwargs.pop("page", 1)
    search_url = f"https://www.qidian.com/so/{query}.html"

    if page > 1:
        browser_page = engine.new_page()
        browser_page.get(search_url)
        next_page_xpath = f"/html/body/div[1]/div[3]/div[1]/div[4]/div[2]/div/div/ul/li[{page}]"
        browser_page.ele(f"xpath:{next_page_xpath}").click()
        html = browser_page.html
    else:
        html = engine.fetch_text(search_url, **kwargs)

    return list(parse_search_result(html))
