"""书籍详情（番茄 app API，directory/list 的 book_info）。

接口：GET https://api.fanqiesdk.com/api/novel/book/directory/list/v1
参数：公共参数链 + book_id
响应 data.book_info 含书籍完整元数据（书名/作者/简介/字数/封面/连载状态等）。
实测（2026-08-23）：带 X-Gorgon 签名可用。
"""
from novelbase.core.exceptions import NovelNotFoundError
from novelbase.models.novel import Illustration, Novel
from ._client import HOST_SDK, common_params, signed_get_json
from ..._common import standardize_id


async def novel_info(url: str, engine, **kwargs) -> Novel:
    book_id = standardize_id(url)
    params = common_params(engine)
    params["book_id"] = book_id
    data = await signed_get_json(f"{HOST_SDK}/api/novel/book/directory/list/v1", params)

    info = (data.get("data") or {}).get("book_info") or {}
    if not info:
        raise NovelNotFoundError(f"appapi: empty book_info for book_id={book_id}")

    book_name = info.get("book_name")
    if not book_name:
        raise NovelNotFoundError(f"appapi: missing book_name for book_id={book_id}")

    serial = info.get("serial_count") or 0
    try:
        serial = int(serial)
    except (TypeError, ValueError):
        serial = 0

    count = info.get("word_number")
    try:
        count = int(count)
    except (TypeError, ValueError):
        count = None

    status = info.get("creation_status")
    status_label = "连载中" if str(status) == "1" else "已完结"
    category = info.get("category") or ""
    tags = [t.strip() for t in str(category).split(",") if t.strip()]
    tags.insert(0, status_label) if status_label not in tags else None

    cover_url = info.get("thumb_url") or None
    cover = Illustration(raw_data=b"", alt=book_name, url=cover_url) if cover_url else None

    return Novel(
        url=f"https://fanqienovel.com/page/{book_id}",
        title=book_name,
        author=info.get("author"),
        serial=serial,
        tags=tuple(tags) if tags else None,
        description=info.get("abstract"),
        count=count,
        cover=cover,
    )
