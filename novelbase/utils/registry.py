import os
import re
import threading
from importlib import import_module
from pathlib import Path
from typing import Any, Callable

from ..core.options import ExportOptions

_lock = threading.Lock()
_cache_source: dict[str, dict] | None = None
_cache_exporter: dict[str, Callable] | None = None
_cache_export_opts: dict[str, type[ExportOptions]] | None = None


def _is_compiled() -> bool:
    """检测是否为 Nuitka/PyInstaller 编译产物。"""
    return "__compiled__" in globals()


def _scan_sources() -> dict[str, dict]:
    """扫描 sources/ 目录，收集每个 source 的 NAME / HOSTS / ID_PATTERN 等。

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
                "book_url_template": getattr(module, "BOOK_URL_TEMPLATE", ""),
            }
        except ImportError as e:
            print(f"load source failed {module_name} reason: {e}")

    return result


def register_source() -> dict[str, dict]:
    """返回所有已注册的 source 元数据。Nuitka 模式从 manifest 读取。"""
    global _cache_source
    if _cache_source is not None:
        return _cache_source
    with _lock:
        if _cache_source is not None:
            return _cache_source
        if _is_compiled():
            _cache_source = _load_manifest_sources()
        else:
            _cache_source = _scan_sources()
    return _cache_source


def _load_manifest_sources() -> dict[str, dict]:
    """从 _manifest.py 加载书源数据（Nuitka 模式）。"""
    try:
        from ..utils import _manifest
        return _manifest._flat_sources()
    except ImportError:
        return {}


# ── Exporters ────────────────────────────────────────


def _static_exporters() -> dict[str, Callable]:
    from ..exporters.txt import export as _txt_export
    from ..exporters.epub import export as _epub_export
    from ..exporters.img import export as _img_export
    return {"txt": _txt_export, "epub": _epub_export, "img": _img_export}


def _static_export_options() -> dict[str, type[ExportOptions]]:
    from ..exporters.txt import TXTExportOptions
    from ..exporters.epub import EPUBExportOptions
    from ..exporters.img import IMGExportOptions
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


def list_sources() -> list[str]:
    """列出所有可用源名称（开发模式目录扫描，编译模式 manifest）。"""
    if _is_compiled():
        try:
            from ..utils import _manifest
            return list(_manifest._SOURCES.keys())
        except ImportError:
            return []
    pkg_dir = Path(__file__).parent.parent / "sources"
    if not pkg_dir.exists():
        return []
    result: list[str] = []
    for entry in sorted(pkg_dir.iterdir()):
        if entry.name.startswith("_") or not entry.is_dir() or not (entry / "__init__.py").exists():
            continue
        result.append(entry.name)
    return result


def platform_from_url(url: str) -> str | None:
    """从 URL 推断平台名称，基于已注册书源的 hosts 匹配。"""
    sources = register_source()
    for name, meta in sources.items():
        for host in meta.get("hosts", ()):
            if host in url:
                return name
    return None


def resolve_book_url(raw: str) -> str:
    """将 URL 或带前缀 ID 转为完整 URL。

    - 已是完整 URL 则直接返回
    - 带前缀的 ID（如 fanqie_1234567890123456789）通过 ID_PATTERN 匹配平台，
      再通过 BOOK_URL_TEMPLATE 构建完整 URL
    - 无法识别时报 ValueError
    """
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw

    # 带前缀 ID → 匹配平台
    sources = register_source()
    for name, meta in sources.items():
        id_pat = meta.get("id_pattern")
        if id_pat and id_pat.match(raw):
            template = meta.get("book_url_template", "")
            if template:
                num = raw.split("_", 1)[-1] if "_" in raw else raw
                return template.replace("{id}", num)

    raise ValueError(f"无法识别书源或 ID 格式: {raw}")
