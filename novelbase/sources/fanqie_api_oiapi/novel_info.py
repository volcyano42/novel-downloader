import re

from novelbase.core.exceptions import NovelNotFoundError
from novelbase.models.novel import Novel, Illustration, Chapter


def standardize_id(ref: str | Novel | Chapter) -> str:

    if isinstance(ref, Novel):
        ref = ref.url
    if isinstance(ref, Chapter):
        ref = ref.url
    if isinstance(ref, str):
        if re.match(r"^\d{19}$", ref):
            return ref
        if search := re.search(r"book_id=(\d{19})", ref):
            return search.group(1)
        if search := re.search(r"\d{19}", ref):
            return search.group(0)
    raise ValueError(f"ref {ref} Non conformance")


async def novel_info(url: str, engine, **kwargs):
    novel_id = standardize_id(url)
    post_data = {
        "id": novel_id,
        "key": engine.options.key,
        "method": "ids",
        "type": "json"
    }
    json_data = await engine.async_fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data, **kwargs)

    # 契约实测 2026-09-26：method=ids 直接返回
    # dict{thumb,id,title,author,serial,word_number,read_count,docs}
    data = json_data.get('data')
    if not data or json_data.get('code') not in (1, "1"):
        raise NovelNotFoundError()

    url = f"https://fanqienovel.com/page/{data.get('id')}"
    novel_id = str(data.get('id'))

    book_cover_url = data.get('thumb')
    book_cover_data = (await engine.async_fetch_images([book_cover_url]))[0] if book_cover_url else b""
    name = data.get('title')
    novel_image = Illustration(raw_data=book_cover_data, alt=name, url=book_cover_url)
    author = data.get('author')
    word_number: int = int(data.get('word_number') or 0)

    # serial 直接取自 ids 响应（不再二次请求 chapters，后者对扁平 list 求和会得垃圾）
    serial = int(data.get('serial') or 0)

    novel = Novel(url=url,
                  id=f"fanqie_{novel_id}",
                  title=name,
                  serial=serial,
                  author=author,
                  count=word_number,
                  description=data.get('docs'),
                  cover=novel_image
                  )
    return novel
