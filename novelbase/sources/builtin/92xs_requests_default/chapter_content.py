"""92xs chapter_content — 解析 /html/{book_id}/{ch_id}.html。"""
from bs4 import BeautifulSoup

from novelbase.models.novel import Chapter


async def chapter_content(chapter: Chapter, engine, **kwargs) -> Chapter | None:
    html = await engine.async_fetch_text(chapter.url)
    soup = BeautifulSoup(html, "html.parser")

    content_el = soup.select_one("#ccontent")
    if not content_el:
        return None

    # 正文首尾各插一个站内广告位（「最新网址：www.92xs.info」，域名可能变）→ 按 id 剥离，不匹配文本
    for tip in content_el.select("#center_tip"):
        tip.decompose()

    text = content_el.get_text()
    if not text.strip():
        return None

    chapter.content = text
    chapter.count = len(text)
    return chapter
