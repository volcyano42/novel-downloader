"""qimao browser - fetch novel info."""

import re

from bs4 import BeautifulSoup

from novelbase.core.exceptions import NovelNotFoundError
from novelbase.models.novel import Novel, Illustration


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

def parse_novel_info(html: str, *, url: str = ""):
    soup = BeautifulSoup(html, "lxml")
    meta_desc = soup.select_one('meta[data-hid="description"]')
    if meta_desc and 'content="\u300aundefined\u300b' in str(meta_desc):
        raise NovelNotFoundError("qimao novel not found (meta contains undefined)")
    title_span = soup.select_one(".book-information .wrap-txt .title .txt")
    if not title_span:
        raise NovelNotFoundError("qimao novel detail page missing title element")
    name = title_span.get_text(strip=True)
    book_url = url
    if not book_url:
        canonical = soup.select_one('link[rel="canonical"]')
        if canonical:
            book_url = canonical.get("href", "")
    author = ""
    author_tag = soup.select_one(".sub-title .txt em a")
    if author_tag:
        author = author_tag.get_text(strip=True)
    else:
        meta_author = soup.select_one('meta[name="author"]')
        if meta_author:
            author = meta_author.get("content", "")
    tags: list[str] = []
    status_tag = soup.select_one(".qm-tag.tag.orange")
    if status_tag:
        tags.append(status_tag.get_text(strip=True))
    for tag_a in soup.select(".tags-wrap .qm-tag.tag a"):
        tag_text = tag_a.get_text(strip=True)
        if tag_text:
            tags.append(tag_text)
    count_word = 0
    stats_ems = soup.select(".statistics-wrap .txt em")
    if stats_ems:
        word_str = stats_ems[0].get_text(strip=True)
        try:
            if "\u4e07" in word_str:
                count_word = int(float(word_str.replace("\u4e07", "").replace("\u5b57", "")) * 10000)
            else:
                count_word = int(re.sub(r"[^\d]", "", word_str) or "0")
        except (ValueError, TypeError):
            count_word = 0
    intro_p = soup.select_one(".book-introduction .intro")
    abstract = intro_p.get_text(strip=True) if intro_p else ""
    cover_img = soup.select_one(".wrap-pic img")
    cover_url = cover_img.get("src", "") if cover_img else ""
    # 封面字节由能力函数经 engine.async_fetch_images 下载
    cover = Illustration(raw_data=b"", alt=name, url=cover_url)
    serial = 0
    chapter_tab = soup.select_one(".qm-tab-list-item .sub-txt")
    if chapter_tab:
        tab_text = chapter_tab.get_text(strip=True)
        try:
            serial = int(re.sub(r"[^\d]", "", tab_text) or "0")
        except ValueError:
            serial = 0
    if serial == 0:
        chapter_items = soup.select(".book-catalog-list-content li a")
        serial = len(chapter_items)
    return Novel(url=book_url, title=name, author=author,
                 serial=serial, tags=tuple(tags), description=abstract,
                 count=count_word, cover=cover)

async def novel_info(url: str, engine, **kwargs) -> Novel:
    novel_id = standardize_id(url)
    url = f"https://www.qimao.com/shuku/{novel_id}/"
    html = await engine.async_fetch_text(url=url, **kwargs)
    novel = parse_novel_info(html, url=url)
    if novel.cover and novel.cover.url:
        data = await engine.async_fetch_images([novel.cover.url])
        novel.cover = Illustration(
            raw_data=data[0], alt=novel.cover.alt, url=novel.cover.url
        )
    return novel
