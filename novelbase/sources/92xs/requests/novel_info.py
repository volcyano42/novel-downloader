"""92xs novel_info — 解析 /book/{id}.html。"""
from bs4 import BeautifulSoup
from novelbase.models.novel import Novel, Illustration


def novel_info(url: str, engine, **kwargs) -> Novel:
    html = engine.fetch_text(url)
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

    # 封面
    cover: Illustration | None = None
    cover_img = soup.select_one("#bookimg img")
    if cover_img:
        cover_url = cover_img.get("src", "")
        if cover_url:
            cover = Illustration(raw_data=b"", url=cover_url, alt=title)

    # 提取 book_id
    import re
    from urllib.parse import urlparse
    path = urlparse(url).path
    m = re.search(r"(?:/book/|/html/)(\d+)", path)
    novel_id = f"92xs_{m.group(1)}" if m else ""

    return Novel(
        title=title,
        author=author,
        id=novel_id,
        url=url,
        description=description,
        tags=tuple(tags),
        count=word_count,
        cover=cover,
        serial="",  # 暂无可靠来源
    )
