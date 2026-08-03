import os
import threading
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

from ..core.options import ExportOptions

_lock = threading.Lock()
_cache_source: dict[str, dict] | None = None
_cache_exporter: dict[str, Callable] | None = None
_cache_export_opts: dict[str, type[ExportOptions]] | None = None


def _scan_sources() -> dict[str, dict]:
    """扫描 sources/ 目录，收集每个 source 的 NAME / HOSTS / ID_PATTERN。

    识别规则：目录 + 不以 _ 开头 + 含 __init__.py。

    Returns:
        {module_name: {"name": ..., "hosts": ..., "id_pattern": ...}}
    """
    result = {}
    pkg_dir = Path(__file__).parent.parent / "sources"
    if not pkg_dir.exists():
        return result

    for entry in sorted(os.listdir(pkg_dir)):
        if entry.startswith("_") or entry == "__pycache__":
            continue
        entry_path = pkg_dir / entry
        if not entry_path.is_dir() or not (entry_path / "__init__.py").exists():
            continue
        module_name = entry
        try:
            module = import_module(f"..sources.{module_name}", __package__)
            result[module_name] = {
                "name": getattr(module, "NAME", module_name),
                "show_name": getattr(module, "SHOW_NAME", module_name),
                "hosts": getattr(module, "HOSTS", ()),
                "id_pattern": getattr(module, "ID_PATTERN", None),
                "origin_id_pattern": getattr(module, "ORIGIN_ID_PATTERN", None),
            }
        except ImportError as e:
            print(f"load source failed {module_name} reason: {e}")

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


def register_source() -> dict[str, dict]:
    """返回所有已注册的 source（{name: {name, hosts, id_pattern}}）。"""
    global _cache_source
    if _cache_source is not None:
        return _cache_source
    with _lock:
        if _cache_source is not None:
            return _cache_source
        result = _scan_sources()
        _cache_source = result
    return _cache_source




def _scan_exporters() -> dict[str, Callable]:
    """扫描 exporters/ 目录，发现 export() 函数。"""
    result: dict[str, Callable] = {}
    pkg_dir = Path(__file__).parent.parent / "exporters"
    if not pkg_dir.exists():
        return result
    for entry in sorted(os.listdir(pkg_dir)):
        if entry.endswith(".py") and entry not in ("__init__.py", "base.py"):
            module_name = entry[:-3]
            try:
                module = import_module(f"..exporters.{module_name}", __package__)
                result[module_name] = module.export
            except (ImportError, AttributeError):
                pass
    return result


def register_exporter() -> dict[str, Callable]:
    global _cache_exporter
    if _cache_exporter is not None:
        return _cache_exporter
    with _lock:
        if _cache_exporter is not None:
            return _cache_exporter
        result = _scan_exporters()
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
        _cache_export_opts = result  # type: ignore[assignment]
    return _cache_export_opts


def list_sources() -> list[str]:
    """列出所有可用源名称。"""
    pkg_dir = Path(__file__).parent.parent / "sources"
    if not pkg_dir.exists():
        return []
    result: list[str] = []
    for entry in sorted(pkg_dir.iterdir()):
        if entry.name.startswith("_") or not entry.is_dir() or not (entry / "__init__.py").exists():
            continue
        result.append(entry.name)
    return result
