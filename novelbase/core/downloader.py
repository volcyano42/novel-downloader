from typing import Iterable, Sequence, TypeVar

from .engine import BrowserEngine, APIEngine, RequestsEngine
from .exceptions import FetcherNotFoundError
from .options import Options, ExportOptions
from .storage import BaseStorage, create_storage
from ..exporters.base import BASEExporter
from ..models.auth import AuthCredential
from ..models.novel import Novel, Chapter, Chapters, SearchResult
from ..fetchers.base import BaseFetcher
from ..utils.logger import get_logger

_T = TypeVar('_T')

_log = get_logger("novelbase.core.downloader")

def get_fetcher_for_url(url: str):
    """根据 URL 查找匹配的 Fetcher 类。"""
    from ..utils.registry import register_fetcher
    from yarl import URL
    parsed = URL(url)
    for fetcher_cls in register_fetcher().values():
        if parsed.host in fetcher_cls.host:
            return fetcher_cls
    return None


def get_fetcher_for_id(novel_id: str):
    """根据裸 novel_id 查找匹配的 Fetcher 类。

    遍历所有已注册 Fetcher 的 ``id_pattern``，命中则返回该类。
    ``id_pattern`` 须包含一个捕获组，调用方通过 ``.group(1)`` 提取纯净 ID。
    """
    from ..utils.registry import register_fetcher
    for fetcher_cls in register_fetcher().values():
        if fetcher_cls.id_pattern and fetcher_cls.id_pattern.match(novel_id):
            return fetcher_cls
    return None


def get_fetchers() -> dict[str, type[BaseFetcher]]:
    """返回所有已注册的 Fetcher 类（{platform: FetcherCls}）。"""
    from ..utils.registry import register_fetcher
    return register_fetcher()


def get_exporters() -> dict[str, type[BASEExporter]]:
    """返回所有已注册的 Exporter 类（{format: ExporterCls}）。"""
    from ..utils.registry import register_exporter
    return register_exporter()


def get_exporter_options() -> dict[str, type[ExportOptions]]:
    from ..utils.registry import register_export_options
    return register_export_options()


def split_into_groups(target: Sequence[_T], group: int) -> tuple[Sequence[_T], ...]:
    """将章节列表按批次大小分组。"""
    return tuple(target[i:i + group] for i in range(0, len(target), group))


def search(platform: str,
           query: str,
           engine,
           page: int = 1,
           skip_delay: bool = False,
           **kwargs) -> tuple[SearchResult, ...]:
    """搜索小说。

    Args:
        platform: 平台标识（如 ``"fanqie"``）。
        query:    搜索关键词。
        engine:   下载引擎实例。
        page:     页码，从 1 开始。
        skip_delay: 跳过请求间延迟。
    """
    fetcher_cls = get_fetchers().get(platform)
    if fetcher_cls is None:
        raise FetcherNotFoundError(f"fetcher not found: {platform}")
    fetcher = fetcher_cls()
    kwargs["page"] = page
    kwargs["skip_delay"] = skip_delay
    return fetcher.fetch_search_result(query=query, engine=engine, **kwargs)


def login(platform: str, engine: BrowserEngine) -> AuthCredential:
    """登录指定平台。

    Args:
        platform: 平台标识。
        engine:   下载引擎实例。
    """
    fetcher_cls = get_fetchers().get(platform)
    if fetcher_cls is None:
        raise FetcherNotFoundError(f"fetcher not found: {platform}")
    fetcher = fetcher_cls()
    return fetcher.login(engine=engine)

def fetch_meta(url: str, engine, skip_delay: bool = False, **kwargs) -> Novel:
    """获取小说元数据。

    Args:
        url: 小说页面 URL。
        engine: 下载引擎实例。
        skip_delay: 跳过请求间延迟。

    Returns:
        包含书名、作者、简介、封面等信息的 Novel 对象。
    """
    fetcher_cls = get_fetcher_for_url(url)
    if fetcher_cls is None:
        raise FetcherNotFoundError(f"fetcher not found for: {url}")
    kwargs["skip_delay"] = skip_delay
    return fetcher_cls().fetch_novel_info(url=url, engine=engine, **kwargs)


def fetch_chapter_list(url: str, engine, skip_delay: bool = False, **kwargs) -> Chapters:
    """获取章节列表。

    Args:
        url: 小说页面 URL。
        engine: 下载引擎实例。
        skip_delay: 跳过请求间延迟。

    Returns:
        按 order 排序的章节列表。
    """
    fetcher_cls = get_fetcher_for_url(url)
    if fetcher_cls is None:
        raise FetcherNotFoundError(f"fetcher not found for: {url}")
    kwargs["skip_delay"] = skip_delay
    return fetcher_cls().fetch_chapter_list(url=url, engine=engine, **kwargs)


def resolve_chapter(chapter: Chapter, engine, fetcher=None, skip_delay: bool = False, **kwargs) -> Chapter | None:
    """下载单个章节。

    Args:
        chapter: 要下载的章节。
        engine:  下载引擎实例。
        fetcher: 可选抓取器实例。为 None 时自动从章节 novel_id 解析。
        skip_delay: 跳过请求间延迟。

    Returns:
        已填充的 Chapter，章节不可获取时返回 None。
    """
    if fetcher is None:
        fetcher_cls = get_fetcher_for_id(chapter.novel_id)
        if fetcher_cls is None:
            raise FetcherNotFoundError(f"fetcher not found for novel_id: {chapter.novel_id}")
        fetcher = fetcher_cls()
    kwargs["skip_delay"] = skip_delay
    return fetcher.fetch_chapter_content(chapter=chapter, engine=engine, **kwargs)


def export(novel: Novel, options: ExportOptions | None = None, format: str | None = None, **kwargs):
    """导出小说。

    Args:
        novel:   要导出的小说。
        options: 导出选项。
        format:  可选导出格式覆盖。
    """
    from ..utils.registry import register_exporter

    opt = options
    if opt is None or not opt.enabled:
        return

    fmt = format or opt.format
    if not fmt:
        return

    exporter_cls = register_exporter().get(fmt)
    if exporter_cls is None:
        return

    exporter = exporter_cls(options=opt)
    exporter.export(novel.chapters, novel, **kwargs)
