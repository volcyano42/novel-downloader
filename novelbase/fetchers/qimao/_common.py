"""七猫中文网（qimao.com）共享代码�?
包含 ID 标准化函数、HTML 解析函数、API URL 构建函数和日志器�?"""

import re
import requests

from box import Box
from bs4 import BeautifulSoup, Tag

from ...core.exceptions import ChapterNotFoundError, NovelNotFoundError, ParseError
from ...models.novel import Chapter, Chapters, Illustration, Novel, SearchResult
from ...utils.logger import get_logger

_log = get_logger("novelbase.fetchers.qimao")


# ---------------------------------------------------------------------------
# ID 标准�?# ---------------------------------------------------------------------------

def standardize_id(ref: str | Novel | Chapter) -> str:
    """�?URL 或对象中提取 novelbase 内部使用�?ID�?
    对于七猫�?    - 小说 ID：纯数字（如 ``195958``�?    - 章节 ID：``book_id-chapter_id``（如 ``195958-499610``�?    """
    if isinstance(ref, Novel):
        ref = ref.url
    if isinstance(ref, Chapter):
        ref = ref.url

    if isinstance(ref, str):
        # 完整章节 URL�?shuku/195958-499610/
        if m := re.search(r"/shuku/(\d+-\d+)", ref):
            return m.group(1)
        # 小说 URL�?shuku/195958/
        if m := re.search(r"/shuku/(\d+)", ref):
            return m.group(1)
        # 裸数�?ID
        if m := re.match(r"^(\d+)$", ref):
            return m.group(1)
    raise ValueError(f"ref {ref} 不符合七�?ID 规范")


# ---------------------------------------------------------------------------
# HTML 解析
# ---------------------------------------------------------------------------

def parse_search_result(html: str) -> tuple[SearchResult, ...]:
    """解析搜索结果�?HTML�?""
    soup = BeautifulSoup(html, "lxml")
    results: list[SearchResult] = []

    items = soup.select("ul.search-book-list li.qm-cover-text-item")
    if not items:
        return ()

    for item in items:
        # 标题和链�?        title_a = item.select_one(".text-content .s-tit a")
        if not title_a:
            continue
        title = title_a.get_text(strip=True)
        url = title_a.get("href", "")

        # 作�?        author = ""
        author_a = item.select_one(".text-bottom-row .item-wrap .link")
        if author_a:
            author = author_a.get_text(strip=True)

        # 简�?        desc_span = item.select_one(".text-content .s-desc")
        description = desc_span.get_text(strip=True) if desc_span else ""

        results.append(SearchResult(
            title=title,
            author=author,
            url=url,
            description=description,
        ))

    return tuple(results)


def parse_novel_info(html: str, *, url: str = "") -> Novel:
    """解析小说详情�?HTML�?""
    soup = BeautifulSoup(html, "lxml")

    # 检测小说不存在：meta description 中出�?"undefined"
    meta_desc = soup.select_one('meta[data-hid="description"]')
    if meta_desc and 'content="《undefined�? in str(meta_desc):
        raise NovelNotFoundError("七猫小说不存在（meta �?undefined�?)

    # 书名
    title_span = soup.select_one(".book-information .wrap-txt .title .txt")
    if not title_span:
        raise NovelNotFoundError("七猫小说详情页缺少书名元�?)
    name = title_span.get_text(strip=True)

    # URL：优先传入的 url，其�?canonical
    book_url = url
    if not book_url:
        canonical = soup.select_one('link[rel="canonical"]')
        if canonical:
            book_url = canonical.get("href", "")

    # 作�?    author = ""
    author_tag = soup.select_one(".sub-title .txt em a")
    if author_tag:
        author = author_tag.get_text(strip=True)
    else:
        # fallback：meta author
        meta_author = soup.select_one('meta[name="author"]')
        if meta_author:
            author = meta_author.get("content", "")

    # 状态标�?    tags: list[str] = []
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
        # 格式�?"876.92�? �?"151.62万字"
        try:
            if "�? in word_str:
                count_word = int(float(word_str.replace("�?, "").replace("�?, "")) * 10000)
            else:
                count_word = int(re.sub(r"[^\d]", "", word_str) or "0")
        except (ValueError, TypeError):
            count_word = 0

    # 简�?    intro_p = soup.select_one(".book-introduction .intro")
    abstract = intro_p.get_text(strip=True) if intro_p else ""

    # 封面
    cover_img = soup.select_one(".wrap-pic img")
    cover_url = cover_img.get("src", "") if cover_img else ""
    try:
        cover_data = requests.get(cover_url, timeout=10).content if cover_url else b""
    except requests.RequestException:
        cover_data = b""
    cover = Illustration(raw_data=cover_data, alt=name, url=cover_url)

    # 章节�?�?�?tab 中读�?    serial = 0
    chapter_tab = soup.select_one(".qm-tab-list-item .sub-txt")
    if chapter_tab:
        tab_text = chapter_tab.get_text(strip=True)
        try:
            serial = int(re.sub(r"[^\d]", "", tab_text) or "0")
        except ValueError:
            serial = 0
    if serial == 0:
        # fallback: 直接数章�?li 数量
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


def parse_chapter_list(html: str, *, novel_id: str = "") -> Chapters:
    """解析章节目录�?
    七猫的章节目录在小说详情页的「作品目录」tab 中，
    �?tab 内容由客户端 JS 动态加载，初始 SSR HTML 中可能不包含�?    本方法优先尝试主目录（qm-book-catalog-list-content），
    若未找到则回退到阅读页侧边栏目录（book-catalog-list-content）�?    """
    soup = BeautifulSoup(html, "lxml")

    # 检测页面是否有�?    meta_desc = soup.select_one('meta[data-hid="description"]')
    if meta_desc and 'content="《undefined�? in str(meta_desc):
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


def parse_chapter_content(html: str, chapter: Chapter) -> Chapter | None:
    """解析章节正文内容�?""
    soup = BeautifulSoup(html, "lxml")

    # 检测章节不存在：标题为空且字数�?0
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
        raise ChapterNotFoundError("七猫章节不存在（标题与字数均为空�?)

    # 更新章节标题
    if chapter_title:
        chapter.title = chapter_title

    # 检测章节不完整（VIP/需登录/APP 专享�?    if soup.select_one(".reader-login-code") or soup.select_one(".show-part"):
        return None

    # 提取正文
    article_div = soup.select_one(".chapter-detail-article .article")
    if not article_div:
        raise ParseError("七猫章节页缺少正文容�?.article")

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


# ---------------------------------------------------------------------------
# Rain API 辅助
# ---------------------------------------------------------------------------

def _api_url(engine, **params) -> str:
    """构建 Rain API 请求 URL�?""
    key = engine.options.key
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"https://v3.rain.ink/qimao/?apikey={key}&{qs}"
