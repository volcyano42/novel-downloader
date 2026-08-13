"""导出器注册表 — 注册 novelbase 的导出器（txt/epub/img）与导出选项。

Source 相关的注册/发现（register_source / list_sources / platform_from_url 等）
在 novelbase.source，本模块只负责 exporter。
"""

import threading
from typing import Callable

from .core.options import ExportOptions

_lock = threading.Lock()
_cache_exporter: dict[str, Callable] | None = None
_cache_export_opts: dict[str, type[ExportOptions]] | None = None


def _static_exporters() -> dict[str, Callable]:
    from .exporters.txt import export as _txt_export
    from .exporters.epub import export as _epub_export
    from .exporters.img import export as _img_export
    return {"txt": _txt_export, "epub": _epub_export, "img": _img_export}


def _static_export_options() -> dict[str, type[ExportOptions]]:
    from .exporters.txt import TXTExportOptions
    from .exporters.epub import EPUBExportOptions
    from .exporters.img import IMGExportOptions
    return {"txt": TXTExportOptions, "epub": EPUBExportOptions, "img": IMGExportOptions}


def register_exporter() -> dict[str, Callable]:
    global _cache_exporter
    if _cache_exporter is not None:
        return _cache_exporter
    with _lock:
        if _cache_exporter is not None:
            return _cache_exporter
        _cache_exporter = _static_exporters()
    return _cache_exporter


def register_export_options() -> dict[str, type[ExportOptions]]:
    global _cache_export_opts
    if _cache_export_opts is not None:
        return _cache_export_opts
    with _lock:
        if _cache_export_opts is not None:
            return _cache_export_opts
        _cache_export_opts = _static_export_options()
    return _cache_export_opts
