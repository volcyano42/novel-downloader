"""qimao requests - search."""

from novelbase.models.novel import SearchResult
from ..._common import _log, parse_search_result


async def search(query: str, engine, **kwargs) -> list[SearchResult]:
    page = kwargs.pop("page", 1)
    _log.debug("qimao search: ref=%s page=%s", query, page)
    if page > 1:
        search_url = f"https://www.qimao.com/search/index/?keyword={query}&page={page}"
    else:
        search_url = f"https://www.qimao.com/search/index/?keyword={query}"
    html = await engine.async_fetch_text(url=search_url, **kwargs)
    return list(parse_search_result(html))
