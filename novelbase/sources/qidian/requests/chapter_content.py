from bs4 import BeautifulSoup

from .._common import parse_chapter_content
from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter


async def chapter_content(chapter: Chapter, engine, **kwargs) -> Chapter | None:
    url = chapter.url
    html = await engine.async_fetch_text(url=url, **kwargs)
    if BeautifulSoup(html, "lxml").select_one("div.no-content"):
        raise ChapterNotFoundError(f"Qidian chapter page shows no-content div: {chapter.url}")
    result = parse_chapter_content(html, chapter)
    return result
