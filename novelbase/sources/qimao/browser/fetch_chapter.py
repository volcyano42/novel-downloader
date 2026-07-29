"""qimao browser - fetch chapter content."""

from .._common import parse_chapter_content
from novelbase.models.novel import Chapter


def fetch_chapter(chapter: Chapter, engine, **kwargs) -> Chapter | None:
    html = engine.fetch_text(url=chapter.url, **kwargs)
    return parse_chapter_content(html, chapter)
