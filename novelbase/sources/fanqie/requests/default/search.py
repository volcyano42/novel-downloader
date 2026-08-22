from ..._common import parse_search_result


async def search(query: str, engine, **kwargs) -> list:
    search_url = (
        f"https://api-lf.fanqiesdk.com/api/novel/channel/homepage/search/search/v1/"
        f"?aid=1967&offset=0&q={query}"
    )
    try:
        data = await engine.async_fetch_json(search_url, **kwargs)
    except Exception:
        return []
    return list(parse_search_result(data=data))
