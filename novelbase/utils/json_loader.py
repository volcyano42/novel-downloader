"""JSON 声明式规则加载器 — 纯 CSS 选择器驱动，零 Python 代码添加书源。

约定：
- 选择器以 `` @attr`` 结尾时提取属性值而非文本（如 ``"img @src"``）
- ``{query}`` / ``{novel_id}`` / ``{chapter_id}`` 在 URL 模板中替换
"""

import json
import re
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup, Tag

from novelbase.core.exceptions import ChapterNotFoundError, NovelNotFoundError
from novelbase.models.novel import Novel, Chapter, Chapters, SearchResult

# JSON 源文件搜索路径
_SOURCE_DIRS = [
    Path("app_data/sources"),
    Path(__file__).parent.parent.parent / "app_data" / "sources",  # 项目根
]


def _find_json(name: str) -> Path | None:
    """查找 JSON 源定义文件。"""
    for d in _SOURCE_DIRS:
        p = d / f"{name}.json"
        if p.exists():
            return p
    return None


def _load_json(name: str) -> dict[str, Any]:
    """加载 JSON 源定义。"""
    path = _find_json(name)
    if path is None:
        raise FileNotFoundError(f"JSON source not found: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _select_one(soup: BeautifulSoup, selector: str) -> str:
    """执行 CSS 选择器，返回文本或属性值。

    - ``"h1"`` → 元素文本
    - ``"img @src"`` → 属性值
    """
    attr: str | None = None
    if " @" in selector:
        selector, attr = selector.rsplit(" @", 1)
        selector = selector.strip()
        attr = attr.strip()

    el = soup.select_one(selector)
    if el is None:
        return ""
    if attr:
        return el.get(attr, "") or ""
    return el.get_text(strip=True)


def _select_all(soup: BeautifulSoup, selector: str) -> list[str]:
    """批量执行 CSS 选择器。"""
    attr: str | None = None
    if " @" in selector:
        selector, attr = selector.rsplit(" @", 1)
        selector = selector.strip()
        attr = attr.strip()

    results: list[str] = []
    for el in soup.select(selector):
        if attr:
            val = (el.get(attr) or "") if isinstance(el, Tag) else ""
            if val:
                results.append(val)
        else:
            results.append(el.get_text(strip=True))
    return results


def _resolve_url(template: str, **kwargs) -> str:
    """替换 URL 模板中的占位符。"""
    for k, v in kwargs.items():
        template = template.replace(f"{{{k}}}", str(v))
    return template


class JsonSourceFetcher:
    """基于 JSON 规则的动态 Fetcher。

    通过 CSS 选择器声明式定义 search / book_info / chapter_list /
    chapter_content 四个阶段的提取逻辑。
    """

    def __init__(self, name: str, rules: dict[str, Any]):
        self._name = name
        self._rules = rules

    # ── 搜索 ──

    def fetch_search_result(self, query: str, engine, **kwargs) -> tuple[SearchResult, ...]:
        rules = self._rules.get("search")
        if not rules:
            return ()

        url = _resolve_url(rules["url"], query=query)
        html = engine.fetch_text(url, **kwargs)
        soup = BeautifulSoup(html, "lxml")

        items = soup.select(rules["list_selector"])
        fields = rules.get("fields", {})

        results: list[SearchResult] = []
        for item in items:
            item_soup = BeautifulSoup(str(item), "lxml")
            title = _select_one(item_soup, fields.get("title", ""))
            author = _select_one(item_soup, fields.get("author", ""))
            item_url = _select_one(item_soup, fields.get("url", ""))
            description = _select_one(item_soup, fields.get("description", ""))
            cover_url = _select_one(item_soup, fields.get("cover_url", ""))

            if not title:
                continue

            results.append(SearchResult(
                title=title,
                author=author,
                url=item_url or "",
                description=description or None,
                cover_url=cover_url or None,
            ))
        return tuple(results)

    # ── 书籍信息 ──

    def fetch_novel_info(self, url: str, engine, **kwargs) -> Novel:
        rules = self._rules.get("book_info")
        if not rules:
            raise NovelNotFoundError(f"No book_info rules for {self._name}")

        html = engine.fetch_text(url, **kwargs)
        soup = BeautifulSoup(html, "lxml")

        title = _select_one(soup, rules.get("title", ""))
        author = _select_one(soup, rules.get("author", ""))
        description = _select_one(soup, rules.get("description", ""))
        cover_url = _select_one(soup, rules.get("cover_url", ""))

        tags_raw = _select_all(soup, rules.get("tags", ""))
        tags = tuple(tags_raw) if tags_raw else None

        # 用 URL 的 slug 生成 ID
        from hashlib import md5
        novel_id = md5(url.encode()).hexdigest()[:12]

        return Novel(
            title=title,
            author=author,
            url=url,
            id=novel_id,
            serial=0,
            description=description,
            tags=tags,
            cover=None,
        )

    # ── 章节目录 ──

    def fetch_chapter_list(self, url: str, engine, **kwargs) -> Chapters:
        rules = self._rules.get("chapter_list")
        if not rules:
            raise ChapterNotFoundError(f"No chapter_list rules for {self._name}")

        html = engine.fetch_text(url, **kwargs)
        soup = BeautifulSoup(html, "lxml")

        items = soup.select(rules["list_selector"])
        fields = rules.get("fields", {})

        from hashlib import md5
        novel_id = md5(url.encode()).hexdigest()[:12]

        chapters: list[Chapter] = []
        for i, item in enumerate(items, start=1):
            item_soup = BeautifulSoup(str(item), "lxml")
            ch_title = _select_one(item_soup, fields.get("title", ""))
            ch_url = _select_one(item_soup, fields.get("url", ""))

            if not ch_title:
                continue

            ch_id = md5(ch_url.encode()).hexdigest()[:12]
            chapters.append(Chapter(
                id=ch_id,
                url=ch_url or "",
                novel_id=novel_id,
                title=ch_title,
                order=i,
            ))

        return Chapters(chapters)

    # ── 章节正文 ──

    def fetch_chapter_content(self, chapter: Chapter, engine, **kwargs) -> Chapter | None:
        rules = self._rules.get("chapter_content")
        if not rules:
            return None

        html = engine.fetch_text(chapter.url, **kwargs)
        soup = BeautifulSoup(html, "lxml")

        content_el = soup.select_one(rules["content_selector"])
        if not content_el:
            raise ChapterNotFoundError(f"Content selector not found: {rules['content_selector']}")

        # 提取段落文本
        paragraphs: list[str] = []
        for p in content_el.select("p"):
            text = p.get_text(strip=True)
            if text:
                paragraphs.append(text)

        if not paragraphs:
            # 没有 p 标签，直接取整个元素的文本
            content = content_el.get_text("\n", strip=True)
        else:
            content = "\n\n".join(paragraphs)

        chapter.content = content
        chapter.count = len(content)
        return chapter


# ═══════════════════════════════════════════════════════════════════
# Registry 集成
# ═══════════════════════════════════════════════════════════════════

def load_source(name: str):
    """加载源定义 — 优先 Python 包，其次 JSON 规则。

    Returns:
        Fetcher 实例（BaseFetcher 子类或 JsonSourceFetcher）。
    """
    # 1. 尝试 Python 包
    from novelbase.utils.registry import register_fetcher
    fetchers = register_fetcher()
    fetcher_cls = fetchers.get(name)
    if fetcher_cls is not None:
        return fetcher_cls()

    # 2. 尝试 JSON 规则
    rules = _load_json(name)
    return JsonSourceFetcher(name, rules)


def list_json_sources() -> list[str]:
    """列出所有 JSON 规则定义的源名称。"""
    seen: set[str] = set()
    for d in _SOURCE_DIRS:
        if d.exists():
            for f in sorted(d.glob("*.json")):
                seen.add(f.stem)
    return sorted(seen)
