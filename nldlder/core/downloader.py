from typing import Any, Sequence

from .engine import BrowserEngine
from .exceptions import (
    AntiCrawlError, ChapterNotFoundError, FeatureNotSupportedError,
    ParserNotFoundError,
)
from .options import Options
from .progress import DownloadProgress
from ..models.auth import AuthCredential
from ..models.novel import Novel, Chapter, Chapters, SearchResult
from ..parsers.base import BaseParser
from ..utils.logger import get_logger

_log = get_logger("nldlder.core.downloader")

# ═══════════════════════════════════════════════════════════════════
# 模块级工具函数（无状态，不依赖 NovelDownloader 实例）
# ═══════════════════════════════════════════════════════════════════

def get_parser_for_url(url: str):
    """根据 URL 查找匹配的 Parser 类。"""
    from ..utils.registry import register_parser
    for parser_cls in register_parser().values():
        if parser_cls.can_handle(url):
            return parser_cls
    return None


def get_parsers() -> dict[str, Any]:
    """返回所有已注册的 Parser 类（{platform: ParserCls}）。"""
    from ..utils.registry import register_parser
    return register_parser()


def get_exporters() -> dict[str, Any]:
    """返回所有已注册的 Exporter 类（{format: ExporterCls}）。"""
    from ..utils.registry import register_exporter
    return register_exporter()


def get_exporter_options() -> dict[str, Any]:
    from ..utils.registry import register_export_options
    return register_export_options()


def split_into_groups(target: Sequence, group: int) -> tuple[Sequence, ...]:
    """将章节列表按批次大小分组。"""
    return tuple(target[i:i + group] for i in range(0, len(target), group))


def search(platform: str,
           query: str,
           engine,
           page: int = 0) -> tuple[SearchResult, ...] | None:
    """搜索小说。

    Args:
        platform: 平台标识（如 ``"fanqie"``）。
        query:    搜索关键词。
        engine:   下载引擎实例。
        page:     页码（从 0 开始）。
    """
    parser_cls = get_parsers().get(platform)
    if parser_cls is None:
        raise ParserNotFoundError(f"parser not found: {platform}")
    parser = parser_cls()
    return parser.parse_search_info(search_ref=query, engine=engine,
                                    page=page)


def login(platform: str, engine: BrowserEngine) -> AuthCredential:
    """登录指定平台。

    Args:
        platform: 平台标识。
        engine:   下载引擎实例。
    """
    parser_cls = get_parsers().get(platform)
    if parser_cls is None:
        raise ParserNotFoundError(f"parser not found: {platform}")
    parser = parser_cls()
    if not isinstance(parser, BaseParser):
        raise FeatureNotSupportedError("login", f"Not Supported Platform: {platform}")
    return parser.login(engine=engine)


# ═══════════════════════════════════════════════════════════════════
# NovelDownloader — 下载编排器（无状态，不绑定小说）
# ═══════════════════════════════════════════════════════════════════

class NovelDownloader:
    """小说下载编排器。

    不持有 Novel 或 Parser 状态，每次调用独立解析。
    """

    def __init__(self,
                 engine,
                 *,
                 options: Options | None = None):
        """
        Args:
            engine:  下载引擎（由调用者创建和管理，可多实例共享）。
            options: 下载配置（影响 batch_size / max_workers 等）。
        """
        self._engine = engine
        self._options = options or Options()
        self._progress = DownloadProgress()

    # ── 公开 API ─────────────────────────────────────────────────

    def fetch_novel(self, url: str) -> Novel:
        """获取小说元数据。

        Args:
            url: 小说页面 URL。

        Returns:
            包含书名、作者、简介、封面等信息的 Novel 对象。
        """
        parser = self._resolve_parser(url)
        return parser.parse_novel_info(novel_ref=url, engine=self._engine)

    def fetch_chapter_list(self, novel: Novel) -> Chapters:
        """获取章节列表。

        Args:
            novel: 小说对象（需包含 url 属性供解析器识别平台）。

        Returns:
            按 order 排序的章节列表。
        """
        parser = self._resolve_parser(novel.url)
        return parser.parse_chapter_list(novel_ref=novel, engine=self._engine)

    def download_chapters(self,
                          chapters: Sequence[Chapter] | Chapter,
                          *,
                          parser=None) -> Chapters:
        """下载一批章节。

        Args:
            chapters: 要下载的章节列表。
            parser:   可选解析器实例。为 None 时自动从首个章节 URL 解析。

        Returns:
            已下载完成的章节（Chapters 对象）。
        """
        if not chapters:
            return Chapters()
        if isinstance(chapters, Chapter):
            chapters = [chapters]
        if parser is None:
            parser = self._resolve_parser(chapters[0].index_url)
        return parser.parse_chapter_content(chapter_ref=chapters, engine=self._engine)

    # ── 属性 ─────────────────────────────────────────────────────

    @property
    def engine(self) -> Any:
        return self._engine

    @property
    def progress(self) -> DownloadProgress:
        """当前批次的下载进度。"""
        return self._progress


    # ═══════════════════════════════════════════════════════════
    # 内部实现
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _resolve_parser(url: str):
        parser_cls = get_parser_for_url(url)
        if parser_cls is None:
            raise ParserNotFoundError(f"parser not found for: {url}")
        return parser_cls()

    @staticmethod
    def _get_chapter_content(chapters: Sequence[Chapter],
                             parser,
                             engine) -> Chapters:
        return parser.parse_chapter_content(chapter_ref=chapters, engine=engine)
