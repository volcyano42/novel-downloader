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

import hashlib
import os
import sys
from importlib import import_module
from importlib import util as importlib_util
from inspect import signature
from pathlib import Path

from .sources.contracts import CAPABILITY_META
from .sources.manifest import (
    DuplicateSourceNameError,
    ManifestError,
    check_capability_files,
    load_manifest,
    scan_source_names,
)

__all__ = ["list_sources", "get_manifest", "capabilities", "resolve",
           "resolve_book_url", "add_source_root", "source_roots"]

_PRIVATE_SOURCES_ROOT: str | None = os.environ.get("NLD_PRIVATE_SOURCES")

# 多根源环境变量（`os.pathsep` 分隔）。与 `NLD_PRIVATE_SOURCES` 同在函数体内读取：
# 测试用 `monkeypatch.setattr(_PRIVATE_SOURCES_ROOT, ...)` 依赖这一点，导入期快照会让它失效。
_SOURCE_ROOTS_ENV = "NLD_SOURCE_ROOTS"

# `add_source_root()` 注入的显式根（`shared` 层用它在 import 时加上 `<APP_DATA>/sources`）。
_EXPLICIT_ROOTS: list[Path] = []

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


def add_source_root(path: str | Path) -> None:
    """追加一个显式源根（重复追加同一路径无副作用）。

    `novelbase` 不认识 `app_data` 布局（它是可 `pip install` 的纯库，不能反向
    依赖 `shared`）。用户根由 `shared.config` 在 import 时调用本函数接线。
    """
    p = Path(path)
    if p not in _EXPLICIT_ROOTS:
        _EXPLICIT_ROOTS.append(p)


def _resolve_source_roots() -> list[Path]:
    """当前生效的有序源根（只保留真实存在的目录）。

    顺序：`NLD_SOURCE_ROOTS` → 旧 `NLD_PRIVATE_SOURCES` → `add_source_root()`
    注入 → 官方 `builtin` 根。

    顺序**不改变语义**：`source_name` 跨根撞名一律抛
    `DuplicateSourceNameError`，不退化成一占先得；顺序只影响报错消息里的
    先占者/后来者。
    """
    roots: list[Path] = []
    raw = os.environ.get(_SOURCE_ROOTS_ENV, "")
    roots += [Path(p) for p in raw.split(os.pathsep) if p.strip()]
    if _PRIVATE_SOURCES_ROOT:
        roots.append(Path(_PRIVATE_SOURCES_ROOT))
    roots += list(_EXPLICIT_ROOTS)
    roots.append(_SOURCES_DIR / "builtin")
    return [r for r in roots if r.is_dir()]


def source_roots() -> list[Path]:
    """当前生效的有序源根（只读快照，供调用方展示/诊断）。"""
    return _resolve_source_roots()


def _source_dirs() -> dict[str, Path]:
    """全局唯一书源表 `{source_name: 目录}`。

    任一 `source_name` 重复（含跨根）→ `DuplicateSourceNameError`。
    """
    return scan_source_names(_resolve_source_roots())


def _source_dir(source_name: str) -> Path | None:
    """源目录；未知 `source_name` 返回 `None`。"""
    return _source_dirs().get(source_name)


def _merged_compiled_table() -> tuple[dict[str, dict], dict[str, Path]]:
    """编译模式的两张表：`{source_name: 静态 manifest}` + `{source_name: 目录}`。

    官方源被编译进产物、文件系统里没有 `.py` → 只能读 `_manifest.py` 静态表；
    用户源仍在文件系统源根里 → 照常扫描。**两表合并**，撞名口径与非编译模式一致
    （不静默取一个）。
    """
    static = {m["source_name"]: m for m in _compiled_sources().values()}
    dirs = _compiled_dir_by_source()
    orphan = sorted(set(static) - set(dirs))
    if orphan:
        # 构建产物损坏：SOURCES 里有、SOURCE_DIRS 里没有 → 否则 get_manifest() 能用、
        # resolve() 却抛 unknown source，一半可用比彻底坏更难查。
        raise ManifestError(
            f"编译静态表不一致：{orphan} 存在于 _manifest.SOURCES 但没有 SOURCE_DIRS 映射。"
            f"请重新运行 python -m novelbase.utils.build_manifest"
        )
    from_fs = scan_source_names(_resolve_source_roots())
    clash = sorted(set(static) & set(from_fs))
    if clash:
        raise DuplicateSourceNameError(
            f"source_name {clash} 同时出现在编译静态表与文件系统源根："
            f"目录 {from_fs[clash[0]]} 与静态表重复。请给其中一个书源换 source_name"
        )
    return static, from_fs


