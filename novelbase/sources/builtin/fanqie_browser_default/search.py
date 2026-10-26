from typing import Any

from novelbase.models.novel import SearchResult


def parse_search_result(data: dict[str, Any]) -> tuple[SearchResult, ...]:
    results: list[SearchResult] = []
    if data.get("data") and data["data"].get("ret_data"):
        for book_info in data["data"]["ret_data"]:
            book_id = book_info.get("book_id")
            book_url = f"https://fanqienovel.com/page/{book_id}"
            book_name = book_info.get("title")
            author = book_info.get("author")
            description = book_info.get("abstract")

            results.append(SearchResult(
                title=book_name,
                author=author,
                url=book_url,
                description=description,
                cover_url=book_info.get("thumb_url") or book_info.get("thumbUri") or None,
            ))

    return tuple(results)

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
