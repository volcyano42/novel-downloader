import os
import threading
from importlib import import_module
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_cache_parser: dict[str, Any] | None = None
_cache_exporter: dict[str, Any] | None = None
_cache_export_opts: dict[str, Any] | None = None


def _scan_plugins(subpackage: str, *, capitalize: bool) -> dict[str, Any]:
    """扫描子包目录，发现命名符合约定的插件类。

    Args:
        subpackage: 相对子包名，如 ``"parsers"`` / ``"exporters"``。
        capitalize: True 则类名用首字母大写（如 FanqieParser），
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
            cls_name = stem + subpackage.rstrip("s").capitalize()  # "Parser" / "Exporter"
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


def register_parser() -> dict[str, Any]:
    global _cache_parser
    if _cache_parser is not None:
        return _cache_parser
    with _lock:
        if _cache_parser is not None:
            return _cache_parser
        _cache_parser = _scan_plugins("parsers", capitalize=True)
    return _cache_parser


def register_exporter() -> dict[str, Any]:
    global _cache_exporter
    if _cache_exporter is not None:
        return _cache_exporter
    with _lock:
        if _cache_exporter is not None:
            return _cache_exporter
        _cache_exporter = _scan_plugins("exporters", capitalize=False)
    return _cache_exporter


def register_export_options() -> dict[str, Any]:
    global _cache_export_opts
    if _cache_export_opts is not None:
        return _cache_export_opts
    with _lock:
        if _cache_export_opts is not None:
            return _cache_export_opts
        _cache_export_opts = _scan_export_options()
    return _cache_export_opts
