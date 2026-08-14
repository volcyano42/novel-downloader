from novelbase.core.exceptions import NovelNotFoundError
from novelbase.models.novel import Novel, Illustration

from ..._common import standardize_id


async def novel_info(url: str, engine, **kwargs):
    novel_id = standardize_id(url)
    post_data = {
        "id": novel_id,
        "key": engine.options.key,
        "method": "detail",
        "type": "json"
    }
    json_data = await engine.async_fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data, **kwargs)

    data = json_data.get('data')
    if not data:
        raise NovelNotFoundError()

    url = f"https://fanqienovel.com/page/{data.get('id')}"
    novel_id = str(data.get('id'))

    book_cover_url = data.get('cover')
    book_cover_data = (await engine.async_fetch_images([book_cover_url]))[0] if book_cover_url else b""
    name = data.get('title')
    novel_image = Illustration(raw_data=book_cover_data, alt=name, url=book_cover_url)
    author = data.get('author')
    word_number: int = int(data.get('word_number', 0))

    # 通过获取章节列表获取 serial
    serial_post_data = {
        "id": novel_id,
        "key": engine.options.key,
        "method": "chapters",
        "type": "json"
    }
    chapters_json = await engine.async_fetch_json(url="https://oiapi.net/api/FqRead", post_data=serial_post_data, **kwargs)
    chapter_items_volume = chapters_json.get('data', [])
    serial = sum(len(vol) for vol in chapter_items_volume)

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
