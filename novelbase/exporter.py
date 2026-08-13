"""导出器注册表 — 动态发现 novelbase 的导出器（txt/epub/img 及外部自定义格式）。

内置导出器放在 exporters/ 目录，每个模块约定：
- 一个继承 ExportOptions 的 *ExportOptions 类，带 format 字段（如 TXTExportOptions.format = "txt"）
- 一个顶层 export(chapters, novel, options=None, **kwargs) 函数

外部导出器：设置环境变量 NLD_PRIVATE_EXPORTERS 指向外部目录，
镜像 exporters/ 结构（一个 .py 文件 = 一个格式），自动合并进注册表。
外部与内置同格式时，外部直接替换内置。

Source 相关的注册/发现（register_source / list_sources 等）在 novelbase.source。
"""

import importlib.util as importlib_util
import os
import threading
from pathlib import Path
from typing import Callable

from .core.options import ExportOptions

__all__ = [
    "register_exporter",
    "register_export_options",
    "list_exporter_formats",
]

_PRIVATE_EXPORTERS_ROOT: str | None = os.environ.get("NLD_PRIVATE_EXPORTERS")

_lock = threading.Lock()
_cache_exporter: dict[str, Callable] | None = None
_cache_export_opts: dict[str, type[ExportOptions]] | None = None


def _exporter_dirs() -> list[Path]:
    """返回导出器目录列表（内置 + 外部），内置在前。"""
    dirs = [Path(__file__).parent / "exporters"]
    if _PRIVATE_EXPORTERS_ROOT:
        private_dir = Path(_PRIVATE_EXPORTERS_ROOT)
        if private_dir.is_dir():
            dirs.append(private_dir)
    return dirs


def _load_module(module_path: Path, module_name: str):
    """从文件路径加载导出器模块（内置走包导入，外部走 spec 加载）。"""
    if module_path.parent.name == "exporters" and module_path.parent.parent.name == "novelbase":
        # 内置导出器：走包导入
        from importlib import import_module
        return import_module(f"novelbase.exporters.{module_path.stem}")
    # 外部导出器：spec_from_file_location 加载
    spec = importlib_util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        return None
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scan_one_module(module_path: Path, module_name: str) -> tuple[str, Callable, type[ExportOptions]] | None:
    """扫描单个导出器模块，返回 (format, export_func, options_cls)。

    约定：模块内有继承 ExportOptions 且带 format 字段的类 + 顶层 export 函数。
    不符合约定返回 None。
    """
    try:
        module = _load_module(module_path, module_name)
    except Exception:
        return None
    if module is None:
        return None

    # 找 export 函数
    export_func = getattr(module, "export", None)
    if not callable(export_func):
        return None

    # 运行时签名校验：export 必须接受 chapters/novel 参数
    from inspect import signature as _signature
    from .exporters.contracts import EXPORT_REQUIRED_PARAMS

    try:
        sig = _signature(export_func)
    except (TypeError, ValueError):
        return None
    missing = [p for p in EXPORT_REQUIRED_PARAMS if p not in sig.parameters]
    if missing:
        print(f"skip exporter {module_path}: export 签名缺少参数 {missing}")
        return None

    # 找 *ExportOptions 类（继承 ExportOptions 且带 format 字段）
    options_cls = None
    fmt = None
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if isinstance(obj, type) and issubclass(obj, ExportOptions) and obj is not ExportOptions:
            fmt_val = getattr(obj, "format", None)
            if isinstance(fmt_val, str) and fmt_val:
                options_cls = obj
                fmt = fmt_val
                break

    if fmt is None or options_cls is None:
        return None
    return fmt, export_func, options_cls


def _scan_exporters() -> tuple[dict[str, Callable], dict[str, type[ExportOptions]]]:
    """扫描内置 + 外部导出器目录，返回 (exporter_map, options_map)。

    外部与内置同格式时，外部替换内置（后扫描覆盖先扫描）。
    """
    exporters: dict[str, Callable] = {}
    options: dict[str, type[ExportOptions]] = {}

    for d in _exporter_dirs():
        if not d.is_dir():
            continue
        for module_path in sorted(d.glob("*.py")):
            if module_path.stem.startswith("_") or module_path.stem in ("base",):
                continue
            module_name = f"novelbase_private.exporters.{module_path.stem}"
            result = _scan_one_module(module_path, module_name)
            if result is None:
                continue
            fmt, export_func, options_cls = result
            exporters[fmt] = export_func
            options[fmt] = options_cls

    return exporters, options


def register_exporter() -> dict[str, Callable]:
    global _cache_exporter
    if _cache_exporter is not None:
        return _cache_exporter
    with _lock:
        if _cache_exporter is not None:
            return _cache_exporter
        exporters, _ = _scan_exporters()
        _cache_exporter = exporters
    return _cache_exporter


def register_export_options() -> dict[str, type[ExportOptions]]:
    global _cache_export_opts
    if _cache_export_opts is not None:
        return _cache_export_opts
    with _lock:
        if _cache_export_opts is not None:
            return _cache_export_opts
        _, options = _scan_exporters()
        _cache_export_opts = options
    return _cache_export_opts


def list_exporter_formats() -> list[str]:
    """列出所有可用导出格式名（对称 source.list_sources）。"""
    return sorted(register_exporter().keys())
