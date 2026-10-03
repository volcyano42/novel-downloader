from collections.abc import Callable

from ..models.novel import Chapter, Chapters, Novel, SearchResult
from ..utils.urls import make_novel_id
from .exceptions import SourceNotFoundError
from .options import ExportOptions


def get_exporters() -> dict[str, Callable]:
    """返回所有已注册的导出函数（{format: export_func}）。"""
    from ..exporter import register_exporter
    return register_exporter()


def get_exporter_options() -> dict[str, type[ExportOptions]]:
    from ..exporter import register_export_options
    return register_export_options()


async def search(source_name: str, query: str, engines,
                 skip_delay: bool = False, mode_overrides: dict[str, str] | None = None,
                 **kwargs) -> SearchResult | None:
    """搜索**单个**书源，返回第一条命中；该源无结果 → None。

    源报错 / 不支持搜索（`FeatureNotSupportedError`）**向上抛异常**，由调用方决定
    提示还是跳过——多源并发由调用方各自 gather（core 不再吞异常）。
    `mode_overrides`（能力名 → mode）覆盖书源声明的 mode，用于用户层配置。
    """
    from ..source import resolve as _resolve

    fn, mode = _resolve(source_name, "search")
    mode = (mode_overrides or {}).get("search") or mode
    kwargs["skip_delay"] = skip_delay
    results = await fn(query=query, engine=engines(mode), **kwargs)
    for r in results:                        # 统一打标（书源侧不写死 source_name）
        r.source_name = source_name
    return results[0] if results else None


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
