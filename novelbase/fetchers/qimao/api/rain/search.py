"""qimao API (Rain) - search."""

from box import Box

from ..._common import _api_url, _log
from novelbase.models.novel import SearchResult


def search(query: str, engine, **kwargs) -> list[SearchResult]:
    page = kwargs.pop("page", 1)
    results: list[SearchResult] = []
    offset = (page - 1) * 10
    url = _api_url(engine, type=1, wd=query, page=offset)
    content = engine.fetch_json(url, **kwargs)

    code = content.get("code")
    if code is not None and code != 0 and str(code) != "0":
        _log.warning("qimao Rain API search error: code=%s msg=%s",
                     content.get("code"), content.get("message", ""))
        return []

    books = None
    data = content.get("data")
    if isinstance(data, dict):
        books = data.get("books")
    if not books and isinstance(data, list):
        books = data

    if not books or not isinstance(books, list):
        return []

    for item in books:
        book_name = item.get("original_title") or item.get("book_name") or ""
        book_id = str(item.get("id") or item.get("book_id") or "")
        author = item.get("original_author") or item.get("author") or ""
        description = item.get("intro") or item.get("abstract") or ""

        book_url = f"https://www.qimao.com/shuku/{book_id}/"

        results.append(SearchResult(
            title=book_name,
            author=author,
            url=book_url,
            description=description,
            cover_url=item.get("cover") or item.get("image_link") or None,
            extra=Box(rating=item.get('score'))
        ))
    return results
