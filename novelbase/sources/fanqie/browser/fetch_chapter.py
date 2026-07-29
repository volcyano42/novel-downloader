from bs4 import BeautifulSoup

from novelbase.core.exceptions import ChapterNotFoundError

from .._common import standardize_id, parse_chapter_content


def fetch_chapter(chapter, engine, **kwargs):
    url = f"https://fanqienovel.com/reader/{standardize_id(chapter)}"
    html = engine.fetch_text(url=url, **kwargs)

    if BeautifulSoup(html, "lxml").select_one("div.no-content"):
        raise ChapterNotFoundError("Chapter page shows no-content div")

    return parse_chapter_content(html, chapter)
