"""Source 能力发现与动态分发（公共 API）。

本模块是 source 子系统的唯一入口，负责：
- 元数据注册：register_source() / list_sources()
- 能力发现：capabilities(name)
- 动态分发：resolve(name, mode, function, variant=None)
- URL 识别：platform_from_url() / resolve_book_url()

新增源平台：直接在 sources/ 下创建目录/文件即可，零注册表修改。

私有源：设置环境变量 NLD_PRIVATE_SOURCES 指向外部目录，镜像 sources/{name}/
结构，capabilities/resolve 自动合并。公开仓库不包含私有实现。
"""

import os
import threading
from importlib import import_module, util as importlib_util
from inspect import signature
from pathlib import Path

from .sources.contracts import CAPABILITY_META

__all__ = [
    "capabilities",
    "resolve",
    "list_sources",
    "register_source",
    "platform_from_url",
    "resolve_book_url",
]

_PRIVATE_SOURCES_ROOT: str | None = os.environ.get("NLD_PRIVATE_SOURCES")

_lock = threading.Lock()
_cache_source: dict[str, dict] | None = None


def _is_compiled() -> bool:
    """检测是否为 Nuitka/PyInstaller 编译产物。"""
    return "__compiled__" in globals()


# ═══════════════════════════════════════════════════════════════════
# 元数据注册（source 名 / hosts 等）
# ═══════════════════════════════════════════════════════════════════

def _scan_sources() -> dict[str, dict]:
    """扫描 sources/ 目录，收集每个 source 的 NAME / SHOW_NAME / HOSTS 等。

    Returns:
        {module_name: {"name": ..., "show_name": ..., "hosts": ...}}
    """
    result = {}
    pkg_dir = Path(__file__).parent / "sources"
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
            module = import_module(f".sources.{module_name}", __package__)
            result[module_name] = {
                "name": getattr(module, "NAME", module_name),
                "show_name": getattr(module, "SHOW_NAME", module_name),
                "hosts": getattr(module, "HOSTS", ()),
            }
        except ImportError as e:
            print(f"load source failed {module_name} reason: {e}")

    return result


def _load_manifest_sources() -> dict[str, dict]:
    """从 _manifest.py 加载书源数据（Nuitka 模式）。"""
    try:
        from .utils import _manifest
        return _manifest._flat_sources()
    except ImportError:
        return {}


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


def list_sources() -> list[str]:
    """列出所有可用源名称（开发模式目录扫描，编译模式 manifest）。"""
    if _is_compiled():
        try:
            from .utils import _manifest
            return list(_manifest._SOURCES.keys())
        except ImportError:
            return []
    pkg_dir = Path(__file__).parent / "sources"
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
    """将输入转为完整 URL。

    - 已是完整 URL 则直接返回
    - 其他输入（含 hash id）无法识别时报 ValueError
    """
    raw = raw.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    raise ValueError(f"无法识别书源或 ID 格式: {raw}")


# ═══════════════════════════════════════════════════════════════════
# 能力发现 + 动态分发
# ═══════════════════════════════════════════════════════════════════

def _load_manifest_capabilities(name: str) -> dict[str, dict[str, list[str]]]:
    """Nuitka 模式从 manifest 加载能力矩阵。"""
    try:
        from .utils import _manifest
        return _manifest._SOURCES.get(name, {}).get("modes", {})
    except ImportError:
        return {}


def _scan_source_dirs(name: str) -> list[Path]:
    """返回所有 source 目录路径（内置 + 私有）。

    私有目录路径由 NLD_PRIVATE_SOURCES 环境变量指定，结构镜像 sources/{name}/。
    内置目录始终排在前面。
    """
    dirs = [Path(__file__).parent / "sources" / name]
    if _PRIVATE_SOURCES_ROOT:
        private_dir = Path(_PRIVATE_SOURCES_ROOT) / name
        if private_dir.is_dir():
            dirs.append(private_dir)
    return dirs


def _scan_capabilities(pkg_dir: Path) -> dict[str, dict[str, list[str]]]:
    """扫描单个 source 目录，返回 {mode: {variant: [functions]}}。

    目录不存在时返回空 dict。
    """
    if not pkg_dir.is_dir():
        return {}

    result: dict[str, dict[str, list[str]]] = {}
    for mode_dir in sorted(pkg_dir.iterdir()):
        if not mode_dir.is_dir() or mode_dir.name.startswith("_") or mode_dir.name == "__pycache__":
            continue
        mode = mode_dir.name

        variants: dict[str, list[str]] = {}
        for sub in sorted(mode_dir.iterdir()):
            if sub.is_dir() and not sub.name.startswith("_") and sub.name != "__pycache__":
                funcs: list[str] = []
                for func_name, meta in CAPABILITY_META.items():
                    if (sub / f"{meta['file_stem']}.py").exists():
                        funcs.append(func_name)
                if funcs:
                    variants[sub.name] = funcs

        # 无 fallback：mode 必须用 variant 子目录组织（如 default/），
        # 直接放在 mode 根的文件不再被识别
        if variants:
            result[mode] = variants

    return result


