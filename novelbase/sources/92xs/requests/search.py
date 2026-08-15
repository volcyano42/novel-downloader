"""92xs 搜索 — POST 到 /modules/article/search.php。"""
from bs4 import BeautifulSoup
from novelbase.models.novel import SearchResult
from novelbase.core.exceptions import NetworkError

SEARCH_URL = "http://www.92xs.info/modules/article/search.php"


async def search(query: str, engine, **kwargs) -> list[SearchResult]:
    """POST 搜索，解析返回的 HTML 表格。"""
    try:
        text = await engine.async_fetch_text(
            SEARCH_URL,
            post_data={
                "searchtype": "articlename",
                "searchkey": query,
                "searchtype2": "author",
            },
            skip_delay=kwargs.get("skip_delay", False),
        )
    except NetworkError:
        return []

    soup = BeautifulSoup(text, "html.parser")
    rows = soup.select("table#author tr")
    if not rows:
        return []

    results: list[SearchResult] = []
    for tr in rows[1:]:  # 跳过表头
        tds = tr.select("td")
        if len(tds) < 4:
            continue
        # td[0].odd: 书名 + 链接, td[2].odd: 作者
        a = tds[0].select_one("a")
        if not a:
            continue
        url = a.get("href", "")
        if url.startswith("/"):
            url = "http://www.92xs.info" + url

        results.append(SearchResult(
            title=tds[0].get_text(strip=True),
            author=tds[2].get_text(strip=True),
            url=url,
            description=tds[1].get_text(strip=True),      # 最新章节
            platform="92xs",
        ))

    return results
