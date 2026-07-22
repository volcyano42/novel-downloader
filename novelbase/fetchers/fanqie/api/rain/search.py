from box.box import Box

from novelbase.models.novel import SearchResult

from ._helpers import _api_url


def search(query: str, engine, **kwargs) -> list:
    page = kwargs.pop("page", 1)
    results: list[SearchResult] = []
    offset = (page - 1) * 10
    url = _api_url(engine, type=1, keywords=query, page=offset)
    content = engine.fetch_json(url, **kwargs)

    if content.get("code") != 0 and str(content.get("code")) != "0":
        return []

    books = None
    if "search_tabs" in content:
        for tab in content["search_tabs"]:
            if tab.get("data") is not None:
                books = tab["data"]
                break
    if books is None:
        books = content.get("data")

    if not books or not isinstance(books, list):
        return []

    for item in books:
        if "book_data" in item and isinstance(item["book_data"], list) and len(item["book_data"]) > 0:
            book = item["book_data"][0]
        else:
            book = item

        book_id = book.get("book_id")
        book_url = f"https://fanqienovel.com/page/{book_id}"
        book_name = book.get("book_name")
        author = book.get("author")
        description = book.get("abstract")

        meta = Box(rating=book.get('score'))

        results.append(SearchResult(
            title=book_name,
            author=author,
            url=book_url,
            description=description,
            meta=meta
        ))
    return results
