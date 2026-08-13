import httpx

from .._common import parse_search_result


def search(query: str, engine, **kwargs) -> list:
    search_url = (
        f"https://api-lf.fanqiesdk.com/api/novel/channel/homepage/search/search/v1/"
        f"?aid=1967&offset=0&q={query}"
    )
    try:
        data = httpx.get(search_url, follow_redirects=True).json()
    except Exception:
        return []
    return list(parse_search_result(data=data))
