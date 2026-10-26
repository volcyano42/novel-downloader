import re

from bs4 import BeautifulSoup, Tag

from novelbase.core.exceptions import AntiCrawlError, ChapterNotFoundError
from novelbase.models.novel import Chapter, Chapters, Novel


def standardize_id(url: str) -> str:
    if url.startswith("https"):
        m = re.search(r'/(book|info)/(\d+)', url)
        if m:
            return m.group(2)
        m = re.search(r'/chapter/[^/]+/([^/]+)', url)
        if m:
            return m.group(1)
    raise ValueError(f"ref {url} Non conformance")

def content_is_exist(html: str) -> bool:

    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.select_one("title")
    if title_tag and title_tag.get_text() == "WAF拦截页面":
        raise AntiCrawlError()

    h1_tag = soup.select_one("h1")
    if h1_tag and h1_tag.get_text() == "抱歉，页面无法访问...":
        return False
    return True

def parse_chapter_list(html: str, *, url: str = "") -> Chapters:

    soup = BeautifulSoup(html, 'lxml')

    if not content_is_exist(html):
        raise ChapterNotFoundError("Qidian chapter list page blocked or unavailable")

    chapters_div = soup.select_one('div.catalog-all')
    if not chapters_div:
        return Chapters()

    results: list[Chapter] = []
    order = 1
    for chapters_item in chapters_div:
        if not isinstance(chapters_item, Tag):
            continue
        volume_tag = chapters_item.select_one('h3.volume-name')
        volume = volume_tag.get_text().split("·")[0] if volume_tag else ""

        title_list = [item.text for item in chapters_item.select("a.chapter-name")]
        url_list = ["https:" + item.get("href") for item in chapters_item.select("a.chapter-name")]
        for title, chapter_url in zip(title_list, url_list, strict=True):
            chapter_id = standardize_id(chapter_url)
            results.append(Chapter(
                title=title,
                url=chapter_url,
                id=chapter_id,
                order=order,
                novel_id=standardize_id(url),
                volume=volume,
            ))
            order += 1
    return Chapters(results)

async def chapter_list(url: str, engine, **kwargs) -> list[Chapter]:
    url = url.url if isinstance(url, Novel) else url
    html = await engine.async_fetch_text(url=url, **kwargs)
    chapters = parse_chapter_list(html, url=url)
    return list(chapters) if chapters else []
