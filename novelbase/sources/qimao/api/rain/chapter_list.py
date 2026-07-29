"""qimao API (Rain) - fetch chapter list."""

from ..._common import _api_url, standardize_id
from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter


def chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    novel_id = standardize_id(url)
    api_url = _api_url(engine, type=3, id=novel_id)
    json_data = engine.fetch_json(api_url, **kwargs)

    code = json_data.get("code")
    if code is not None and code != 0 and str(code) != "0":
        raise ChapterNotFoundError(f"Rain API returned error code: {code}")

    chapter_lists = json_data.get("data", {}).get("chapter_lists")
    if not chapter_lists:
        raise ChapterNotFoundError("Rain API returned empty chapter list")

    results: list[Chapter] = []
    for chapter_item in chapter_lists:
        ch_id = chapter_item.get("id")
        chapter_url = f"https://www.qimao.com/shuku/{novel_id}-{ch_id}/"
        title = chapter_item.get("title", "")
        index = int(chapter_item.get("index", "0"))
        chapter = Chapter(
            title=title,
            url=chapter_url,
            id=str(ch_id),
            order=index,
            novel_id=novel_id,
        )
        results.append(chapter)
    return results