def capabilities(name: str) -> dict[str, dict[str, list[str]]]:
    """扫描内置 + 私有 source 目录，返回合并后的可用能力矩阵。

    返回结构统一为 {mode: {variant: [functions]}}。
    无 variant 子目录的 mode 使用 "default" 作为 variant key。
    私有源的同名 variant 覆盖内置源（允许本地覆盖/补丁）。
    Nuitka 编译后目录扫描失败时退回硬编码矩阵。

    >>> capabilities("fanqie")
    {"api": {"oiapi": [...], "rain": [...]},
     "browser": {"default": [...]},
     "requests": {"default": [...]}}

    无该 mode 则不出现 key；source 不存在返回空 dict。
    """
    merged: dict[str, dict[str, list[str]]] = {}
    for pkg_dir in _scan_source_dirs(name):
        caps = _scan_capabilities(pkg_dir)
        for mode, variants in caps.items():
            if mode not in merged:
                merged[mode] = {}
            merged[mode].update(variants)  # 私有源覆盖同名 variant
    # Nuitka: 目录扫描失败（exe 内无 .py 文件），从 manifest 读取
    if not merged and _is_compiled():
        merged = _load_manifest_capabilities(name)
    return merged


def resolve(name: str, mode: str, function: str, variant: str | None = None):
    """动态 import 并返回同步函数。

    >>> fn = resolve("fanqie", "api", "search", "oiapi")
    >>> results = fn("关键词", engine)

    variant 为 None 时优先取 "default"，无 "default" 则取第一个可用 variant；
    无 variant 子目录的 mode 使用 "default" 或省略 variant。

    内置源优先用 import_module 加载；私有源用 spec_from_file_location 加载。
    """
    caps = capabilities(name)
    if mode not in caps:
        raise ValueError(f"mode {mode!r} not available for {name!r}. Available: {list(caps)}")

    mode_caps = caps[mode]
    variant_keys = list(mode_caps.keys())

    if variant is None:
        variant = "default" if "default" in mode_caps else variant_keys[0]
    elif variant not in mode_caps:
        raise ValueError(f"variant {variant!r} not available for {name}/{mode}. Available: {variant_keys}")

    meta = CAPABILITY_META.get(function)
    if meta is None:
        raise ValueError(f"unknown function {function!r}. Known: {list(CAPABILITY_META)}")
    file_stem = meta["file_stem"]

    # 查找 variant 来源：先内置，后私有
    _sources = [Path(__file__).parent / "sources" / name]
    if _PRIVATE_SOURCES_ROOT:
        _sources.append(Path(_PRIVATE_SOURCES_ROOT) / name)

    found = False
    for src_dir in _sources:
        # 统一 variant 子目录结构：mode/variant/stem.py（无 default 根 fallback）
        candidate = src_dir / mode / variant / f"{file_stem}.py"
        if candidate.is_file():
            found = True
            break

    if not found:
        # Nuitka: .py 文件不存在（编译进 exe），直接试 import_module
        if src_dir == _sources[0]:
            module_path = f"novelbase.sources.{name}.{mode}.{variant}.{file_stem}"
            try:
                module = import_module(module_path)
                fn = getattr(module, file_stem)
            except (ImportError, AttributeError) as e:
                raise ImportError(
                    f"Failed to resolve {name}/{mode}/{variant}/{file_stem}: {e}"
                ) from e
        else:
            raise ImportError(
                f"Failed to resolve {name}/{mode}/{variant}/{file_stem}: file not found"
            )

    # 内置源用 import_module，私有源用 spec_from_file_location
    if src_dir == _sources[0]:
        module_path = f"novelbase.sources.{name}.{mode}.{variant}.{file_stem}"
        try:
            module = import_module(module_path)
            fn = getattr(module, file_stem)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Failed to resolve {module_path}: {e}") from e
    else:
        # 私有源：从文件路径加载
        module_name = f"novelbase_private.sources.{name}.{mode}.{variant}.{file_stem}"
        spec = importlib_util.spec_from_file_location(module_name, str(candidate))
        if spec is None or spec.loader is None:
            raise ImportError(f"Failed to load spec from {candidate}")
        module = importlib_util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fn = getattr(module, file_stem)

    # 运行时签名校验：确保函数接受必需参数
    sig = signature(fn)
    missing = [p for p in meta["required_params"] if p not in sig.parameters]
    if missing:
        raise ValueError(
            f"{candidate} 签名缺少参数: {missing}. "
            f"当前签名: {list(sig.parameters)}"
        )
    return fn
