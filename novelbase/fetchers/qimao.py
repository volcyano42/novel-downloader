import re
import time
import json
import requests
from typing import Sequence

from box import Box
from bs4 import BeautifulSoup, Tag

from .base import BaseFetcher
from ..core.exceptions import ChapterNotFoundError, FeatureNotSupportedError, NovelNotFoundError, ParseError
from ..models.auth import AuthCredential
from ..models.novel import Novel, Chapter, SearchResult, Illustration, Chapters
from ..utils.logger import get_logger

_log = get_logger("novelbase.fetchers.qimao")


def standardize_id(ref: str | Novel | Chapter) -> str:
    """从 URL 或对象中提取 novelbase 内部使用的 ID。

    对于七猫：
    - 小说 ID：纯数字（如 ``195958``）
    - 章节 ID：``book_id-chapter_id``（如 ``195958-499610``）
    """
    if isinstance(ref, Novel):
        ref = ref.url
    if isinstance(ref, Chapter):
        ref = ref.url

    if isinstance(ref, str):
        # 完整章节 URL：/shuku/195958-499610/
        if m := re.search(r"/shuku/(\d+-\d+)", ref):
            return m.group(1)
        # 小说 URL：/shuku/195958/
        if m := re.search(r"/shuku/(\d+)", ref):
            return m.group(1)
        # 裸数字 ID
        if m := re.match(r"^(\d+)$", ref):
            return m.group(1)
    raise ValueError(f"ref {ref} 不符合七猫 ID 规范")


