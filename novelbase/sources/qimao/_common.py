"""qimao (qimao.com) shared parse functions."""
import re
import logging

import requests
from bs4 import BeautifulSoup, Tag

from novelbase.core.exceptions import ChapterNotFoundError, NovelNotFoundError, ParseError
from novelbase.models.novel import Novel, Chapter, SearchResult, Illustration, Chapters

_log = logging.getLogger("novelbase.fetchers.qimao")


def _api_url(engine, **params) -> str:
    """Rain API URL builder."""
    key = engine.options.key
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://v3.rain.ink/qimao/?apikey={key}&{qs}"


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


def parse_search_result(html: str):
    soup = BeautifulSoup(html, "lxml")
    results: list = []
    items = soup.select("ul.search-book-list li.qm-cover-text-item")
    if not items:
        return ()
    for item in items:
        title_a = item.select_one(".text-content .s-tit a")
        if not title_a:
            continue
        title = title_a.get_text(strip=True)
        url = title_a.get("href", "")
        author = ""
        author_a = item.select_one(".text-bottom-row .item-wrap .link")
        if author_a:
            author = author_a.get_text(strip=True)
        desc_span = item.select_one(".text-content .s-desc")
        description = desc_span.get_text(strip=True) if desc_span else ""
        cover_img = item.select_one("img.book-cover-src, .cover-img img, img.cover")
        cover_url = cover_img.get("src") or cover_img.get("data-src") or "" if cover_img else ""
        results.append(SearchResult(
            title=title, author=author, url=url, description=description,
            cover_url=cover_url or None,
        ))
    return tuple(results)


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
    try:
        cover_data = requests.get(cover_url, timeout=10).content if cover_url else b""
    except requests.RequestException:
        cover_data = b""
    cover = Illustration(raw_data=cover_data, alt=name, url=cover_url)
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
    novel_id = standardize_id(book_url) if book_url else ""
    return Novel(url=book_url, id=novel_id, title=name, author=author,
                 serial=serial, tags=tuple(tags), description=abstract,
                 count=count_word, cover=cover)


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
