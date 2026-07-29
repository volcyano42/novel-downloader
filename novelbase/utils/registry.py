import os
import re
import threading
from importlib import import_module
from pathlib import Path
from typing import Any

from ..core.options import ExportOptions
from ..exporters.base import BASEExporter

_lock = threading.Lock()
_cache_source: dict[str, dict] | None = None
_cache_exporter: dict[str, type[BASEExporter]] | None = None
_cache_export_opts: dict[str, type[ExportOptions]] | None = None


def _scan_sources() -> dict[str, dict]:
    """扫描 fetchers/ 目录，收集每个 source 的 NAME / HOSTS / ID_PATTERN。

    支持两种形式：
    - 单文件：fetchers/fanqie.py
    - 目录包：fetchers/fanqie/__init__.py

    Returns:
        {module_name: {"name": ..., "hosts": ..., "id_pattern": ...}}
    """
    result = {}
    pkg_dir = Path(__file__).parent.parent / "fetchers"
    if not pkg_dir.exists():
        return result

    for entry in sorted(os.listdir(pkg_dir)):
        entry_path = pkg_dir / entry
        if entry.startswith("_") or entry == "__pycache__":
            continue
        # 单文件形式：fanqie.py
        if entry.endswith(".py") and entry not in ("__init__.py", "base.py"):
            module_name = entry[:-3]
        # 目录包形式：fanqie/__init__.py
        elif entry_path.is_dir() and (entry_path / "__init__.py").exists():
            module_name = entry
        else:
            continue
        try:
            module = import_module(f"..fetchers.{module_name}", __package__)
            result[module_name] = {
                "name": getattr(module, "NAME", module_name),
                "hosts": getattr(module, "HOSTS", ()),
                "id_pattern": getattr(module, "ID_PATTERN", None),
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


def _hardcoded_sources() -> dict[str, dict]:
    """exe 环境下 _scan_sources 可能找不到模块，硬编码兜底。"""
    return {
        "fanqie": {
            "name": "fanqie",
            "hosts": ("fanqienovel.com", "changdunovel.com"),
            "id_pattern": re.compile(r"^(?:book_id=?)?(\d{19})$"),
        },
        "qidian": {
            "name": "qidian",
            "hosts": ("www.qidian.com", "book.qidian.com"),
            "id_pattern": re.compile(r"^(?:/(book|info)/?)?(\d{10})/?$"),
        },
        "qimao": {
            "name": "qimao",
            "hosts": ("www.qimao.com", "qimao.com"),
            "id_pattern": re.compile(r"^(?:/shuku/?)?(\d+)$"),
        },
    }


def register_source() -> dict[str, dict]:
    """返回所有已注册的 source（{name: {name, hosts, id_pattern}}）。"""
    global _cache_source
    if _cache_source is not None:
        return _cache_source
    with _lock:
        if _cache_source is not None:
            return _cache_source
        result = _scan_sources()
        if not result:
            result = _hardcoded_sources()
        _cache_source = result
    return _cache_source


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


def _scan_plugins(subpackage: str, *, capitalize: bool) -> dict[str, Any]:
    """扫描子包目录，发现命名符合约定的插件类。

    Args:
        subpackage: 相对子包名，如 ``"exporters"``。
        capitalize: True 则类名用首字母大写，False 则全大写。
    """
    result = {}
    pkg_dir = Path(__file__).parent.parent / subpackage
    if not pkg_dir.exists():
        return result

    for entry in sorted(os.listdir(pkg_dir)):
        entry_path = pkg_dir / entry
        if entry.endswith(".py") and entry not in ("__init__.py", "base.py"):
            module_name = entry[:-3]
        elif entry_path.is_dir() and (entry_path / "__init__.py").exists():
            module_name = entry
        else:
            continue
        try:
            module = import_module(f"..{subpackage}.{module_name}", __package__)
            stem = module_name.capitalize() if capitalize else module_name.upper()
            cls_name = stem + subpackage.rstrip("s").capitalize()
            result[module_name] = getattr(module, cls_name)
        except (ImportError, AttributeError) as e:
            print(f"load {subpackage} failed {module_name} reason: {e}")

    return result


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


# ═══════════════════════════════════════════════════════════════════
# 能力发现 + 动态分发
# ═══════════════════════════════════════════════════════════════════

def capabilities(name: str) -> dict[str, list[str] | dict[str, list[str]]]:
    """扫描 fetchers/{name}/ 目录，返回可用能力矩阵。

    >>> capabilities("fanqie")
    {"api": {"oiapi": ["search", "novel_info", "chapter_list", "chapter_content"],
             "rain": ["search", "novel_info", "chapter_list", "chapter_content"]},
     "browser": ["search", "novel_info", "chapter_list", "chapter_content", "login"],
     "requests": ["search", "novel_info", "chapter_list", "chapter_content"]}

    多 provider 的 mode 返回 {provider: [functions]}；
    单 provider 的 mode 返回 [functions]；
    无该 mode 则不出现 key。
    """
    pkg_dir = Path(__file__).parent.parent / "fetchers" / name
    if not pkg_dir.is_dir():
        return {}

    # 功能名 → 文件名 stem
    FUNC_FILE_MAP = {
        "search": "search",
        "novel_info": "novel_info",
        "chapter_list": "chapter_list",
        "chapter_content": "chapter_content",
        "login": "login",
    }

    result: dict[str, list[str] | dict[str, list[str]]] = {}
    for mode_dir in sorted(pkg_dir.iterdir()):
        if not mode_dir.is_dir() or mode_dir.name.startswith("_") or mode_dir.name == "__pycache__":
            continue
        mode = mode_dir.name

        providers: dict[str, list[str]] = {}
        for sub in sorted(mode_dir.iterdir()):
            if sub.is_dir() and not sub.name.startswith("_") and sub.name != "__pycache__":
                funcs: list[str] = []
                for func_name, file_stem in FUNC_FILE_MAP.items():
                    if (sub / f"{file_stem}.py").exists():
                        funcs.append(func_name)
                if funcs:
                    providers[sub.name] = funcs

        # 检查 mode 目录自身是否有 .py 文件（无 provider 模式）
        direct_funcs: list[str] = []
        for func_name, file_stem in FUNC_FILE_MAP.items():
            if (mode_dir / f"{file_stem}.py").exists():
                direct_funcs.append(func_name)

        if providers:
            result[mode] = providers
        elif direct_funcs:
            result[mode] = direct_funcs

    return result


def resolve(name: str, mode: str, function: str, provider: str | None = None):
    """动态 import 并返回同步函数。

    >>> fn = resolve("fanqie", "api", "search", "oiapi")
    >>> results = fn("关键词", engine)

    单 provider 时 provider 可为 None，多 provider 时必须指定。
    """
    caps = capabilities(name)
    if mode not in caps:
        raise ValueError(f"mode {mode!r} not available for {name!r}. Available: {list(caps)}")

    mode_caps = caps[mode]
    if isinstance(mode_caps, dict):
        # 多 provider：需要指定
        providers = list(mode_caps.keys())
        if provider is None:
            provider = providers[0]  # 默认第一个
        elif provider not in providers:
            raise ValueError(f"provider {provider!r} not available for {name}/{mode}. Available: {providers}")
        module_path = f"novelbase.fetchers.{name}.{mode}.{provider}.{function}"
    else:
        if provider is not None:
            raise ValueError(f"provider specified but {name}/{mode} has no sub-providers")
        module_path = f"novelbase.fetchers.{name}.{mode}.{function}"

    try:
        module = import_module(module_path)
        return getattr(module, function)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Failed to resolve {module_path}: {e}") from e


def list_sources() -> list[str]:
    """列出所有可用源名称。"""
    pkg_dir = Path(__file__).parent.parent / "fetchers"
    if not pkg_dir.exists():
        return []
    result: list[str] = []
    for entry in sorted(pkg_dir.iterdir()):
        if entry.name.startswith("_") or entry.name == "base.py":
            continue
        if (entry.is_dir() and (entry / "__init__.py").exists()) or \
           (entry.suffix == ".py" and entry.name != "__init__.py"):
            name = entry.stem if entry.is_file() else entry.name
            result.append(name)
    return result
