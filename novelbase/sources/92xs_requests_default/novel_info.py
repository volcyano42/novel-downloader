"""92xs novel_info — 解析 /book/{id}.html。"""
from bs4 import BeautifulSoup

from novelbase.models.novel import Novel, Illustration


async def novel_info(url: str, engine, **kwargs) -> Novel:
    html = await engine.async_fetch_text(url)
    soup = BeautifulSoup(html, "html.parser")

    # 书名
    name_el = soup.select_one(".d_title h1")
    title = name_el.get_text(strip=True) if name_el else ""

    # 作者
    author_el = soup.select_one(".p_author")
    author = author_el.get_text(strip=True) if author_el else ""
    author = author.removeprefix("作者：").removeprefix("作者:")

    # 简介 — #bookintro 下最后一个 p
    intro_el = soup.select_one("#bookintro")
    paragraphs = intro_el.select("p") if intro_el else []
    description = paragraphs[-1].get_text(strip=True) if paragraphs else ""

    # 分类/字数 — #count span
    count_spans = soup.select("#count span")
    tags: list[str] = []
    word_count: int | None = None
    for span in count_spans:
        text = span.get_text(strip=True)
        if not text:
            continue
        if "小说" in text and text not in tags:
            tags.append(text.replace("小说", "").strip())
        elif text.isdigit():
            word_count = int(text)

    # 封面 URL（字节由 engine.async_fetch_images 下载）
    cover: Illustration | None = None
    cover_img = soup.select_one("#bookimg img")
    if cover_img:
        cover_url = cover_img.get("src", "")
        if cover_url:
            # 相对路径 → 绝对 URL
            if cover_url.startswith("/"):
                cover_url = f"http://www.92xs.info{cover_url}"
            cover = Illustration(raw_data=b"", url=cover_url, alt=title)

    novel = Novel(
        title=title,
        author=author,
        url=url,
        description=description,
        tags=tuple(tags),
        count=word_count,
        cover=cover,
        serial=0,  # 暂无可靠来源
    )
    if novel.cover and novel.cover.url:
        data = await engine.async_fetch_images([novel.cover.url])
        novel.cover = Illustration(
            raw_data=data[0], alt=novel.cover.alt, url=novel.cover.url
        )
    return novel
