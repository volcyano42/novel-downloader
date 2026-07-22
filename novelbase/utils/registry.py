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

    支持两种形式：
    - 单文件：fetchers/fanqie.py → FanqieFetcher
    - 目录包：fetchers/fanqie/__init__.py → FanqieFetcher

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

    for entry in sorted(os.listdir(pkg_dir)):
        entry_path = pkg_dir / entry
        # 单文件形式：fanqie.py
        if entry.endswith(".py") and entry not in ("__init__.py", "base.py"):
            module_name = entry[:-3]
        # 目录包形式：fanqie/__init__.py
        elif entry_path.is_dir() and (entry_path / "__init__.py").exists():
            module_name = entry
        else:
            continue
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


# ═══════════════════════════════════════════════════════════════════
# Phase 3 — 能力发现 + 动态分发
# ═══════════════════════════════════════════════════════════════════

def capabilities(name: str) -> dict[str, list[str]]:
    """扫描 fetchers/{name}/ 目录，返回可用能力矩阵。

    >>> capabilities("fanqie")
    {"api": ["oiapi", "rain"], "browser": [], "requests": []}

    单 provider 的 mode 返回空列表；无该 mode 则不出现 key。
    """
    pkg_dir = Path(__file__).parent.parent / "fetchers" / name
    if not pkg_dir.is_dir():
        return {}

    result: dict[str, list[str]] = {}
    for mode_dir in sorted(pkg_dir.iterdir()):
        if not mode_dir.is_dir() or mode_dir.name.startswith("_") or mode_dir.name == "__pycache__":
            continue
        mode = mode_dir.name
        # 检查 mode 目录下是否有 provider 子目录
        providers: list[str] = []
        for sub in sorted(mode_dir.iterdir()):
            if sub.is_dir() and not sub.name.startswith("_") and sub.name != "__pycache__":
                # 确认里面有 .py 文件（不只是空壳）
                if any(f.suffix == ".py" for f in sub.iterdir()):
                    providers.append(sub.name)
        # 检查 mode 目录自身是否有 .py 文件（单 provider 模式）
        has_direct_functions = any(
            f.suffix == ".py" and f.name != "__init__.py"
            for f in mode_dir.iterdir()
        )
        if providers:
            result[mode] = providers
        elif has_direct_functions:
            result[mode] = []
    return result


def resolve(name: str, mode: str, function: str, provider: str | None = None):
    """动态 import 并返回同步 fetcher 函数。

    >>> fn = resolve("fanqie", "api", "search", "oiapi")
    >>> results = fn("关键词", engine)

    单 provider 时 provider 可为 None，多 provider 时必须指定。
    """
    caps = capabilities(name)
    if mode not in caps:
        raise ValueError(f"mode {mode!r} not available for {name!r}. Available: {list(caps)}")

    providers = caps[mode]
    if providers:
        # 多 provider：需要指定
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
