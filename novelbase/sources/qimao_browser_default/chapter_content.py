"""qimao browser - fetch chapter content."""

from bs4 import BeautifulSoup, Tag

from novelbase.core.exceptions import ChapterNotFoundError, ParseError
from novelbase.models.novel import Chapter


def parse_chapter_content(html: str, chapter: Chapter):
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.select_one(".chapter-title")
    chapter_title = title_tag.get_text(strip=True) if title_tag else ""
    word_count_dd = soup.select(".chapter-tips dd")
    word_count = 0
    if len(word_count_dd) >= 3:
        try:
            word_count = int(word_count_dd[2].get_text(strip=True) or "0")
        except ValueError:
            word_count = 0
    if not chapter_title and word_count == 0:
        raise ChapterNotFoundError("qimao chapter not found (title and word count both empty)")
    if chapter_title:
        chapter.title = chapter_title
    if soup.select_one(".reader-login-code") or soup.select_one(".show-part"):
        return None
    article_div = soup.select_one(".chapter-detail-article .article")
    if not article_div:
        raise ParseError("qimao chapter page missing content container .article")
    paragraphs: list[str] = []
    for element in article_div.children:
        if not isinstance(element, Tag):
            continue
        if element.name == "p":
            text = element.get_text(strip=True)
            if text:
                paragraphs.append(text)
    content = "\n\n".join(paragraphs)
    chapter.content = content
    chapter.count = word_count or len(content)
    return chapter

async def chapter_content(chapter: Chapter, engine, **kwargs) -> Chapter | None:
    html = await engine.async_fetch_text(url=chapter.url, **kwargs)
    return parse_chapter_content(html, chapter)
