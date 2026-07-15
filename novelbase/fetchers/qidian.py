import json
import re
import time

import requests
from bs4 import BeautifulSoup, Tag

from .base import BaseFetcher
from novelbase.core.engine import BrowserEngine
from novelbase.core.exceptions import ChapterNotFoundError, FeatureNotSupportedError, NovelNotFoundError, ParseError
from novelbase.models.auth import AuthCredential
from novelbase.models.novel import Novel, Chapter, SearchResult, Illustration, Chapters
from novelbase.utils.logger import get_logger
from .. import AntiCrawlError

_log = get_logger("novelbase.fetchers.qidian")

def standardize_id(url: str) -> str:
    if url.startswith("https"):
        m = re.search(r'/(book|info)/(\d+)', url)
        if m:
            return m.group(2)
        m = re.search(r'/chapter/[^/]+/([^/]+)', url)
        if m:
            return m.group(1)
    raise ValueError(f"ref {url} Non conformance")


class QidianHTMLParser:

    @staticmethod
    def parse_search_result(html: str) -> tuple[SearchResult, ...]:
        soup = BeautifulSoup(html, 'lxml')
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
                    description = book_data.get('bookInfo')
                    book_url = "https:" + book_data.get('bookUrl')
                    author_name = book_data.get('authorName')
                    results.append(SearchResult(
                        title=book_name,
                        author=author_name,
                        url=book_url,
                        description=description,
                    ))
        return tuple(results)

    @staticmethod
    def content_is_exist(html: str) -> bool:

        soup = BeautifulSoup(html, "lxml")

        title_tag = soup.find("title")
        if title_tag and title_tag.get_text() == "WAF拦截页面":
            raise AntiCrawlError()

        h1_tag = soup.find("h1")
        if h1_tag and h1_tag.get_text() == "抱歉，页面无法访问...":
            return False
        return True

    @staticmethod
    def parse_novel_info(html: str, url) -> Novel:
        soup = BeautifulSoup(html, 'lxml')

        if not QidianHTMLParser.content_is_exist(html):
            raise NovelNotFoundError()

        try:
            serial = len(soup.find("div", class_="catalog-all").find_all("li"))

            name = soup.find('h1', id='bookName').get_text()

            intro = soup.find("p", class_="book-desc").get_text() if soup.find("p", class_="book-desc") else None
            if soup.find('div', class_='author-information'):
                author = soup.find('a', class_='writer-name').get_text()
                attribute_str = soup.find('p', class_='book-attribute').text
                attribute = attribute_str.split('·')
                all_label = attribute
            else:
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
            id=novel_id,
            title=name,
            serial=serial,
            author=author,
            count=count_word,
            description=abstract,
            tags=all_label,
            cover=novel_image,
        )

    @staticmethod
    def parse_chapter_list(html: str, *, url: str = "") -> Chapters:

        soup = BeautifulSoup(html, 'lxml')

        if not QidianHTMLParser.content_is_exist(html):
            raise ChapterNotFoundError("Qidian chapter list page blocked or unavailable")

        chapters_div = soup.find('div', class_='catalog-all')
        if not chapters_div:
            return Chapters()

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
                    novel_id=standardize_id(url),
                    volume=volume,
                ))
                order += 1
        return Chapters(results)

    @staticmethod
    def parse_chapter_content(html: str, chapter: Chapter) -> Chapter:
        """解析并填充 content, count, time, """
        parent_soup = BeautifulSoup(html, 'lxml')

        if not QidianHTMLParser.content_is_exist(html):
            raise ChapterNotFoundError("Qidian chapter page blocked or unavailable")

        json_data = parent_soup.find("script", id = "vite-plugin-ssr_pageContext")
        if json_data:
            script_str = json_data.get_text()
            json_data = json.loads(script_str)
            chapter_info = json_data["pageContext"]["pageProps"]["pageData"]["chapterInfo"]
            word_count = chapter_info.get("wordsCount", 0)
            update_time_stamp = chapter_info.get("updateTimestamp", 0)
            novel_content_soup = parent_soup.find('main')
            if parent_soup.find(name='input', attrs = {"type": "checkbox"}):
                # 章节不完整，但内容仍在页面中
                novel_content = '\n\n'.join(i.get_text().strip() for i in novel_content_soup) if novel_content_soup else ""
            else:
                spans = novel_content_soup.find_all("span", class_="content-text") if novel_content_soup else []
                novel_content = '\n\n'.join(i.get_text().strip() for i in spans)

            chapter.content = novel_content
            chapter.count = word_count
            chapter.time = update_time_stamp
            return chapter

        title_tag = parent_soup.find('h1', class_='title')
        title = title_tag.get_text() if title_tag else ""

        count_word = 0
        relative_div = parent_soup.find("div", class_="relative")
        if relative_div:
            spans = relative_div.find_all("span", class_="group inline-flex items-center mr-16px")
            if spans:
                count_word_str = spans[-1].get_text().split()[-1]
                digits = re.findall(r'\d+', count_word_str)
                if digits:
                    count_word = int(digits[0])

        update_time = 0
        time_span = parent_soup.find('span', class_='chapter-date')
        if time_span:
            try:
                update_time = time.mktime(time.strptime(time_span.get_text(), "%Y年%m月%d日 %H:%M"))
            except (ValueError, OSError):
                pass

        novel_content_soup = parent_soup.find('main')
        if parent_soup.find(name='input', attrs = {"type": "checkbox"}):
            # 章节不完整，但内容仍在页面中
            novel_content = '\n\n'.join(i.get_text().strip() for i in novel_content_soup) if novel_content_soup else ""
        else:
            spans = novel_content_soup.find_all("span", class_="content-text") if novel_content_soup else []
            novel_content = '\n\n'.join(i.get_text().strip() for i in spans)

        chapter.content = novel_content
        chapter.title = title
        chapter.count = count_word
        chapter.time = update_time
        return chapter


