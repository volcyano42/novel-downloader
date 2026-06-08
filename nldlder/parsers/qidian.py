import json
import re
import time
from typing import Sequence

import requests
from bs4 import BeautifulSoup, Tag
from yarl import URL

from .base import BaseParser
from ..core.engine import BrowserEngine
from ..core.exceptions import ChapterNotFoundError, FeatureNotSupportedError, NovelNotFoundError
from ..models.auth import AuthCredential
from ..models.novel import Novel, Chapter, SearchResult, Illustration, Chapters
from ..utils.logger import get_logger

_log = get_logger("nldlder.parsers.qidian")

def standardize_id(identifier: str) -> str:
    if identifier.startswith("https"):
        m = re.search(r'/info/(\d+)', identifier)
        if m:
            return m.group(1)
        m = re.search(r'/chapter/([^/]+)', identifier)
        if m:
            return m.group(1)
    raise ValueError(f"ref {identifier} Non conformance")

class QidianHTMLParser(BaseParser):

    @staticmethod
    def can_handle(identifier: str) -> bool:
        return False

    def login(self, engine, **kwargs) -> AuthCredential:
        raise FeatureNotSupportedError("login", "起点中文网暂不支持通过解析器登录")

    def parse_search_info(self,
                          search_ref: str,
                          engine,
                          page: int = 0,
                          **kwargs) -> tuple[SearchResult, ...] | None:
        _log.debug("parse_search_info: ref=%s page=%s", search_ref[:60], page)
        soup = BeautifulSoup(search_ref, 'lxml')
        script_list = soup.find_all('script')
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
                    description = book_data.get('algInfo')
                    book_url = "https:" + book_data.get('bookUrl')
                    author_name = book_data.get('authorName')
                    results.append(SearchResult(
                        title=book_name,
                        author=author_name,
                        url=book_url,
                        description=description,
                    ))
        return tuple(results) if results else None

    def parse_novel_info(self, novel_ref: str, engine, **kwargs) -> Novel:

        soup = BeautifulSoup(novel_ref, 'lxml')

        name = soup.find('h1', id='bookName').get_text()

        if soup.find('div', class_='author-information'):
            author = soup.find('a', class_='writer-name').get_text()
            attribute_str = soup.find('p', class_='book-attribute').text
            attribute = attribute_str.split('·')
            label = [i.get_text() for i in soup.find('p', class_='all-label').find_all('a')]
            attribute.extend(label)
            all_label = attribute
            intro = soup.find('p', class_='intro').get_text()
        else:
            intro = None
            all_label = []
            author = soup.find('span', class_='author').get_text()

        count_word_str = soup.find('p', class_='count').find('em').get_text()
        if count_word_str.endswith("万"):
            count_word = int(float(count_word_str[:-1]) * 10000)
        else:
            count_word = int(count_word_str)

        intro_detail = soup.find('p', id='book-intro-detail').get_text()
        abstract = f'{intro}\n{intro_detail}' if intro else intro_detail

        book_cover_url = 'https:' + soup.find('a', id='bookImg').find('img').get('src')
        try:
            book_cover_data = requests.get(book_cover_url, timeout=10).content
        except Exception:
            book_cover_data = b""
        novel_image = Illustration(raw_data=book_cover_data, alt=name, url=book_cover_url)

        novel_id = standardize_id(kwargs.get("url", ""))
        url = kwargs.get("url", "")
        if not url:
            url = f"https://book.qidian.com/info/{novel_id}"

        novel = Novel(url=url,
                      id=novel_id,
                      title=name,
                      serial=0,
                      author=author,
                      count=count_word,
                      description=abstract,
                      tags=all_label,
                      cover=novel_image,
                      )
        return novel

    def parse_chapter_list(self, novel_ref, engine, **kwargs) -> Chapters:
        html = novel_ref if isinstance(novel_ref, str) else ""
        soup = BeautifulSoup(html, 'lxml')
        chapters_div = soup.find('div', class_='catalog-all')
        if not chapters_div:
            return Chapters()

        url = kwargs.get("url", "")
        results: list[Chapter] = []
        order = 1
        for chapters_item in chapters_div:
            if not isinstance(chapters_item, Tag):
                continue
            volume_tag = chapters_item.find('h3', class_='volume-name')
            volume = volume_tag.get_text().split("·")[0] if volume_tag else ""

            title_list = [item.text for item in chapters_item.find_all("a", class_="chapter-name")]
            url_list = ["https:" + item.get("href") for item in chapters_item.find_all("a", class_="chapter-name")]
            for title, chapter_url in zip(title_list, url_list):
                chapter_id = standardize_id(chapter_url)
                results.append(Chapter(
                    title=title,
                    url=chapter_url,
                    id=chapter_id,
                    order=order,
                    index_url=url,
                    volume=volume,
                ))
                order += 1
        return Chapters(results)

    def parse_chapter_content(self,
                              chapter_ref,
                              engine,
                              **kwargs) -> Chapters:
        """解析并填充 content, count, is_complete"""
        chapter = kwargs["chapter"]

        html = chapter_ref if isinstance(chapter_ref, str) else ""
        soup = BeautifulSoup(html, 'lxml')

        try:
            script_list = soup.find_all("script")
            for script in script_list:
                if "pageContext" not in str(script):
                    continue
                script_str = script.get_text()
                json_data = json.loads(script_str)
                is_complete = json_data["pageContext"]["pageProps"]["isInIsSafeCanary"]
                chapter_info = json_data["pageContext"]["pageProps"]["pageData"]["chapterInfo"]

                title = chapter_info.get("chapterName", chapter.title)
                word_count = chapter_info.get("wordsCount", 0)
                update_time_stamp = chapter_info.get("updateTimestamp", 0)
                seq = chapter_info.get("seq", chapter.order)
                extra = chapter_info.get("extra", {})
                volume_name = extra.get("volumeName", chapter.volume)

                novel_content_soup = soup.find('main')
                if novel_content_soup:
                    if soup.find('div', class_='mt-16px'):
                        novel_content = '\n'.join(i.get_text().strip() for i in novel_content_soup)
                    else:
                        spans = novel_content_soup.find_all("span", class_="content-text")
                        novel_content = '\n'.join(i.get_text().strip() for i in spans) if spans else ""

                chapter.content = novel_content
                chapter.title = title
                chapter.count = word_count
                chapter.time = update_time_stamp
                chapter.order = seq
                chapter.volume = volume_name
                chapter.is_complete = is_complete
                return Chapters(chapter)
        except (KeyError, TypeError, json.JSONDecodeError):
            pass

        title = soup.find('h1', class_='title').get_text()

        count_word = 0
        relative_div = soup.find("div", class_="relative")
        if relative_div:
            spans = relative_div.find_all("span", class_="group inline-flex items-center mr-16px")
            if spans:
                count_word_str = spans[-1].get_text().split()[-1]
                digits = re.findall(r'\d+', count_word_str)
                if digits:
                    count_word = int(digits[0])

        update_time = 0
        time_span = soup.find('span', class_='chapter-date')
        if time_span:
            try:
                update_time = time.mktime(time.strptime(time_span.get_text(), "%Y年%m月%d日 %H:%M"))
            except (ValueError, OSError):
                pass

        novel_content_soup = soup.find('main')
        if soup.find('div', class_='mt-16px'):
            integrity = False
            novel_content = '\n'.join(i.get_text().strip() for i in novel_content_soup) if novel_content_soup else ""
        else:
            integrity = True
            spans = novel_content_soup.find_all("span", class_="content-text") if novel_content_soup else []
            novel_content = '\n'.join(i.get_text().strip() for i in spans)

        chapter.content = novel_content
        chapter.title = title
        chapter.count = count_word
        chapter.time = update_time
        chapter.is_complete = integrity
        return Chapters(chapter)

