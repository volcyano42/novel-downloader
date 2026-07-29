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
    FetcherNotFoundError,
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
from .exporters.base import BASEExporter
from .models.novel import Novel, Chapter, Chapters, Illustration, SearchResult
from .utils.registry import capabilities, resolve, list_sources as _list_registry_sources
from .utils.hooks import SourceHooks

__version__ = "3.0.0"

# ── 向后兼容别名 ──────────────────────────────────────────────

fetch_meta = resolve_meta
fetch_chapter_list = resolve_chapter_list


def get_fetchers() -> dict:
    """DEPRECATED: use list_sources() instead."""
    from .core.downloader import list_sources as _ls
    return {k: type(k, (), {}) for k in _ls()}


def get_fetcher_for_url(url: str):
    """DEPRECATED: use get_source() instead."""
    from .core.downloader import get_source as _gs
    name = _gs(url)
    if name is None:
        return None
    from .utils.registry import register_source
    return register_source().get(name)


def get_fetcher_for_id(novel_id: str):
    """DEPRECATED: use get_source_for_id() instead."""
    from .core.downloader import get_source_for_id as _gsfi
    name = _gsfi(novel_id)
    if name is None:
        return None
    from .utils.registry import register_source
    return register_source().get(name)


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
    # 向后兼容
    "fetch_meta",
    "fetch_chapter_list",
    "get_fetcher_for_url",
    "get_fetcher_for_id",
    "get_fetchers",
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
    "FetcherNotFoundError",
    "FeatureNotSupportedError",
    "StorageError",
    "AntiCrawlError",
    # 模型
    "Novel",
    "Chapter",
    "Chapters",
    "Illustration",
    "SearchResult",
    "BASEExporter",
    # Registry
    "capabilities",
    "resolve",
    "SourceHooks",
]
