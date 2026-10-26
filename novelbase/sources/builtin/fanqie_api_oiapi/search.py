from novelbase.models.novel import SearchResult


async def search(query: str, engine, **kwargs) -> list:
    page = kwargs.pop("page", 1)
    results: list[SearchResult] = []
    post_data = {
        "page": page,
        "keyword": query,
        "key": engine.options.key,
        "method": "search",
        "type": "json"
    }
    content = await engine.async_fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data, **kwargs)

    if content.get("data"):
        book_info_list = content.get("data")
        for book_info in book_info_list:
            book_id = book_info.get("id")
            book_url = f"https://fanqienovel.com/page/{book_id}"
            book_name = book_info.get("title")
            author = book_info.get("author")
            description = book_info.get("docs")

            results.append(SearchResult(
                title=book_name,
                author=author,
                url=book_url,
                description=description,
                cover_url=book_info.get("thumb") or None,
            ))

    return results