class QidianBrowserParser(QidianHTMLParser):

    @staticmethod
    def can_handle(identifier: str) -> bool:
        pass

    def login(self, engine: BrowserEngine, **kwargs) -> AuthCredential:
        _log.info("login start")
        page = engine.new_page()

        try:
            page.get("https://passport.qidian.com/")

            print("请在打开的浏览器窗口中完成登录（扫码/手机号）...")
            deadline = time.time() + 120
            while time.time() < deadline:
                print(page.url)
                if "www.qidian.com" in page.url:
                    break
                time.sleep(0.5)

            time.sleep(2)
            _log.info("login completed")

            raw_cookies = page.cookies()
            cookies = {c["name"]: c["value"] for c in raw_cookies}

            headers = {}

            return AuthCredential(
                cookies=cookies,
                headers=headers,
                extra={}
            )
        finally:
            page.close()

    def parse_search_info(self,
                          search_ref: str,
                          engine,
                          page: int = 0,
                          **kwargs) -> tuple[SearchResult, ...] | None:
        _log.debug("parse_search_info: ref=%s page=%s", search_ref, page)
        search_url = f"https://www.qidian.com/so/{search_ref}.html"
        if page >= 1:
            browser_page = engine.new_page()
            browser_page.get(search_url)
            next_page_xpath = f"/html/body/div[1]/div[3]/div[1]/div[4]/div[2]/div/div/ul/li[{page + 1}]"
            browser_page.ele(f"xpath:{next_page_xpath}").click()
            html = browser_page.html
        else:
            html = engine.fetch_text(search_url, not_delay=True)
        return super().parse_search_info(search_ref=html, engine=engine, page=page, **kwargs)

    def parse_novel_info(self, novel_ref: str, engine, **kwargs) -> Novel:
        html = engine.fetch_text(url=novel_ref, not_delay=True)
        novel = super().parse_novel_info(novel_ref=html, engine=engine, url=novel_ref, **kwargs)
        return novel

    def parse_chapter_list(self, novel_ref, engine, **kwargs) -> Chapters:
        url = novel_ref.url if isinstance(novel_ref, Novel) else novel_ref
        html = engine.fetch_text(url=url, not_delay=True)
        chapter_list = super().parse_chapter_list(novel_ref=html, engine=engine, url=url)
        return Chapters(chapter_list)

    def parse_chapter_content(self,
                              chapter_ref: Sequence[Chapter],
                              engine,
                              **kwargs) -> Chapters:
        url = chapter_ref[0].url
        html = engine.fetch_text(url=url)
        if BeautifulSoup(html, "lxml").find("div", class_="no-content"):
            raise ChapterNotFoundError("chapter content not found")
        chapter = super().parse_chapter_content(chapter_ref=html, engine=engine, chapter=chapter_ref[0], **kwargs)
        return Chapters(chapter)

