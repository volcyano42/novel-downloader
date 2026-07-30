import json
import re
import time

import requests
from bs4 import BeautifulSoup, Tag

from novelbase.core.exceptions import AntiCrawlError, ChapterNotFoundError, NovelNotFoundError, ParseError
from novelbase.models.novel import Novel, Chapter, SearchResult, Illustration, Chapters


def standardize_id(url: str) -> str:
    if url.startswith("https"):
        m = re.search(r'/(book|info)/(\d+)', url)
        if m:
            return m.group(2)
        m = re.search(r'/chapter/[^/]+/([^/]+)', url)
        if m:
            return m.group(1)
    raise ValueError(f"ref {url} Non conformance")


def parse_search_result(html: str) -> tuple[SearchResult, ...]:
    soup = BeautifulSoup(html, 'lxml')
    script_list = soup.select('script')
    results: list[SearchResult] = []
    for script in script_list:
        if "g_data.listInfo=" in str(script):
            script_str = script.get_text()
            start_index = script_str.find('g_data.listInfo=') + len('g_data.listInfo=')
            end_index = script_str.find(",g_data.page=")
            json_str = script_str[start_index:end_index]
            json_data = json.loads(json_str)
            for book_data in json_data:
                book_name = book_data.get('bookName')
                description = book_data.get('bookInfo')
                book_url = "https:" + book_data.get('bookUrl')
                author_name = book_data.get('authorName')
                results.append(SearchResult(
                    title=book_name,
                    author=author_name,
                    url=book_url,
                    description=description,
                    cover_url=("https:" + img) if (img := book_data.get('imgUrl')) and img.startswith("//") else (img or None),
                ))
    return tuple(results)


def content_is_exist(html: str) -> bool:

    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.select_one("title")
    if title_tag and title_tag.get_text() == "WAF拦截页面":
        raise AntiCrawlError()

    h1_tag = soup.select_one("h1")
    if h1_tag and h1_tag.get_text() == "抱歉，页面无法访问...":
        return False
    return True


def parse_novel_info(html: str, url) -> Novel:
    soup = BeautifulSoup(html, 'lxml')

    if not content_is_exist(html):
        raise NovelNotFoundError()

    try:
        serial = len(soup.select("div.catalog-all li"))

        name = soup.select_one('h1#bookName').get_text()

        intro_tag = soup.select_one("p.book-desc")
        intro = intro_tag.get_text() if intro_tag else None
        if soup.select_one('div.author-information'):
            author = soup.select_one('a.writer-name').get_text()
            attribute_str = soup.select_one('p.book-attribute').text
            attribute = attribute_str.split('·')
            all_label = attribute
        else:
            all_label = []
            author = soup.select_one('span.author').get_text()

        count_word_str = soup.select_one('p.count em').get_text()
        if count_word_str.endswith("万"):
            count_word = int(float(count_word_str[:-1]) * 10000)
        else:
            count_word = int(count_word_str)

        intro_detail = soup.select_one('p#book-intro-detail').get_text()
        abstract = f'{intro}\n{intro_detail}' if intro else intro_detail

        book_cover_url = 'https:' + soup.select_one('a#bookImg img').get('src')
    except AttributeError as exc:
        raise ParseError("Qidian novel info page missing expected element", detail=str(exc))
    try:
        book_cover_data = requests.get(book_cover_url, timeout=10).content
    except requests.RequestException:
        book_cover_data = b""
    novel_image = Illustration(raw_data=book_cover_data, alt=name, url=book_cover_url)

    novel_id = standardize_id(url) if url else ""

    return Novel(
        url=url,
        id=f"qidian_{novel_id}",
        title=name,
        serial=serial,
        author=author,
        count=count_word,
        description=abstract,
        tags=all_label,
        cover=novel_image,
    )


def parse_chapter_list(html: str, *, url: str = "") -> Chapters:

    soup = BeautifulSoup(html, 'lxml')

    if not content_is_exist(html):
        raise ChapterNotFoundError("Qidian chapter list page blocked or unavailable")

    chapters_div = soup.select_one('div.catalog-all')
    if not chapters_div:
        return Chapters()

    results: list[Chapter] = []
    order = 1
    for chapters_item in chapters_div:
        if not isinstance(chapters_item, Tag):
            continue
        volume_tag = chapters_item.select_one('h3.volume-name')
        volume = volume_tag.get_text().split("·")[0] if volume_tag else ""

        title_list = [item.text for item in chapters_item.select("a.chapter-name")]
        url_list = ["https:" + item.get("href") for item in chapters_item.select("a.chapter-name")]
        for title, chapter_url in zip(title_list, url_list):
            chapter_id = standardize_id(chapter_url)
            results.append(Chapter(
                title=title,
                url=chapter_url,
                id=chapter_id,
                order=order,
                novel_id=standardize_id(url),
                volume=volume,
            ))
            order += 1
    return Chapters(results)


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
