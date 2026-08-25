"""qimao requests - fetch chapter content."""

from novelbase.models.novel import Chapter
from ..._common import parse_chapter_content


async def chapter_content(chapter: Chapter, engine, **kwargs) -> Chapter | None:
    html = await engine.async_fetch_text(url=chapter.url, **kwargs)
    return parse_chapter_content(html, chapter)
