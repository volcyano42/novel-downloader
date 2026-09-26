import re

from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Novel, Chapter, Chapters


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

    # 契约实测 2026-09-26：真实 data 为**分卷嵌套** list[list[dict]]（每卷若干章）；
    # 兼容扁平 list[dict]（个别响应/书可能直接给扁平列表），两种形态都解析。
    # 章节字段：chapter_id/index/title/time/volume_name（另有 volume/pay）。
    for group in chapter_items_volume:
        chapter_items = group if isinstance(group, list) else [group]
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
