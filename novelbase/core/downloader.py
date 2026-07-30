from typing import Sequence, TypeVar, Callable

from .engine import BrowserEngine
from .exceptions import SourceNotFoundError
from .options import ExportOptions
from ..models.auth import AuthCredential
from ..models.novel import Novel, Chapter, Chapters, SearchResult
from ..utils.logger import get_logger

_T = TypeVar('_T')

_log = get_logger("novelbase.core.downloader")


def _normalize_mode(engine) -> str:
    """从 engine 获取标准化的 mode 名（小写）。"""
    return (engine.mode if hasattr(engine, 'mode') else engine.name).lower()


def _provider_for(engine) -> str | None:
    """获取 API engine 的 provider 名，非 API 返回 None。"""
    if _normalize_mode(engine) == "api":
        opts = getattr(engine, 'options', None)
        if opts is not None:
            return getattr(opts, 'name', None)
    return None


def get_source(url: str) -> str | None:
    """根据 URL 查找匹配的 source 名称。"""
    from ..utils.registry import register_source
    from yarl import URL
    parsed = URL(url)
    for name, info in register_source().items():
        if parsed.host in info["hosts"]:
            return name
    return None


def get_source_for_id(novel_id: str) -> str | None:
    """根据裸 novel_id 查找匹配的 source 名称。"""
    from ..utils.registry import register_source
    for name, info in register_source().items():
        pat = info.get("id_pattern")
        if pat and pat.match(novel_id):
            return name
    return None


def list_sources() -> list[str]:
    """返回所有已注册的 source 名称。"""
    from ..utils.registry import register_source
    return sorted(register_source().keys())


def get_exporters() -> dict[str, Callable]:
    """返回所有已注册的导出函数（{format: export_func}）。"""
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
           skip_delay: bool = False,
           **kwargs) -> tuple[SearchResult, ...]:
    """搜索小说。

    Args:
        platform: 平台标识（如 ``"fanqie"``），传 ``"all"`` 时全平台搜索。
        query:    搜索关键词。
        engine:   下载引擎实例。
        skip_delay: 跳过请求间延迟。
    """
    from ..utils.registry import resolve as _resolve

    mode = _normalize_mode(engine)
    provider = _provider_for(engine)

    if platform == "all":
        all_results: list[SearchResult] = []
        for name in list_sources():
            try:
                fn = _resolve(name, mode, "search", provider=provider)
                kwargs["skip_delay"] = skip_delay
                results = fn(query=query, engine=engine, **kwargs)
                for r in results:
                    r.platform = name
                all_results.extend(results)
            except Exception:
                pass
        return tuple(all_results)

    try:
        fn = _resolve(platform, mode, "search", provider=provider)
    except (ValueError, ImportError):
        raise SourceNotFoundError(f"source not found: {platform}")
    kwargs["skip_delay"] = skip_delay
    results = fn(query=query, engine=engine, **kwargs)
    for r in results:
        r.platform = platform
    return results


def login(platform: str, engine: BrowserEngine) -> AuthCredential:
    """登录指定平台。

    Args:
        platform: 平台标识。
        engine:   下载引擎实例。
    """
    from ..utils.registry import resolve as _resolve

    mode = _normalize_mode(engine)
    try:
        fn = _resolve(platform, mode, "login")
    except (ValueError, ImportError):
        raise SourceNotFoundError(f"source not found: {platform}")
    return fn(engine=engine)


def resolve_meta(url: str, engine, skip_delay: bool = False, **kwargs) -> Novel:
    """获取小说元数据。

    Args:
        url: 小说页面 URL。
        engine: 下载引擎实例。
        skip_delay: 跳过请求间延迟。

    Returns:
        包含书名、作者、简介、封面等信息的 Novel 对象。
    """
    from ..utils.registry import resolve as _resolve

    name = get_source(url)
    if name is None:
        raise SourceNotFoundError(f"source not found for: {url}")

    mode = _normalize_mode(engine)
    provider = _provider_for(engine)
    kwargs["skip_delay"] = skip_delay
    fn = _resolve(name, mode, "novel_info", provider=provider)
    return fn(url=url, engine=engine, **kwargs)


def resolve_chapter_list(url: str, engine, skip_delay: bool = False, **kwargs) -> Chapters:
    """获取章节列表。

    Args:
        url: 小说页面 URL。
        engine: 下载引擎实例。
        skip_delay: 跳过请求间延迟。

    Returns:
        按 order 排序的章节列表。
    """
    from ..utils.registry import resolve as _resolve

    name = get_source(url)
    if name is None:
        raise SourceNotFoundError(f"source not found for: {url}")

    mode = _normalize_mode(engine)
    provider = _provider_for(engine)
    kwargs["skip_delay"] = skip_delay
    fn = _resolve(name, mode, "chapter_list", provider=provider)
    return fn(url=url, engine=engine, **kwargs)


def resolve_chapter(chapter: Chapter, engine, skip_delay: bool = False, **kwargs) -> Chapter | None:
    """下载单个章节。

    Args:
        chapter: 要下载的章节。
        engine:  下载引擎实例。
        skip_delay: 跳过请求间延迟。

    Returns:
        已填充的 Chapter，章节不可获取时返回 None。
    """
    from ..utils.registry import resolve as _resolve

    name = get_source_for_id(chapter.novel_id)
    # 回退：novel_id 不带前缀时用 chapter.url 查找
    if name is None:
        name = get_source(chapter.url)
    if name is None:
        raise SourceNotFoundError(f"source not found for novel_id: {chapter.novel_id}")

    mode = _normalize_mode(engine)
    provider = _provider_for(engine)
    kwargs["skip_delay"] = skip_delay
    fn = _resolve(name, mode, "chapter_content", provider=provider)
    return fn(chapter=chapter, engine=engine, **kwargs)


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

    export_func = register_exporter().get(fmt)
    if export_func is None:
        return

    return export_func(novel.chapters, novel, options=opt, **kwargs)