class QidianBrowserFetcher(BaseFetcher):

    def login(self, engine: BrowserEngine, **kwargs) -> AuthCredential:
        _log.info("login start")
        page = engine.new_page()

        try:
            page.get("https://passport.qidian.com/")

            print("请在打开的浏览器窗口中完成登录（扫码/手机号）...")
            deadline = time.time() + 120
            while time.time() < deadline:
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

    def fetch_search_result(self,
                            query: str,
                            engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        page = kwargs.pop("page", 1)
        _log.debug("parse_search_info: ref=%s page=%s", query, page)
        search_url = f"https://www.qidian.com/so/{query}.html"

        if page > 1:
            browser_page = engine.new_page()
            browser_page.get(search_url)
            next_page_xpath = f"/html/body/div[1]/div[3]/div[1]/div[4]/div[2]/div/div/ul/li[{page}]"
            browser_page.ele(f"xpath:{next_page_xpath}").click()
            html = browser_page.html
        else:
            html = engine.fetch_text(search_url, **kwargs)

        return QidianHTMLParser.parse_search_result(html)

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        html = engine.fetch_text(url=url, **kwargs)
        return QidianHTMLParser.parse_novel_info(html, url=url)

    def fetch_chapter_list(self, url, engine, **kwargs) -> Chapters:
        url = url.url if isinstance(url, Novel) else url
        html = engine.fetch_text(url=url, **kwargs)
        return QidianHTMLParser.parse_chapter_list(html, url=url)

    def fetch_chapter_content(
            self,
            chapter: Chapter,
            engine,
            **kwargs) -> Chapter | None:
        url = chapter.url
        html = engine.fetch_text(url=url, **kwargs)
        if BeautifulSoup(html, "lxml").find("div", class_="no-content"):
            raise ChapterNotFoundError("Qidian chapter page shows no-content div")
        result = QidianHTMLParser.parse_chapter_content(html, chapter)
        return result


class QidianRequestsFetcher(BaseFetcher):

    def fetch_search_result(self,
                            query: str,
                            engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        raise FeatureNotSupportedError("起点中文网不支持 Requests 获取搜索结果")

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        html = engine.fetch_text(url=url, **kwargs)
        return QidianHTMLParser.parse_novel_info(html, url=url)

    def fetch_chapter_list(self, url, engine, **kwargs) -> Chapters:
        url = url.url if isinstance(url, Novel) else url
        html = engine.fetch_text(url=url, **kwargs)
        return QidianHTMLParser.parse_chapter_list(html, url=url)

    def fetch_chapter_content(
            self,
            chapter: Chapter,
            engine,
            **kwargs) -> Chapter | None:
        url = chapter.url
        html = engine.fetch_text(url=url, **kwargs)
        if BeautifulSoup(html, "lxml").find("div", class_="no-content"):
            raise ChapterNotFoundError(f"Qidian chapter page shows no-content div: {chapter.url}")
        result = QidianHTMLParser.parse_chapter_content(html, chapter)
        return result


def use_fetcher(engine) -> type[QidianRequestsFetcher | QidianBrowserFetcher]:
    if engine.name == "browser":
        return QidianBrowserFetcher
    elif engine.name == "requests":
        return QidianRequestsFetcher
    elif engine.name == "API":
        raise FeatureNotSupportedError("起点中文网不支持 API 模式")
    else:
        raise ValueError(f"Unknown engine: {engine.name!r}")


class QidianFetcher(BaseFetcher):
    host = ("www.qidian.com", "book.qidian.com")
    id_pattern = re.compile(r"^(?:/(book|info)/?)?(\d{10})/?$")

    def login(self, engine: BrowserEngine, **kwargs) -> AuthCredential:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.login(engine=engine, **kwargs)

    def fetch_search_result(self,
                            query: str,
                            engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_search_result(query=query, engine=engine, **kwargs)

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_novel_info(url=url, engine=engine, **kwargs)

    def fetch_chapter_list(self, url, engine, **kwargs) -> Chapters:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_chapter_list(url=url, engine=engine, **kwargs)

    def fetch_chapter_content(
            self,
            chapter: Chapter,
            engine,
            **kwargs) -> Chapter | None:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_chapter_content(chapter=chapter, engine=engine, **kwargs)
