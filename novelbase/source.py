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

`source_name` **全局唯一**：内置根与私有根（`NLD_PRIVATE_SOURCES`）是同一命名空间，
任何两个目录声明同一个 `source_name` 都会在加载期抛 `DuplicateSourceNameError`
（`ManifestError` 的子类，见 `sources/manifest.py::scan_source_names()`）——宁可
整个加载失败，也不静默选一个源继续跑。私有源因此必须自带独立 `source_name`，
不能作为内置源的替代实现。
"""

import os
from importlib import import_module, util as importlib_util
from inspect import signature
from pathlib import Path
from .sources.contracts import CAPABILITY_META
from .sources.manifest import (
    DuplicateSourceNameError, ManifestError, check_capability_files,
    load_manifest, scan_source_names,
)

__all__ = ["list_sources", "get_manifest", "capabilities", "resolve",
           "resolve_book_url"]

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


def _source_dirs() -> dict[str, Path]:
    """全局唯一书源表 `{source_name: 目录}`（内置根在前，私有根在后）。

    任一 `source_name` 重复（含跨根）→ `DuplicateSourceNameError`。
    """
    roots: list[Path] = []
    if _SOURCES_DIR.is_dir():
        roots.append(_SOURCES_DIR)
    if _PRIVATE_SOURCES_ROOT:
        p = Path(_PRIVATE_SOURCES_ROOT)
        if p.is_dir():
            roots.append(p)
    return scan_source_names(roots)


def _source_dir(source_name: str) -> tuple[Path, bool] | None:
    """`(目录, 是否内置)`；未知 `source_name` 返回 `None`。"""
    path = _source_dirs().get(source_name)
    if path is None:
        return None
    return path, path.parent == _SOURCES_DIR


def list_sources() -> list[str]:
    """列出内置 + 私有书源的 source_name（排序；重名 → DuplicateSourceNameError）。"""
    if _is_compiled():
        return sorted(m["source_name"] for m in _compiled_sources().values())
    return sorted(_source_dirs())


def get_manifest(source_name: str) -> dict:
    """返回书源的 `source.json` 内容（非编译模式校验能力段 ⇔ .py 文件）。"""
    if _is_compiled():
        dirname = _compiled_dir_by_source().get(source_name)
        if dirname is None or dirname not in _compiled_sources():
            raise KeyError(f"unknown source: {source_name}")
        return _compiled_sources()[dirname]
    entry = _source_dir(source_name)
    if entry is None:
        raise KeyError(f"unknown source: {source_name}")
    d, _ = entry
    manifest = load_manifest(d)
    check_capability_files(d, manifest)  # spec 规则 1：能力段 ⇔ .py 文件双向一致
    return manifest


def capabilities(source_name: str) -> dict[str, str]:
    """返回 `{capability: mode}`；书源不存在或声明非法时返回 `{}`。

    唯一例外：`source_name` 重复（撞名）直接抛——那是环境级错误，不该被静默
    吞成「未声明能力」（否则后端 `GET /config/sources/{name}` 会显示空能力）。
    """
    try:
        manifest = get_manifest(source_name)
    except DuplicateSourceNameError:
        raise
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


def _resolve_private(d: Path, capability: str):
    """私有源在包外（`NLD_PRIVATE_SOURCES`），必须走 spec_from_file_location（spec:163）。"""
    candidate = d / f"{capability}.py"
    if not candidate.is_file():
        raise ImportError(f"{d} 缺少能力文件 {candidate.name}")
    module_name = f"novelbase_private.sources.{d.name}.{capability}"
    spec = importlib_util.spec_from_file_location(module_name, str(candidate))
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load spec from {candidate}")
    module = importlib_util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, capability, None)
    if fn is None:
        raise ImportError(f"{candidate} 里没有名为 {capability} 的函数")
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
        entry = _source_dir(source_name)
        if entry is None:
            raise ImportError(f"unknown source: {source_name}")
        d, is_builtin = entry
        # 全局唯一：每个 source_name 至多一个目录 → 无需「内置优先、私有补齐」循环
        fn = (_resolve_import(source_name, capability, d.name) if is_builtin
              else _resolve_private(d, capability))

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
