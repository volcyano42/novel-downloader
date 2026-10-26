import re

from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter, Chapters, Novel


def _api_url(engine, **params) -> str:
    key = engine.options.key
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    base = f"https://v3.rain.ink/fanqie/?apikey={key}"
    return f"{base}&{qs}" if qs else base


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
    url = _api_url(engine, type=3, bookid=novel_id)
    json_data = await engine.async_fetch_json(url, **kwargs)

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
