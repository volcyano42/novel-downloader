"""92xs chapter_content — 解析 /html/{book_id}/{ch_id}.html。"""
from bs4 import BeautifulSoup
from novelbase.models.novel import Chapter


def chapter_content(chapter: Chapter, engine, **kwargs) -> Chapter | None:
    html = engine.fetch_text(chapter.url)
    soup = BeautifulSoup(html, "html.parser")

    content_el = soup.select_one("#ccontent")
    if not content_el:
        return None

    text = content_el.get_text()
    if not text.strip():
        return None

    chapter.content = text
    chapter.count = len(text)
    return chapter
