from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter, Chapters

from ..._common import standardize_id


async def chapter_list(url: str, engine, **kwargs) -> list:
    novel_id = standardize_id(url)
    post_data = {
        "id": novel_id,
        "key": engine.options.key,
        "method": "chapters",
        "type": "json"
    }
    json_data = await engine.async_fetch_json(url="https://oiapi.net/api/FqRead", post_data=post_data, **kwargs)

    chapter_items_volume = json_data.get('data')
    if not chapter_items_volume:
        raise ChapterNotFoundError("OIAPI returned empty chapter list")
    results = []

    for chapter_items in chapter_items_volume:
        for chapter_item in chapter_items:
            chapter_id: int = chapter_item.get("chapter_id")
            chapter_url = "https://fanqienovel.com/reader/" + str(chapter_id)
            title: str = chapter_item["title"]
            order: int = chapter_item["index"]
            timestamp: float = chapter_item["time"]
            volume_name = chapter_item["volume_name"]
            chapter = Chapter(
                title=title,
                url=chapter_url,
                id=str(chapter_id),
                order=order,
                novel_id=standardize_id(url),
                volume=volume_name,
                time=timestamp
            )
            results.append(chapter)

    return Chapters(results)