class QidianRequestsParser(QidianHTMLParser):

    @staticmethod
    def can_handle(identifier: str) -> bool:
        pass

    def login(self, engine, **kwargs) -> AuthCredential:
        raise FeatureNotSupportedError("login", "起点中文网 requests 模式暂不支持登录")

    def parse_search_info(self,
                          search_ref: str,
                          engine,
                          page: int = 0,
                          **kwargs) -> tuple[SearchResult, ...] | None:
        raise FeatureNotSupportedError("search", "起点中文网不支持 Requests 获取搜索结果")

    def parse_novel_info(self, novel_ref: str, engine, **kwargs) -> Novel:
        html = engine.fetch_text(url=novel_ref, not_delay=True)
        novel = super().parse_novel_info(novel_ref=html, engine=engine, url=novel_ref, **kwargs)
        return novel

    def parse_chapter_list(self, novel_ref, engine, **kwargs) -> Chapters:
        url = novel_ref.url if isinstance(novel_ref, Novel) else novel_ref
        html = engine.fetch_text(url=url, not_delay=True)
        chapter_list = super().parse_chapter_list(novel_ref=html, engine=engine, url=url)
        return Chapters(chapter_list)

    def parse_chapter_content(self,
                              chapter_ref: Sequence[Chapter],
                              engine,
                              **kwargs) -> Chapters:
        url = chapter_ref[0].url
        html = engine.fetch_text(url=url)
        if BeautifulSoup(html, "lxml").find("div", class_="no-content"):
            raise ChapterNotFoundError(chapter_ref[0].url)
        chapter = super().parse_chapter_content(chapter_ref=html, engine=engine, chapter=chapter_ref[0], **kwargs)
        return Chapters(chapter)

def use_parser(engine) -> type[QidianRequestsParser | QidianBrowserParser]:
    if engine.name == "browser":
        return QidianBrowserParser
    elif engine.name == "requests":
        return QidianRequestsParser
    elif engine.name == "API":
        raise FeatureNotSupportedError("API", "起点中文网不支持 API 模式")
    else:
        raise ValueError(f"Unknown engine: {engine.name!r}")

class QidianParser(BaseParser):

    @staticmethod
    def can_handle(identifier: str) -> bool:
        try:
            standardize_id(identifier)
            if URL(identifier).host in ("qidian.com", "book.qidian.com", "read.qidian.com"):
                return True
        finally:
            pass
        return False

    def login(self, engine: BrowserEngine, **kwargs) -> AuthCredential | None:
        parser = use_parser(engine=engine)()
        return parser.login(engine=engine, **kwargs)

    def parse_search_info(self,
                          search_ref: str,
                          engine,
                          page=0,
                          **kwargs) -> tuple[SearchResult, ...] | None:
        parser = use_parser(engine=engine)()
        return parser.parse_search_info(search_ref=search_ref, engine=engine, page=page, **kwargs)

    def parse_novel_info(self, novel_ref: str, engine, **kwargs) -> Novel:
        parser = use_parser(engine=engine)()
        return parser.parse_novel_info(novel_ref=novel_ref, engine=engine, **kwargs)

    def parse_chapter_list(self, novel_ref, engine, **kwargs) -> Chapters:
        parser = use_parser(engine=engine)()
        return parser.parse_chapter_list(novel_ref=novel_ref, engine=engine, **kwargs)

    def parse_chapter_content(self,
                              chapter_ref: Sequence[Chapter],
                              engine,
                              **kwargs) -> Chapters:
        parser = use_parser(engine=engine)()
        chapters = parser.parse_chapter_content(chapter_ref=chapter_ref, engine=engine, **kwargs)
        return chapters
