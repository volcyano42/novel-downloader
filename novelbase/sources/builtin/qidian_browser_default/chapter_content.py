import json
import re
import time

from bs4 import BeautifulSoup

from novelbase.core.exceptions import AntiCrawlError, ChapterNotFoundError
from novelbase.models.novel import Chapter


def content_is_exist(html: str) -> bool:

    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.select_one("title")
    if title_tag and title_tag.get_text() == "WAF拦截页面":
        raise AntiCrawlError()

    h1_tag = soup.select_one("h1")
    if h1_tag and h1_tag.get_text() == "抱歉，页面无法访问...":
        return False
    return True

def parse_chapter_content(html: str, chapter: Chapter) -> Chapter:
    """解析并填充 content, count, time, """
    parent_soup = BeautifulSoup(html, 'lxml')

    if not content_is_exist(html):
        raise ChapterNotFoundError("Qidian chapter page blocked or unavailable")

    json_data = parent_soup.select_one("script#vite-plugin-ssr_pageContext")
    if json_data:
        script_str = json_data.get_text()
        json_data = json.loads(script_str)
        chapter_info = json_data["pageContext"]["pageProps"]["pageData"]["chapterInfo"]
        word_count = chapter_info.get("wordsCount", 0)
        update_time_stamp = chapter_info.get("updateTimestamp", 0)
        novel_content_soup = parent_soup.select_one('main')
        if parent_soup.select_one('input[type="checkbox"]'):
            # 章节不完整，但内容仍在页面中
            novel_content = '\n\n'.join(i.get_text().strip() for i in novel_content_soup) if novel_content_soup else ""
        else:
            spans = novel_content_soup.select("span.content-text") if novel_content_soup else []
            novel_content = '\n\n'.join(i.get_text().strip() for i in spans)

        chapter.content = novel_content
        chapter.count = word_count
        chapter.time = update_time_stamp
        return chapter

    title_tag = parent_soup.select_one('h1.title')
    title = title_tag.get_text() if title_tag else ""

    count_word = 0
    relative_div = parent_soup.select_one("div.relative")
    if relative_div:
        spans = relative_div.select("span.group.inline-flex.items-center.mr-16px")
        if spans:
            count_word_str = spans[-1].get_text().split()[-1]
            digits = re.findall(r'\d+', count_word_str)
            if digits:
                count_word = int(digits[0])

    update_time = 0
    time_span = parent_soup.select_one('span.chapter-date')
    if time_span:
        try:
            update_time = time.mktime(time.strptime(time_span.get_text(), "%Y年%m月%d日 %H:%M"))
        except (ValueError, OSError):
            pass

    novel_content_soup = parent_soup.select_one('main')
    if parent_soup.select_one('input[type="checkbox"]'):
        # 章节不完整，但内容仍在页面中
        novel_content = '\n\n'.join(i.get_text().strip() for i in novel_content_soup) if novel_content_soup else ""
    else:
        spans = novel_content_soup.select("span.content-text") if novel_content_soup else []
        novel_content = '\n\n'.join(i.get_text().strip() for i in spans)

    chapter.content = novel_content
    chapter.title = title
    chapter.count = count_word
    chapter.time = update_time
    return chapter

async def chapter_content(chapter: Chapter, engine, **kwargs) -> Chapter | None:
    url = chapter.url
    html = await engine.async_fetch_text(url=url, **kwargs)
    if BeautifulSoup(html, "lxml").select_one("div.no-content"):
        raise ChapterNotFoundError("Qidian chapter page shows no-content div")
    result = parse_chapter_content(html, chapter)
    return result
