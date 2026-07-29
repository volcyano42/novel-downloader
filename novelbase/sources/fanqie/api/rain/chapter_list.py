from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter, Chapters

from ..._common import standardize_id
from ._helpers import _api_url


def chapter_list(url: str, engine, **kwargs) -> list:
    novel_id = standardize_id(url)
    url = _api_url(engine, type=3, bookid=novel_id)
    json_data = engine.fetch_json(url, **kwargs)

    if json_data.get("code") != 0 and str(json_data.get("code")) != "0":
        raise ChapterNotFoundError(f"Rain API returned error code: {json_data.get('code')}")

    item_data_list = json_data.get("data", {}).get("item_data_list")
    if not item_data_list:
        raise ChapterNotFoundError("Rain API returned empty chapter list")

    results: list[Chapter] = []
    for idx, chapter_item in enumerate(item_data_list, start=1):
        item_id = chapter_item.get("item_id")
        chapter_url = f"https://fanqienovel.com/reader/{item_id}"
        title: str = chapter_item.get("title", "")
        volume_name = chapter_item.get("volume_name", "")
        first_pass_time: float = chapter_item.get("first_pass_time", 0)
        chapter = Chapter(
            title=title,
            url=chapter_url,
            id=str(item_id),
            order=idx,
            novel_id=novel_id,
            volume=volume_name,
            time=first_pass_time,
        )
        results.append(chapter)
    return Chapters(results)
