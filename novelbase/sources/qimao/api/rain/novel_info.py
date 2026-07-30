"""qimao API (Rain) - fetch novel info."""

from ..._common import _api_url, standardize_id
from novelbase.core.exceptions import NovelNotFoundError
from novelbase.models.novel import Novel, Illustration
import requests
from box import Box


def novel_info(url: str, engine, **kwargs):
    novel_id = standardize_id(url)
    api_url = _api_url(engine, type=2, id=novel_id)
    json_data = engine.fetch_json(api_url, **kwargs)

    code = json_data.get("code")
    if code is not None and code != 0 and str(code) != "0":
        raise NovelNotFoundError()

    book = json_data.get("data", {}).get("book")
    if not book:
        raise NovelNotFoundError()

    book_url = f"https://www.qimao.com/shuku/{novel_id}/"
    name = book.get("title") or ""

    author = book.get("author") or ""

    serial = int(book.get("chapters", 0))
    word_number = int(book.get("words_num", 0))

    cover_url = book.get("image_link", "")
    try:
        book_cover_data = requests.get(cover_url, timeout=10).content if cover_url else b""
    except requests.RequestException:
        book_cover_data = b""
    novel_image = Illustration(raw_data=book_cover_data, alt=name, url=cover_url)

    tags: list[str] = []
    tags.append("\u5df2\u5b8c\u7ed3" if book.get("is_over") == "1" else "\u8fde\u8f7d\u4e2d")
    for key in ("category1_name", "category2_name"):
        v = book.get(key)
        if v:
            tags.append(v)

    extra = Box(rating=book.get('score'))
    novel = Novel(url=book_url,
                  id=f"qimao_{novel_id}",
                  title=name,
                  serial=serial,
                  author=author,
                  count=word_number,
                  description=book.get("intro", ""),
                  cover=novel_image,
                  tags=tuple(tags),
                  extra=extra,
                  )
    return novel
