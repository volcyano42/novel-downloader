"""92xs 搜索 — POST 到 /modules/article/search.php。"""
import httpx
from bs4 import BeautifulSoup
from novelbase.models.novel import SearchResult
from novelbase.utils.encoding import detect_encoding

SEARCH_URL = "http://www.92xs.info/modules/article/search.php"


async def search(query: str, engine, **kwargs) -> list[SearchResult]:
    """POST 搜索，解析返回的 HTML 表格。

    92xs 是 requests 平台，engine 的 async_fetch_text 只支持 GET；
    这里用 engine 的异步客户端直接 POST（保留 POST body 语义）。
    """
    try:
        client = engine._get_async_client()
        resp = await client.post(
            SEARCH_URL,
            data={
                "searchtype": "articlename",
                "searchkey": query,
                "searchtype2": "author",
            },
            timeout=15,
            follow_redirects=True,
        )
    except httpx.HTTPError:
        return []
    # httpx 无 apparent_encoding 属性，用项目统一的编码探测
    text = resp.content.decode(detect_encoding(resp.content), errors="replace")

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
