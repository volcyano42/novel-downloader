import os
import threading
from importlib import import_module
from pathlib import Path
from typing import Any

from ..core.options import ExportOptions
from ..exporters.base import BASEExporter
from ..fetchers.base import BaseFetcher

_lock = threading.Lock()
_cache_fetcher: dict[str, type[BaseFetcher]] | None = None
_cache_exporter: dict[str, type[BASEExporter]] | None = None
_cache_export_opts: dict[str, type[ExportOptions]] | None = None


def _scan_plugins(subpackage: str, *, capitalize: bool) -> dict[str, Any]:
    """扫描子包目录，发现命名符合约定的插件类。

    Args:
        subpackage: 相对子包名，如 ``"fetchers"`` / ``"exporters"``。
        capitalize: True 则类名用首字母大写（如 FanqieFetcher），
                    False 则全大写（如 EPUBExporter）。

    Returns:
        {module_name: class} 字典。
    """
    result = {}
    pkg_dir = Path(__file__).parent.parent / subpackage
    if not pkg_dir.exists():
        return result

    for file in sorted(os.listdir(pkg_dir)):
        if not file.endswith(".py") or file in ("__init__.py", "base.py"):
            continue
        module_name = file[:-3]
        try:
            module = import_module(f"..{subpackage}.{module_name}", __package__)
            stem = module_name.capitalize() if capitalize else module_name.upper()
            cls_name = stem + subpackage.rstrip("s").capitalize()  # "Fetcher" / "Exporter"
            result[module_name] = getattr(module, cls_name)
        except (ImportError, AttributeError) as e:
            print(f"load {subpackage} failed {module_name} reason: {e}")

    return result


def _scan_export_options() -> dict[str, Any]:
    """扫描 exporters/ 目录，发现 *ExportOptions 类。"""
    result = {}
    pkg_dir = Path(__file__).parent.parent / "exporters"
    if not pkg_dir.exists():
        return result

    for file in sorted(os.listdir(pkg_dir)):
        if not file.endswith(".py") or file in ("__init__.py", "base.py"):
            continue
        module_name = file[:-3]
        try:
            module = import_module(f"..exporters.{module_name}", __package__)
            cls_name = module_name.upper() + "ExportOptions"
            result[module_name] = getattr(module, cls_name)
        except (ImportError, AttributeError) as e:
            print(f"load export_options failed {module_name} reason: {e}")

    return result


def _hardcoded_fetchers() -> dict[str, type[BaseFetcher]]:
    """exe 环境下 _scan_plugins 可能找不到模块，硬编码兜底。"""
    from ..fetchers.fanqie import FanqieFetcher
    from ..fetchers.qidian import QidianFetcher
    from ..fetchers.qimao import QimaoFetcher
    return {"fanqie": FanqieFetcher, "qidian": QidianFetcher, "qimao": QimaoFetcher}


def register_fetcher() -> dict[str, type[BaseFetcher]]:
    global _cache_fetcher
    if _cache_fetcher is not None:
        return _cache_fetcher
    with _lock:
        if _cache_fetcher is not None:
            return _cache_fetcher
        result = _scan_plugins("fetchers", capitalize=True)
        if not result:
            result = _hardcoded_fetchers()  # exe 兜底
        _cache_fetcher = result
    return _cache_fetcher


def _hardcoded_exporters() -> dict[str, type[BASEExporter]]:
    """exe 环境下 _scan_plugins 可能找不到模块，硬编码兜底。"""
    from ..exporters.txt import TXTExporter
    from ..exporters.epub import EPUBExporter
    from ..exporters.img import IMGExporter
    return {"txt": TXTExporter, "epub": EPUBExporter, "img": IMGExporter}


def _hardcoded_export_options() -> dict[str, type[ExportOptions]]:
    """exe 环境下 _scan_export_options 可能找不到模块，硬编码兜底。"""
    from ..exporters.txt import TXTExportOptions
    from ..exporters.epub import EPUBExportOptions
    from ..exporters.img import IMGExportOptions
    return {"txt": TXTExportOptions, "epub": EPUBExportOptions, "img": IMGExportOptions}


def register_exporter() -> dict[str, type[BASEExporter]]:
    global _cache_exporter
    if _cache_exporter is not None:
        return _cache_exporter
    with _lock:
        if _cache_exporter is not None:
            return _cache_exporter
        result = _scan_plugins("exporters", capitalize=False)
        if not result:
            result = _hardcoded_exporters()
        _cache_exporter = result  # type: ignore[assignment]
    return _cache_exporter


def register_export_options() -> dict[str, type[ExportOptions]]:
    global _cache_export_opts
    if _cache_export_opts is not None:
        return _cache_export_opts
    with _lock:
        if _cache_export_opts is not None:
            return _cache_export_opts
        result = _scan_export_options()
        if not result:
            result = _hardcoded_export_options()
        _cache_export_opts = result  # type: ignore[assignment]
    return _cache_export_opts
