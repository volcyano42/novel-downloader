"""七猫 browser 模式 - 搜索�?""

from .._common import _log, parse_search_result
from novelbase.models.novel import SearchResult


def search(query: str, engine, **kwargs) -> list[SearchResult]:
    _log.debug("七猫搜索: ref=%s", query)
    search_url = f"https://www.qimao.com/search/index/?keyword={query}"
    html = engine.fetch_text(url=search_url, **kwargs)
    return list(parse_search_result(html))