class QimaoHTMLParser:
    """七猫中文网 HTML 解析器。

    七猫使用 Nuxt SSR 渲染，所有数据直接嵌入 HTML 中，
    无需额外的 JSON 提取步骤。
    """

    # ---------- 搜索 ----------

    @staticmethod
    def parse_search_result(html: str) -> tuple[SearchResult, ...]:
        """解析搜索结果页 HTML。"""
        soup = BeautifulSoup(html, "lxml")
        results: list[SearchResult] = []

        items = soup.select("ul.search-book-list li.qm-cover-text-item")
        if not items:
            return ()

        for item in items:
            # 标题和链接
            title_a = item.select_one(".text-content .s-tit a")
            if not title_a:
                continue
            title = title_a.get_text(strip=True)
            url = title_a.get("href", "")

            # 作者
            author = ""
            author_a = item.select_one(".text-bottom-row .item-wrap .link")
            if author_a:
                author = author_a.get_text(strip=True)

            # 简介
            desc_span = item.select_one(".text-content .s-desc")
            description = desc_span.get_text(strip=True) if desc_span else ""

            results.append(SearchResult(
                title=title,
                author=author,
                url=url,
                description=description,
            ))

        return tuple(results)

    # ---------- 小说详情 ----------

    @staticmethod
    def parse_novel_info(html: str, *, url: str = "") -> Novel:
        """解析小说详情页 HTML。"""
        soup = BeautifulSoup(html, "lxml")

        # 检测小说不存在：meta description 中出现 "undefined"
        meta_desc = soup.find("meta", attrs={"data-hid": "description"})
        if meta_desc and 'content="《undefined》' in str(meta_desc):
            raise NovelNotFoundError("七猫小说不存在（meta 含 undefined）")

        # 书名
        title_span = soup.select_one(".book-information .wrap-txt .title .txt")
        if not title_span:
            raise NovelNotFoundError("七猫小说详情页缺少书名元素")
        name = title_span.get_text(strip=True)

        # URL：优先传入的 url，其次 canonical
        book_url = url
        if not book_url:
            canonical = soup.find("link", rel="canonical")
            if canonical:
                book_url = canonical.get("href", "")

        # 作者
        author = ""
        author_tag = soup.select_one(".sub-title .txt em a")
        if author_tag:
            author = author_tag.get_text(strip=True)
        else:
            # fallback：meta author
            meta_author = soup.find("meta", attrs={"name": "author"})
            if meta_author:
                author = meta_author.get("content", "")

        # 状态标签
        tags: list[str] = []
        status_tag = soup.select_one(".qm-tag.tag.orange")
        if status_tag:
            status_text = status_tag.get_text(strip=True)
            tags.append(status_text)

        # 分类标签
        for tag_a in soup.select(".tags-wrap .qm-tag.tag a"):
            tag_text = tag_a.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)

        # 字数
        count_word = 0
        stats_ems = soup.select(".statistics-wrap .txt em")
        if stats_ems:
            word_str = stats_ems[0].get_text(strip=True)
            # 格式如 "876.92万" 或 "151.62万字"
            try:
                if "万" in word_str:
                    count_word = int(float(word_str.replace("万", "").replace("字", "")) * 10000)
                else:
                    count_word = int(re.sub(r"[^\d]", "", word_str) or "0")
            except (ValueError, TypeError):
                count_word = 0

        # 简介
        intro_p = soup.select_one(".book-introduction .intro")
        abstract = intro_p.get_text(strip=True) if intro_p else ""

        # 封面
        cover_img = soup.select_one(".wrap-pic img")
        cover_url = cover_img.get("src", "") if cover_img else ""
        try:
            cover_data = requests.get(cover_url, timeout=10).content if cover_url else b""
        except requests.RequestException:
            cover_data = b""
        cover = Illustration(raw_data=cover_data, alt=name, url=cover_url)

        # 章节数 — 从 tab 中读取
        serial = 0
        chapter_tab = soup.select_one(".qm-tab-list-item .sub-txt")
        if chapter_tab:
            tab_text = chapter_tab.get_text(strip=True)
            try:
                serial = int(re.sub(r"[^\d]", "", tab_text) or "0")
            except ValueError:
                serial = 0
        if serial == 0:
            # fallback: 直接数章节 li 数量
            chapter_items = soup.select(".book-catalog-list-content li a")
            serial = len(chapter_items)

        novel_id = standardize_id(book_url) if book_url else ""

        return Novel(
            url=book_url,
            id=novel_id,
            title=name,
            author=author,
            serial=serial,
            tags=tuple(tags),
            description=abstract,
            count=count_word,
            cover=cover,
        )

    # ---------- 章节目录 ----------

    @staticmethod
    def parse_chapter_list(html: str, *, novel_id: str = "") -> Chapters:
        """解析章节目录。

        七猫的章节目录在小说详情页的「作品目录」tab 中，
        该 tab 内容由客户端 JS 动态加载，初始 SSR HTML 中可能不包含。
        本方法优先尝试主目录（qm-book-catalog-list-content），
        若未找到则回退到阅读页侧边栏目录（book-catalog-list-content）。
        """
        soup = BeautifulSoup(html, "lxml")

        # 检测页面是否有效
        meta_desc = soup.find("meta", attrs={"data-hid": "description"})
        if meta_desc and 'content="《undefined》' in str(meta_desc):
            raise ChapterNotFoundError("七猫小说不存在，无法获取目录")

        # 优先：小说详情页「作品目录」tab（完整章节列表）
        chapter_items = soup.select(".qm-book-catalog-list-content li a")
        if not chapter_items:
            # 回退：阅读页侧边栏目录（仅包含部分章节）
            chapter_items = soup.select(".book-catalog-list-content li a")

        results: list[Chapter] = []
        for order, a_tag in enumerate(chapter_items, start=1):
            title_span = a_tag.select_one("span.txt")
            title = title_span.get_text(strip=True) if title_span else ""
            chapter_url = a_tag.get("href", "")
            if not chapter_url:
                continue

            # 构建完整 URL
            if chapter_url.startswith("/"):
                chapter_url = f"https://www.qimao.com{chapter_url}"

            chapter_id = standardize_id(chapter_url)

            results.append(Chapter(
                id=chapter_id,
                url=chapter_url,
                novel_id=novel_id,
                title=title,
                order=order,
            ))

        return Chapters(results)

    # ---------- 章节正文 ----------

    @staticmethod
    def parse_chapter_content(html: str, chapter: Chapter) -> Chapter | None:
        """解析章节正文内容。"""
        soup = BeautifulSoup(html, "lxml")

        # 检测章节不存在：标题为空且字数为 0
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
            raise ChapterNotFoundError("七猫章节不存在（标题与字数均为空）")

        # 更新章节标题
        if chapter_title:
            chapter.title = chapter_title

        # 检测章节不完整（VIP/需登录/APP 专享）
        if soup.select_one(".reader-login-code") or soup.select_one(".show-part"):
            return None

        # 提取正文
        article_div = soup.select_one(".chapter-detail-article .article")
        if not article_div:
            raise ParseError("七猫章节页缺少正文容器 .article")

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

