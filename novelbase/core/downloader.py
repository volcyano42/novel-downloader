from collections.abc import Callable

from ..models.novel import Chapter, Chapters, Novel, SearchResult
from ..utils.urls import make_novel_id
from .engine import Engine
from .exceptions import SourceNotFoundError
from .options import ExportOptions


def _reject_legacy_engines(engine) -> None:
    """防呆：`engines(mode) -> engine` 解析器已移除，这里必须是 Engine 实例。"""
    if callable(engine):
        raise TypeError(
            "engine 现在必须传入 Engine 实例（原 engines(mode) 解析器已移除）；"
            "请用 shared.config.effective_capabilities(source_name) 选 mode 后自行 create_engine"
        )


def get_exporters() -> dict[str, Callable]:
    """返回所有已注册的导出函数（{format: export_func}）。"""
    from ..exporter import register_exporter
    return register_exporter()


def get_exporter_options() -> dict[str, type[ExportOptions]]:
    from ..exporter import register_export_options
    return register_export_options()


async def search(source_name: str, query: str, engine: Engine,
                 skip_delay: bool = False, **kwargs) -> SearchResult | None:
    """搜索**单个**书源，返回第一条命中；该源无结果 → None。

    源报错 / 不支持搜索（`FeatureNotSupportedError`）**向上抛异常**，由调用方决定
    提示还是跳过——多源并发由调用方各自 gather（core 不再吞异常）。
    `engine` 由调用方按该能力的**有效 mode** 建好后传入（core 不关心 mode）。
    """
    from ..source import resolve as _resolve

    _reject_legacy_engines(engine)
    fn, _ = _resolve(source_name, "search")
    kwargs["skip_delay"] = skip_delay
    results = await fn(query=query, engine=engine, **kwargs)
    for r in results:                        # 统一打标（书源侧不写死 source_name）
        r.source_name = source_name
    return results[0] if results else None


async def resolve_meta(url: str, source_name: str, engine: Engine, skip_delay: bool = False,
                       **kwargs) -> Novel:
    from ..source import resolve as _resolve

    _reject_legacy_engines(engine)
    try:
        fn, _ = _resolve(source_name, "novel_info")
    except (ValueError, ImportError) as e:
        raise SourceNotFoundError(f"source not found: {source_name}") from e
    kwargs["skip_delay"] = skip_delay
    novel = await fn(url=url, engine=engine, **kwargs)
    novel.id = make_novel_id(novel.url)
    return novel


async def resolve_chapter_list(url: str, source_name: str, engine: Engine,
                               skip_delay: bool = False, **kwargs) -> Chapters:
    from ..source import resolve as _resolve

    _reject_legacy_engines(engine)
    fn, _ = _resolve(source_name, "chapter_list")
    kwargs["skip_delay"] = skip_delay
    return await fn(url=url, engine=engine, **kwargs)


async def resolve_chapter(chapter: Chapter, source_name: str, engine: Engine,
                          skip_delay: bool = False, **kwargs) -> Chapter | None:
    from ..source import resolve as _resolve

    _reject_legacy_engines(engine)
    fn, _ = _resolve(source_name, "chapter_content")
    kwargs["skip_delay"] = skip_delay
    return await fn(chapter=chapter, engine=engine, **kwargs)


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
