import asyncio
from typing import Sequence, TypeVar, Callable

from .exceptions import SourceNotFoundError
from .options import ExportOptions
from ..models.novel import Novel, Chapter, Chapters, SearchResult
from ..utils.logger import get_logger
from ..utils.urls import make_novel_id

_T = TypeVar('_T')

_log = get_logger("novelbase.core.downloader")


def get_exporters() -> dict[str, Callable]:
    """返回所有已注册的导出函数（{format: export_func}）。"""
    from ..exporter import register_exporter
    return register_exporter()


def get_exporter_options() -> dict[str, type[ExportOptions]]:
    from ..exporter import register_export_options
    return register_export_options()


def split_into_groups(target: Sequence[_T], group: int) -> tuple[Sequence[_T], ...]:
    """将章节列表按批次大小分组。"""
    return tuple(target[i:i + group] for i in range(0, len(target), group))


async def search(sources: Sequence[str], query: str, engines,
                 skip_delay: bool = False, mode_overrides: dict[str, str] | None = None,
                 **kwargs) -> tuple[SearchResult, ...]:
    """并发搜索给定书源；单个书源失败静默跳过。

    `mode_overrides`（能力名 → mode）覆盖书源声明的 mode，用于用户层配置。
    """
    from ..source import resolve as _resolve

    async def _one(name: str) -> list[SearchResult]:
        fn, mode = _resolve(name, "search")
        mode = (mode_overrides or {}).get("search") or mode
        kwargs["skip_delay"] = skip_delay
        results = await fn(query=query, engine=engines(mode), **kwargs)
        for r in results:
            r.source_name = name
        return list(results)

    gathered = await asyncio.gather(*(_one(n) for n in sources), return_exceptions=True)
    out: list[SearchResult] = []
    for item in gathered:
        if isinstance(item, Exception):
            _log.warning("search failed for one source: %s", item)
            continue
        out.extend(item)
    return tuple(out)


async def resolve_meta(url: str, source_name: str, engines, skip_delay: bool = False,
                       mode_overrides: dict[str, str] | None = None, **kwargs) -> Novel:
    from ..source import resolve as _resolve

    try:
        fn, mode = _resolve(source_name, "novel_info")
    except (ValueError, ImportError) as e:
        raise SourceNotFoundError(f"source not found: {source_name}") from e
    mode = (mode_overrides or {}).get("novel_info") or mode
    kwargs["skip_delay"] = skip_delay
    novel = await fn(url=url, engine=engines(mode), **kwargs)
    novel.id = make_novel_id(novel.url)
    return novel


async def resolve_chapter_list(url: str, source_name: str, engines, skip_delay: bool = False,
                               mode_overrides: dict[str, str] | None = None, **kwargs) -> Chapters:
    from ..source import resolve as _resolve

    fn, mode = _resolve(source_name, "chapter_list")
    mode = (mode_overrides or {}).get("chapter_list") or mode
    kwargs["skip_delay"] = skip_delay
    return await fn(url=url, engine=engines(mode), **kwargs)


async def resolve_chapter(chapter: Chapter, source_name: str, engines, skip_delay: bool = False,
                          mode_overrides: dict[str, str] | None = None, **kwargs) -> Chapter | None:
    from ..source import resolve as _resolve

    fn, mode = _resolve(source_name, "chapter_content")
    mode = (mode_overrides or {}).get("chapter_content") or mode
    kwargs["skip_delay"] = skip_delay
    return await fn(chapter=chapter, engine=engines(mode), **kwargs)


def export(novel: Novel, options: ExportOptions | None = None, format: str | None = None, **kwargs):
    """导出小说。

    Args:
        novel:   要导出的小说。
        options: 导出选项。
        format:  可选导出格式覆盖。
    """
    from ..exporter import register_exporter

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
