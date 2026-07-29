from .core.downloader import (
    resolve_meta,
    resolve_chapter_list,
    resolve_chapter,
    export,
    get_source,
    get_source_for_id,
    get_exporters,
    get_exporter_options,
    split_into_groups,
    search,
    login,
)
from .core.engine import create_engine
from .core.exceptions import (
    NovelDownloaderError,
    NetworkError,
    AuthenticationError,
    NovelNotFoundError,
    ChapterNotFoundError,
    ParseError,
    SourceNotFoundError,
    FeatureNotSupportedError,
    StorageError,
    AntiCrawlError,
)
from .core.options import (
    Options,
    APIOptions,
    BrowserOptions,
    RequestsOptions,
    StorageOptions,
    ExportOptions,
)
from .core.storage import LocalStorage
from .models.novel import Novel, Chapter, Chapters, Illustration, SearchResult
from .utils.registry import capabilities, resolve, list_sources as _list_registry_sources
from .utils.hooks import SourceHooks

__version__ = "4.0.0"

def list_sources():
    """列出所有可用 source 名称。"""
    from .core.downloader import list_sources as _ls
    return _ls()


__all__ = [
    "resolve_meta",
    "resolve_chapter_list",
    "resolve_chapter",
    "export",
    "create_engine",
    "get_source",
    "get_source_for_id",
    "get_exporters",
    "get_exporter_options",
    "split_into_groups",
    "search",
    "login",
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
    "capabilities",
    "resolve",
    "SourceHooks",
]
