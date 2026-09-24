import json
import re
from typing import Any

from bs4 import BeautifulSoup

from novelbase.core.exceptions import NovelNotFoundError
from novelbase.models.novel import Novel, Illustration, Chapter


def standardize_id(ref: str | Novel | Chapter) -> str:

    if isinstance(ref, Novel):
        ref = ref.url
    if isinstance(ref, Chapter):
        ref = ref.url
    if isinstance(ref, str):
        if re.match(r"^\d{19}$", ref):
            return ref
        if search := re.search(r"book_id=(\d{19})", ref):
            return search.group(1)
        if search := re.search(r"\d{19}", ref):
            return search.group(0)
    raise ValueError(f"ref {ref} Non conformance")

def extract_json(html_content: str) -> dict[str, Any]:

    start = html_content.find("window.__INITIAL_STATE__=")
    if start == -1:
        return {}

    start += len("window.__INITIAL_STATE__=")
    start_html = html_content[start:]
    end = start_html.find(")()")
    script = start_html[:end].strip()[:-1].strip()[:-1]
    script = script.replace('"libra":undefined', '"libra":"undefined"')

    json_data = json.loads(script)
    return json_data

def parse_novel_info(html: str) -> Novel:

    if BeautifulSoup(html, 'lxml').select_one("div.no-content"):
        raise NovelNotFoundError()

    json_data = extract_json(html)
    if not json_data:
        raise NovelNotFoundError()

    page_data = json_data.get('page')
    book_url = f"https://fanqienovel.com/page/{page_data['bookId']}"
    name = page_data.get("bookName")
    author = page_data.get("author")
    label_item_str = page_data.get("categoryV2")
    label_item_list = json.loads(label_item_str)
    status = page_data.get("creationStatus")
    label_list = []
    if status == 1:
        label_list.append("连载中")
    else:
        label_list.append("已完结")

    for label_item in label_item_list:
        label_list.append(label_item.get("Name"))
    count_word = page_data.get("wordNumber")
    abstract = page_data.get("abstract")

    book_cover_url = page_data.get("thumbUri")
    # 封面只收集 URL，字节下载归 novel_info 能力函数（engine.async_fetch_images）
    cover_image = Illustration(raw_data=b"", alt=name, url=book_cover_url) if book_cover_url else None
    chapter_list_with_volume = json_data.get("page", {}).get("chapterListWithVolume", {})
    serial = 0
    for chapters_list in chapter_list_with_volume:
        serial += len(chapters_list)

    novel = Novel(url=book_url,
                  title=name,
                  author=author,
                  serial=serial,
                  tags=tuple(label_list),
                  description=abstract,
                  count=count_word,
                  cover=cover_image
                  )
    return novel

async def novel_info(url: str, engine, **kwargs):
    url = f"https://fanqienovel.com/page/{standardize_id(url)}"
    html = await engine.async_fetch_text(url=url, **kwargs)
    novel = parse_novel_info(html=html)
    if novel.cover and novel.cover.url:
        data = await engine.async_fetch_images([novel.cover.url])
        novel.cover = Illustration(
            raw_data=data[0], alt=novel.cover.alt, url=novel.cover.url
        )
    return novel
