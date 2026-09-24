"""Source 能力发现与动态分发（公共 API）。

书源 = `novelbase/sources/{dir}/`，身份与出厂配置在 `source.json`，能力在 `{capability}.py`。
本模块对外只有 4 个函数 + 1 个 URL 入口：

- `list_sources()`                        所有书源名（source.json 的 source_name）
- `get_manifest(source_name)`             `source.json` 内容
- `capabilities(source_name)`             `{capability: mode}`
- `resolve(source_name, capability)`      `(函数, mode)`
- `resolve_book_url(raw)`                 把输入规范成完整 URL

键约定：`source_name` 与目录名解耦（目录名是合法标识符的磁盘位置，source_name 是
`source.json` 里的唯一 id，形如 `fanqie-api-rain`）。本模块所有公开 API 均以
`source_name` 为键；目录名只在 `import_module` 时使用。

私有源：`NLD_PRIVATE_SOURCES` 指向的目录镜像 `sources/{dir}/`，同名书源目录里
已存在的能力文件优先用内置，缺失的用私有实现补齐。
"""

import os
from importlib import import_module, util as importlib_util
from inspect import signature
from pathlib import Path
from typing import Callable

from .sources.contracts import CAPABILITY_META
from .sources.manifest import ManifestError, check_capability_files, load_manifest

__all__ = ["list_sources", "get_manifest", "capabilities", "resolve", "resolve_book_url"]

_PRIVATE_SOURCES_ROOT: str | None = os.environ.get("NLD_PRIVATE_SOURCES")

_SOURCES_DIR = Path(__file__).parent / "sources"


def _is_compiled() -> bool:
    """Nuitka/PyInstaller 产物里 `__compiled__` 会出现在模块 globals。"""
    return "__compiled__" in globals()


def _compiled_sources() -> dict[str, dict]:
    """编译模式下的书源表：{目录名: source.json 内容}。"""
    from .utils import _manifest
    return _manifest.SOURCES


def _compiled_dir_by_source() -> dict[str, str]:
    """编译模式下的 {source_name: 目录名} 映射（供 import_module 用）。"""
    from .utils import _manifest
    return _manifest.SOURCE_DIRS


def _iter_source_dirs(source_name: str) -> list[tuple[Path, bool]]:
    """按 source_name 反查目录（(路径, 是否内置)），内置在前、私有在后。"""
    dirs: list[tuple[Path, bool]] = []
    if _SOURCES_DIR.is_dir():
        for entry in sorted(_SOURCES_DIR.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_") or not (entry / "source.json").is_file():
                continue
            try:
                if load_manifest(entry).get("source_name") == source_name:
                    dirs.append((entry, True))
            except ManifestError:
                continue
    if _PRIVATE_SOURCES_ROOT:
        p = Path(_PRIVATE_SOURCES_ROOT)
        if p.is_dir():
            for entry in sorted(p.iterdir()):
                if entry.is_dir() and not entry.name.startswith("_") and (entry / "source.json").is_file():
                    try:
                        if load_manifest(entry).get("source_name") == source_name:
                            dirs.append((entry, False))
                    except ManifestError:
                        continue
    return dirs


def list_sources() -> list[str]:
    """列出内置 + 私有书源的 source_name（去重排序）。"""
    if _is_compiled():
        return sorted(m["source_name"] for m in _compiled_sources().values())
    names: set[str] = set()
    roots: list[Path] = []
    if _SOURCES_DIR.is_dir():
        roots.append(_SOURCES_DIR)
    if _PRIVATE_SOURCES_ROOT:
        p = Path(_PRIVATE_SOURCES_ROOT)
        if p.is_dir():
            roots.append(p)
    for root in roots:
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_") or not (entry / "source.json").is_file():
                continue
            try:
                names.add(load_manifest(entry)["source_name"])
            except ManifestError:
                continue
    return sorted(names)


def get_manifest(source_name: str) -> dict:
    """返回书源的 `source.json` 内容（内置优先；非编译模式校验能力段 ⇔ .py 文件）。"""
    if _is_compiled():
        dirname = _compiled_dir_by_source().get(source_name)
        if dirname is None or dirname not in _compiled_sources():
            raise KeyError(f"unknown source: {source_name}")
        return _compiled_sources()[dirname]
    dirs = _iter_source_dirs(source_name)
    if not dirs:
        raise KeyError(f"unknown source: {source_name}")
    d, _ = dirs[0]
    manifest = load_manifest(d)
    check_capability_files(d, manifest)  # spec 规则 1：能力段 ⇔ .py 文件双向一致
    return manifest


def capabilities(source_name: str) -> dict[str, str]:
    """返回 `{capability: mode}`；书源不存在或声明非法时返回 `{}`。"""
    try:
        manifest = get_manifest(source_name)
    except (KeyError, ManifestError):
        return {}
    return {cap: section["mode"] for cap, section in manifest.get("default_config", {}).items()}


def _resolve_import(source_name: str, capability: str, dirname: str):
    """按目录名 import 能力模块并返回函数。"""
    module_path = f"novelbase.sources.{dirname}.{capability}"
    try:
        module = import_module(module_path)
    except ImportError as e:
        raise ImportError(f"Failed to resolve {module_path}: {e}") from e
    fn = getattr(module, capability, None)
    if fn is None:
        raise ImportError(f"{module_path} 里没有名为 {capability} 的函数")
    return fn


def resolve(source_name: str, capability: str):
    """动态加载并返回 `(函数, 该能力的 mode)`。"""
    meta = CAPABILITY_META.get(capability)
    if meta is None:
        raise ValueError(f"unknown capability {capability!r}. Known: {list(CAPABILITY_META)}")

    mode = capabilities(source_name).get(capability)
    if mode is None:
        raise ValueError(f"{source_name} 未声明能力 {capability!r}")

    if _is_compiled():
        # 编译模式：能力模块已被 --include-package=novelbase.sources 打进产物，
        # 文件系统里没有 .py 可查，直接按目录名 import
        dirname = _compiled_dir_by_source().get(source_name)
        if dirname is None:
            raise ImportError(f"unknown source: {source_name}")
        fn = _resolve_import(source_name, capability, dirname)
    else:
        fn = None
        for d, is_builtin in _iter_source_dirs(source_name):
            if is_builtin:
                # 内置：import_module；同名能力内置优先，内置缺失再试私有补齐
                try:
                    fn = _resolve_import(source_name, capability, d.name)
                except ImportError:
                    continue
            else:
                # 私有：在包外（NLD_PRIVATE_SOURCES），必须走 spec_from_file_location（spec:163）
                candidate = d / f"{capability}.py"
                if not candidate.is_file():
                    continue
                module_name = f"novelbase_private.sources.{d.name}.{capability}"
                spec = importlib_util.spec_from_file_location(module_name, str(candidate))
                if spec is None or spec.loader is None:
                    raise ImportError(f"Failed to load spec from {candidate}")
                module = importlib_util.module_from_spec(spec)
                spec.loader.exec_module(module)
                fn = getattr(module, capability, None)
            if fn is not None:
                break
        if fn is None:
            raise ImportError(f"{source_name} 缺少能力文件 {capability}.py")

    sig = signature(fn)
    missing = [p for p in meta["required_params"] if p not in sig.parameters]
    if missing:
        raise ValueError(f"{source_name}.{capability} 签名缺少参数: {missing}. 当前签名: {list(sig.parameters)}")
    return fn, mode


def resolve_book_url(raw: str) -> str:
    """把输入规范成完整 URL（仅接受 http(s)；无法识别时抛 ValueError）。"""
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    raise ValueError(f"无法识别书源或 ID 格式: {raw}")
