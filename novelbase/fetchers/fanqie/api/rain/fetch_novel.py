import json

import requests
from box.box import Box

from novelbase.core.exceptions import NovelNotFoundError
from novelbase.models.novel import Novel, Illustration

from ..._common import standardize_id
from ._helpers import _api_url


def fetch_novel(url: str, engine, **kwargs):
    novel_id = standardize_id(url)
    url = _api_url(engine, type=2, bookid=novel_id)
    json_data = engine.fetch_json(url, **kwargs)

    if json_data.get("code") != 0 and str(json_data.get("code")) != "0":
        raise NovelNotFoundError()

    data = json_data.get("data")
    if not data:
        raise NovelNotFoundError()

    book_url = f"https://fanqienovel.com/page/{data.get('book_id')}"
    name = data.get("book_name")

    author = ""
    author_info = data.get("author_info")
    if author_info and isinstance(author_info, dict):
        author = author_info.get("user_name", "")
    if not author:
        try:
            original_authors = json.loads(data.get("original_authors", "[]"))
            if original_authors:
                author = original_authors[0].get("AuthorName", "")
        except (json.JSONDecodeError, IndexError):
            pass

    serial = int(data.get("serial_count", 0))
    word_number = int(data.get("word_number", 0))

    cover_url = data.get("thumb_url", "")
    try:
        book_cover_data = requests.get(cover_url, timeout=10).content if cover_url else b""
    except requests.RequestException:
        book_cover_data = b""
    novel_image = Illustration(raw_data=book_cover_data, alt=name, url=cover_url)

    tags: list[str] = []
    status = data.get("status", "0")
    tags.append("\u8fde\u8f7d\u4e2d" if status == "0" else "\u5df2\u5b8c\u7ed3")
    try:
        category_v2 = json.loads(data.get("category_v2", "[]"))
        for cat in category_v2:
            cat_name = cat.get("Name")
            if cat_name:
                tags.append(cat_name)
    except json.JSONDecodeError:
        pass

    meta = Box(rating=data.get("score"))

    novel = Novel(url=book_url,
                  id=novel_id,
                  title=name,
                  serial=serial,
                  author=author,
                  count=word_number,
                  description=data.get("abstract", ""),
                  cover=novel_image,
                  tags=tuple(tags),
                  meta=meta
                  )
    return novel
