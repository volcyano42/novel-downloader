"""92xs chapter_list — 解析 /html/{id}/。"""
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from novelbase.models.novel import Chapter, Chapters


async def chapter_list(url: str, engine, **kwargs) -> Chapters:
    # 规范化 URL：/book/{id}.html → /html/{id}/
    import re
    path = urlparse(url).path
    m = re.search(r"(?:/book/|/html/)(\d+)", path)
    if m:
        url = f"http://www.92xs.info/html/{m.group(1)}/"

    html = await engine.async_fetch_text(url)
    soup = BeautifulSoup(html, "html.parser")

    chapters: list[Chapter] = []
    for ccss in soup.select(".ccss"):
        a = ccss.select_one("a")
        if not a:
            continue
        href = a.get("href", "")
        if not href:
            continue
        if href.startswith("/"):
            href = "http://www.92xs.info" + href

        chapter = Chapter(
            id=href,           # 用 URL 作唯一标识
            url=href,
            novel_id="",       # 由 downloader 回填
            title=a.get_text(strip=True),
            order=len(chapters) + 1,
        )
        chapters.append(chapter)

    return Chapters(chapters)
