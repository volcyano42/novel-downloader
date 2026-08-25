"""搜索（番茄 app API）。

接口：GET https://reading.snssdk.com/reading/bookapi/search/search/v1/
参数：公共参数链 + q / offset / search_id
实测（2026-08-23）：带 X-Gorgon 签名返回 {"code":0,"data":{"search_result":[...]}}。
"""
from novelbase.models.novel import SearchResult

from ._client import HOST_APP, common_params, signed_get_json

PAGE_SIZE = 10


async def search(query: str, engine, **kwargs) -> list:
    page = kwargs.pop("page", 1)
    params = common_params(engine)
    params.update({
        "q": query,
        "offset": str((page - 1) * PAGE_SIZE),
        "search_id": "",
    })
    data = await signed_get_json(f"{HOST_APP}/reading/bookapi/search/search/v1/", params)
    if data.get("code") != 0:
        return []

    results: list[SearchResult] = []
    for item in (data.get("data") or {}).get("search_result") or []:
        book_id = item.get("book_id")
        if not book_id:
            continue
        results.append(SearchResult(
            title=item.get("book_name"),
            author=item.get("author"),
            url=f"https://fanqienovel.com/page/{book_id}",
            description=item.get("abstract"),
            cover_url=item.get("thumb_url") or None,
        ))
    return results
