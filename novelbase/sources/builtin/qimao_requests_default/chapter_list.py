"""qimao requests - fetch chapter list.
Note: qimao chapter catalog is loaded by client-side JS in the initial SSR HTML.
If the catalog is missing from SSR HTML, fallback to reader sidebar (partial only).
For the full catalog, use browser engine."""

import re

from bs4 import BeautifulSoup

from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter, Chapters


def standardize_id(ref):
    if hasattr(ref, 'url'):
        ref = ref.url
    if isinstance(ref, str):
        if m := re.search(r"/shuku/(\d+-\d+)", ref):
            return m.group(1)
        if m := re.search(r"/shuku/(\d+)", ref):
            return m.group(1)
        if m := re.match(r"^(\d+)$", ref):
            return m.group(1)
    raise ValueError(f"ref {ref} does not match qimao ID format")

def parse_chapter_list(html: str, *, novel_id: str = ""):
    soup = BeautifulSoup(html, "lxml")
    meta_desc = soup.select_one('meta[data-hid="description"]')
    if meta_desc and 'content="\u300aundefined\u300b' in str(meta_desc):
        raise ChapterNotFoundError("qimao novel not found, cannot get catalog")
    chapter_items = soup.select(".qm-book-catalog-list-content li a")
    if not chapter_items:
        chapter_items = soup.select(".book-catalog-list-content li a")
    results: list[Chapter] = []
    for order, a_tag in enumerate(chapter_items, start=1):
        title_span = a_tag.select_one("span.txt")
        title = title_span.get_text(strip=True) if title_span else ""
        chapter_url = a_tag.get("href", "")
        if not chapter_url:
            continue
        if chapter_url.startswith("/"):
            chapter_url = f"https://www.qimao.com{chapter_url}"
        chapter_id = standardize_id(chapter_url)
        results.append(Chapter(id=chapter_id, url=chapter_url, novel_id=novel_id,
                               title=title, order=order))
    return Chapters(results)

async def chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    novel_id = standardize_id(url)
    url = f"https://www.qimao.com/shuku/{novel_id}/"
    html = await engine.async_fetch_text(url=url, **kwargs)
    chapters = parse_chapter_list(html, novel_id=standardize_id(url))
    if len(chapters) == 0:
        raise ChapterNotFoundError(
            "qimao chapter catalog not found in initial HTML (loaded by JS), "
            "please use browser engine or provide catalog page HTML"
        )
    return list(chapters)
