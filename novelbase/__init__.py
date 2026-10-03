from .core.downloader import (
    export,
    get_exporter_options,
    get_exporters,
    resolve_chapter,
    resolve_chapter_list,
    resolve_meta,
    search,
)
from .core.engine import create_engine
from .core.exceptions import (
    AntiCrawlError,
    AuthenticationError,
    ChapterNotFoundError,
    FeatureNotSupportedError,
    NetworkError,
    NovelDownloaderError,
    NovelNotFoundError,
    ParseError,
    SourceNotFoundError,
    StorageError,
)
from .core.options import (
    APIOptions,
    BrowserOptions,
    ExportOptions,
    Options,
    RequestsOptions,
    StorageOptions,
)
from .core.storage import LocalStorage
from .models.novel import Chapter, Chapters, Illustration, Novel, SearchResult
from .utils.hooks import SourceHooks

__version__ = "4.5.1"

def list_sources():
    """列出所有可用 source 名称。"""
    from .source import list_sources as _ls
    return _ls()


__all__ = [
    "resolve_meta",
    "resolve_chapter_list",
    "resolve_chapter",
    "export",
    "create_engine",
    "get_exporters",
    "get_exporter_options",
    "search",
    "list_sources",
    # 选项
    "Options",
    "APIOptions",
    "BrowserOptions",
    "RequestsOptions",
    "StorageOptions",
    "ExportOptions",
    "LocalStorage",
    # 异常
    "NovelDownloaderError",
    "NetworkError",
    "AuthenticationError",
    "NovelNotFoundError",
    "ChapterNotFoundError",
    "ParseError",
    "SourceNotFoundError",
    "FeatureNotSupportedError",
    "StorageError",
    "AntiCrawlError",
    # 模型
    "Novel",
    "Chapter",
    "Chapters",
    "Illustration",
    "SearchResult",
    # Registry
    "SourceHooks",
]
