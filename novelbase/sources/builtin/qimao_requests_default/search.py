"""qimao requests - search."""

import logging

from bs4 import BeautifulSoup

from novelbase.models.novel import SearchResult

_log = logging.getLogger("novelbase.sources.qimao")

def parse_search_result(html: str):
    soup = BeautifulSoup(html, "lxml")
    results: list = []
    items = soup.select("ul.search-book-list li.qm-cover-text-item")
    if not items:
        return ()
    for item in items:
        title_a = item.select_one(".text-content .s-tit a")
        if not title_a:
            continue
        title = title_a.get_text(strip=True)
        url = title_a.get("href", "")
        author = ""
        author_a = item.select_one(".text-bottom-row .item-wrap .link")
        if author_a:
            author = author_a.get_text(strip=True)
        desc_span = item.select_one(".text-content .s-desc")
        description = desc_span.get_text(strip=True) if desc_span else ""
        cover_img = item.select_one("img.book-cover-src, .cover-img img, img.cover")
        cover_url = cover_img.get("src") or cover_img.get("data-src") or "" if cover_img else ""
        results.append(SearchResult(
            title=title, author=author, url=url, description=description,
            cover_url=cover_url or None,
        ))
    return tuple(results)

async def search(query: str, engine, **kwargs) -> list[SearchResult]:
    page = kwargs.pop("page", 1)
    _log.debug("qimao search: ref=%s page=%s", query, page)
    if page > 1:
        search_url = f"https://www.qimao.com/search/index/?keyword={query}&page={page}"
    else:
        search_url = f"https://www.qimao.com/search/index/?keyword={query}"
    html = await engine.async_fetch_text(url=search_url, **kwargs)
    return list(parse_search_result(html))