def list_sources() -> list[str]:
    """列出全部书源的 source_name（排序；重名 → DuplicateSourceNameError）。"""
    if _is_compiled():
        static, from_fs = _merged_compiled_table()
        return sorted({*static, *from_fs})
    return sorted(_source_dirs())


def get_manifest(source_name: str) -> dict:
    """返回书源的 `source.json` 内容（非编译模式校验能力段 ⇔ .py 文件）。"""
    if _is_compiled():
        static, from_fs = _merged_compiled_table()
        if source_name in static:
            return static[source_name]
        d = from_fs.get(source_name)
        if d is None:
            raise KeyError(f"unknown source: {source_name}")
        manifest = load_manifest(d)
        check_capability_files(d, manifest)
        return manifest
    d = _source_dir(source_name)
    if d is None:
        raise KeyError(f"unknown source: {source_name}")
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


def _resolve_compiled(source_name: str, capability: str, dirname: str):
    """**仅编译模式**：产物里官方源的 `.py` 已被编译、文件系统无源文件，
    只能按包路径 `import_module`（详见 §5 的已知特例）。"""
    module_path = f"novelbase.sources.builtin.{dirname}.{capability}"
    try:
        module = import_module(module_path)
    except ImportError as e:
        raise ImportError(f"Failed to resolve {module_path}: {e}") from e
    fn = getattr(module, capability, None)
    if fn is None:
        raise ImportError(f"{module_path} 里没有名为 {capability} 的函数")
    return fn


def _module_name(root: Path, dirname: str, capability: str) -> str:
    """模块名必须含根标识：多根下同名目录否则会撞同一个 `sys.modules` key。"""
    tag = hashlib.sha1(str(root.resolve()).encode()).hexdigest()[:8]
    return f"nld_src_{tag}.{dirname}.{capability}"


def _load_capability(source_dir: Path, capability: str) -> object:
    """从源目录加载能力函数（不依赖包路径，包内包外同一条路径）。

    模块按「根哈希 + 目录名 + 能力」注册进 `sys.modules`，避免同一源被反复
    `exec_module`（每次章节下载都会 resolve）。
    """
    candidate = source_dir / f"{capability}.py"
    if not candidate.is_file():
        raise ImportError(f"{source_dir} 缺少能力文件 {candidate.name}")
    name = _module_name(source_dir.parent, source_dir.name, capability)
    cached = sys.modules.get(name)
    if cached is not None:
        fn = getattr(cached, capability, None)
        if fn is not None:
            return fn
    spec = importlib_util.spec_from_file_location(name, str(candidate))
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load spec from {candidate}")
    module = importlib_util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)   # 加载失败不留下半成品
        raise
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
        # 编译模式：官方源的能力模块已被打进产物，文件系统里没有 .py 可查，
        # 只能按包路径 import；用户源在文件系统里，照常走 _load_capability。
        static, from_fs = _merged_compiled_table()
        if source_name in static:
            dirname = _compiled_dir_by_source().get(source_name)
            if dirname is None:
                raise ImportError(f"unknown source: {source_name}")
            fn = _resolve_compiled(source_name, capability, dirname)
        else:
            d = from_fs.get(source_name)
            if d is None:
                raise ImportError(f"unknown source: {source_name}")
            fn = _load_capability(d, capability)
    else:
        d = _source_dir(source_name)
        if d is None:
            raise ImportError(f"unknown source: {source_name}")
        # 全局唯一：每个 source_name 至多一个目录 → 无需「内置优先、私有补齐」循环；
        # 加载路径也不再看「是否在包内」—— 官方源与用户源完全平等
        fn = _load_capability(d, capability)

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