class QimaoBrowserFetcher(BaseFetcher):
    """浏览器引擎（Playwright）获取器。"""

    def login(self, engine, **kwargs) -> AuthCredential:
        _log.info("七猫浏览器登录开始")
        page = engine.new_page()

        try:
            page.get("https://www.qimao.com/")
            print("请在打开的浏览器窗口中完成登录（扫码/手机号）...")
            deadline = time.time() + 120
            while time.time() < deadline:
                if "user" in page.url:
                    break
                time.sleep(0.5)
            time.sleep(2)
            _log.info("七猫登录完成")

            raw_cookies = page.cookies()
            cookies = {c["name"]: c["value"] for c in raw_cookies}
            return AuthCredential(cookies=cookies, headers={}, extra={})
        finally:
            page.close()

    def fetch_search_result(self, query: str, engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        _log.debug("七猫搜索: ref=%s", query)
        search_url = f"https://www.qimao.com/search/index/?keyword={query}"
        html = engine.fetch_text(url=search_url, **kwargs)
        return QimaoHTMLParser.parse_search_result(html)

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        novel_id = standardize_id(url)
        url = f"https://www.qimao.com/shuku/{novel_id}/"
        html = engine.fetch_text(url=url, **kwargs)
        return QimaoHTMLParser.parse_novel_info(html, url=url)

    def fetch_chapter_list(self, url: str, engine, **kwargs) -> Chapters:
        novel_id = standardize_id(url)
        url = f"https://www.qimao.com/shuku/{novel_id}/"
        # 浏览器引擎：需要点击「作品目录」tab 以触发章节加载
        page = engine.new_page()
        try:
            page.get(url)
            catalog_tab = page.ele(".tab-inner")
            if catalog_tab:
                catalog_tab.click()
                page.wait(3)
            html = page.html
        finally:
            page.close()
        return QimaoHTMLParser.parse_chapter_list(html, novel_id=standardize_id(url))

    def fetch_chapter_content(self, chapter: Chapter, engine,
                              **kwargs) -> Chapter | None:
        html = engine.fetch_text(url=chapter.url, **kwargs)
        result = QimaoHTMLParser.parse_chapter_content(html, chapter)
        return result

class QimaoRainFetcher(BaseFetcher):

    def login(self, engine, **kwargs):
        raise FeatureNotSupportedError("Not Supported login by the Rain API")

    @staticmethod
    def _api_url(engine, **params) -> str:
        key = engine.options.key
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"https://v3.rain.ink/qimao/?apikey={key}&{qs}"

    def fetch_search_result(self,
                            query: str,
                            engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        page = kwargs.pop("page", 1)
        results: list[SearchResult] = []
        offset = (page - 1) * 10
        url = QimaoRainFetcher._api_url(engine, type=1, keywords=query, page=offset)
        content = engine.fetch_json(url, **kwargs)

        if content.get("code") != 0 and str(content.get("code")) != "0":
            return ()

        books = None
        if "search_tabs" in content:
            for tab in content["search_tabs"]:
                if tab.get("data") is not None:
                    books = tab["data"]
                    break
        if books is None:
            books = content.get("data")

        if not books or not isinstance(books, list):
            return ()

        for item in books:
            if "book_data" in item and isinstance(item["book_data"], list) and len(item["book_data"]) > 0:
                book = item["book_data"][0]
            else:
                book = item

            book_id = book.get("book_id")
            book_url = f"https://www.qimao.com/shuku/{book_id}/"
            book_name = book.get("book_name")
            author = book.get("author")
            description = book.get("abstract")

            results.append(SearchResult(
                title=book_name,
                author=author,
                url=book_url,
                description=description,
                extras=Box(rating=book.get('score'))
            ))
        return tuple(results)

    def fetch_novel_info(self, url, engine, **kwargs) -> Novel:

        novel_id = standardize_id(url)
        url = QimaoRainFetcher._api_url(engine, type=2, bookid=novel_id)
        json_data = engine.fetch_json(url, **kwargs)

        if json_data.get("code") != 0 and str(json_data.get("code")) != "0":
            raise NovelNotFoundError()

        data = json_data.get("data")
        if not data:
            raise NovelNotFoundError()

        book_url = f"https://www.qimao.com/shuku/{data.get('book_id')}/"
        name = data.get("book_name")

        author = ""
        author_info = data.get("author_info")
        if author_info and isinstance(author_info, dict):
            author = author_info.get("user_name", "")
        if not author:
            try:
                original_authors = json.loads(data.get("original_authors", "[]"))
                if original_authors:
                    author = original_authors[0].get("AuthorName", "")
            except (json.JSONDecodeError, IndexError):
                pass

        serial = int(data.get("serial_count", 0))
        word_number = int(data.get("word_number", 0))

        cover_url = data.get("thumb_url", "")
        try:
            book_cover_data = requests.get(cover_url, timeout=10).content if cover_url else b""
        except requests.RequestException:
            book_cover_data = b""
        novel_image = Illustration(raw_data=book_cover_data, alt=name, url=cover_url)

        tags: list[str] = []
        status = data.get("status", "0")
        tags.append("连载中" if status == "0" else "已完结")
        try:
            category_v2 = json.loads(data.get("category_v2", "[]"))
            for cat in category_v2:
                cat_name = cat.get("Name")
                if cat_name:
                    tags.append(cat_name)
        except json.JSONDecodeError:
            pass

        extras = Box(rating=data.get('score'))
        novel = Novel(url=book_url,
                      id=novel_id,
                      title=name,
                      serial=serial,
                      author=author,
                      count=word_number,
                      description=data.get("abstract", ""),
                      cover=novel_image,
                      tags=tuple(tags),
                      extras=extras,
                      )
        return novel

    def fetch_chapter_list(self, url, engine, **kwargs) -> Chapters:

        novel_id = standardize_id(url)
        url = QimaoRainFetcher._api_url(engine, type=3, bookid=novel_id)
        json_data = engine.fetch_json(url, **kwargs)

        if json_data.get("code") != 0 and str(json_data.get("code")) != "0":
            raise ChapterNotFoundError(f"Rain API returned error code: {json_data.get('code')}")

        item_data_list = json_data.get("data", {}).get("item_data_list")
        if not item_data_list:
            raise ChapterNotFoundError("Rain API returned empty chapter list")

        results: list[Chapter] = []
        for idx, chapter_item in enumerate(item_data_list, start=1):
            item_id = chapter_item.get("item_id")
            chapter_url = f"https://www.qimao.com/shuku/{novel_id}-{item_id}/"
            title: str = chapter_item.get("title", "")
            volume_name = chapter_item.get("volume_name", "")
            first_pass_time: float = chapter_item.get("first_pass_time", 0)
            chapter = Chapter(
                title=title,
                url=chapter_url,
                id=str(item_id),
                order=idx,
                novel_id=novel_id,
                volume=volume_name,
                time=first_pass_time,
            )
            results.append(chapter)
        return Chapters(results)

    def fetch_chapter_content(self, chapter: Chapter, engine, **kwargs) -> Chapter | None:
        """解析并填充content, count, (True)"""
        item_id = standardize_id(chapter)
        url = QimaoRainFetcher._api_url(engine, type=4, itemid=item_id)
        response = engine.fetch_json(url, **kwargs)

        if response.get("code") != 0 and str(response.get("code")) != "0":
            err_msg = response.get("data", {}).get("content", "Unknown error")
            raise ChapterNotFoundError(message=f"Chapter content error: {err_msg}")

        data = response.get("data", {})
        title = data.get("title", "")
        raw_content = data.get("content", "")
        content = raw_content.strip()
        content = content.replace("</p>", "\n\n")
        if content.startswith(title):
            content = content[len(title):].strip()

        chapter.content = content
        chapter.count = len(content)

        return chapter

class QimaoRequestsFetcher(BaseFetcher):
    """HTTP Requests 引擎获取器。

    注意：七猫的章节目录由客户端 JS 动态加载，初始 HTML 中可能不包含完整目录。
    若 SSR HTML 中缺失目录，会尝试从阅读页侧边栏获取（仅部分章节）。
    完整目录建议使用浏览器引擎。
    """

    def fetch_search_result(self, query: str, engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        page = kwargs.pop("page", 1)
        _log.debug("七猫搜索: ref=%s page=%s", query, page)
        if page > 1:
            search_url = f"https://www.qimao.com/search/index/?keyword={query}&page={page}"
        else:
            search_url = f"https://www.qimao.com/search/index/?keyword={query}"
        html = engine.fetch_text(url=search_url, **kwargs)
        return QimaoHTMLParser.parse_search_result(html)

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        novel_id = standardize_id(url)
        url = f"https://www.qimao.com/shuku/{novel_id}/"
        html = engine.fetch_text(url=url, **kwargs)
        return QimaoHTMLParser.parse_novel_info(html, url=url)

    def fetch_chapter_list(self, url: str, engine, **kwargs) -> Chapters:
        novel_id = standardize_id(url)
        url = f"https://www.qimao.com/shuku/{novel_id}/"
        html = engine.fetch_text(url=url, **kwargs)
        chapters = QimaoHTMLParser.parse_chapter_list(html, novel_id=standardize_id(url))
        if len(chapters) == 0:
            raise ChapterNotFoundError(
                "七猫章节目录未在初始 HTML 中找到（由 JS 动态加载），"
                "请使用浏览器引擎或提供目录页 HTML"
            )
        return chapters

    def fetch_chapter_content(self, chapter: Chapter, engine,
                              **kwargs) -> Chapter | None:
        html = engine.fetch_text(url=chapter.url, **kwargs)
        result = QimaoHTMLParser.parse_chapter_content(html, chapter)
        return result


def use_fetcher(engine) -> type[QimaoRequestsFetcher | QimaoBrowserFetcher | QimaoRainFetcher]:
    """根据引擎名称选择合适的获取器。"""
    if engine.name == "browser":
        return QimaoBrowserFetcher
    elif engine.name == "requests":
        return QimaoRequestsFetcher
    elif engine.name == "API":
        api_name = engine.options.name
        if api_name == "rain":
            return QimaoRainFetcher
        raise ValueError(
            f"Unsupported API backend: {api_name!r}. "
            f"Only 'rain' are supported."
        )
    else:
        raise ValueError(f"Unknown engine: {engine.name!r}")


class QimaoFetcher(BaseFetcher):
    """七猫中文网（www.qimao.com）小说获取器。

    支持 requests 和 browser 两种引擎。
    """

    host = ("www.qimao.com", "qimao.com")
    id_pattern = re.compile(r"^(?:/shuku/?)?(\d+)$")

    def login(self, engine, **kwargs) -> AuthCredential:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.login(engine=engine, **kwargs)

    def fetch_search_result(self, query: str, engine,
                            **kwargs) -> tuple[SearchResult, ...]:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_search_result(query=query, engine=engine,
                                           **kwargs)

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_novel_info(url=url, engine=engine, **kwargs)

    def fetch_chapter_list(self, url: str, engine, **kwargs) -> Chapters:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_chapter_list(url=url, engine=engine, **kwargs)

    def fetch_chapter_content(self, chapter: Chapter, engine,
                              **kwargs) -> Chapter | None:
        fetcher = use_fetcher(engine=engine)()
        return fetcher.fetch_chapter_content(chapter=chapter, engine=engine,
                                             **kwargs)
