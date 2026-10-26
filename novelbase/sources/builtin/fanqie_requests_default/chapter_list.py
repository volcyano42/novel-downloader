import json
import re
from typing import Any

from bs4 import BeautifulSoup

from novelbase.core.exceptions import ChapterNotFoundError
from novelbase.models.novel import Chapter, Chapters, Novel


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

def parse_chapter_list(html: str) -> Chapters:

    if BeautifulSoup(html, 'lxml').select_one("div.no-content"):
        raise ChapterNotFoundError("Chapter list page shows no-content div")
    json_data = extract_json(html)
    if not json_data:
        raise ChapterNotFoundError("Chapter list JSON extraction returned empty")

    chapter_list_with_volume = json_data.get("page").get("chapterListWithVolume")
    book_url = "https://fanqienovel.com/page/" + json_data.get("page", {}).get("bookId")
    chapter_list = []

    for chapters_list in chapter_list_with_volume:
        for chapter_item in chapters_list:
            title = chapter_item["title"]
            chapter_url = 'https://fanqienovel.com/reader/' + chapter_item.get("itemId")
            first_pass_time = int(chapter_item.get("firstPassTime", 0))
            order = int(chapter_item.get("realChapterOrder"))
            volume_name = chapter_item.get("volume_name")
            chapter = Chapter(title=title,
                              url=chapter_url,
                              novel_id=standardize_id(book_url),
                              id=standardize_id(chapter_url),
                              volume=volume_name,
                              order=order,
                              time=first_pass_time)
            chapter_list.append(chapter)

    return Chapters(chapter_list)

async def chapter_list(url: str, engine, **kwargs) -> list:
    url = f"https://fanqienovel.com/page/{standardize_id(url)}"
    html = await engine.async_fetch_text(url=url, **kwargs)
    return list(parse_chapter_list(html=html))
