"""Source 能力发现与动态分发（公共 API）。

本模块提供 source 开发者和使用者需要的入口：
- capabilities(name) → 返回统一结构的可用能力矩阵
- resolve(name, mode, function, variant=None) → 动态 import 并返回同步函数
- list_sources() → 列出所有可用源名称
- register_source() → 返回已注册 source 元数据

新增源平台：直接在 sources/ 下创建目录/文件即可，零注册表修改。

私有源：设置环境变量 NLD_PRIVATE_SOURCES 指向外部目录，镜像 sources/{name}/
结构，capabilities/resolve 自动合并。公开仓库不包含私有实现。
"""

import os
from importlib import import_module, util as importlib_util
from inspect import signature
from pathlib import Path

from .sources.contracts import CAPABILITY_META
from .utils.registry import list_sources, register_source  # noqa: F401 — 重导出


__all__ = ["capabilities", "resolve", "list_sources", "register_source"]

_PRIVATE_SOURCES_ROOT: str | None = os.environ.get("NLD_PRIVATE_SOURCES")


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

        direct_funcs: list[str] = []
        for func_name, meta in CAPABILITY_META.items():
            if (mode_dir / f"{meta['file_stem']}.py").exists():
                direct_funcs.append(func_name)

        if variants:
            result[mode] = variants
        elif direct_funcs:
            result[mode] = {"default": direct_funcs}

    return result


def capabilities(name: str) -> dict[str, dict[str, list[str]]]:
    """扫描内置 + 私有 source 目录，返回合并后的可用能力矩阵。

    返回结构统一为 {mode: {variant: [functions]}}。
    无 variant 子目录的 mode 使用 "default" 作为 variant key。
    私有源的同名 variant 覆盖内置源（允许本地覆盖/补丁）。

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
        if variant == "default":
            # default variant: mode 目录下直接有 .py 文件
            candidate = src_dir / mode / f"{file_stem}.py"
        else:
            # 命名 variant: mode/variant/ 子目录下有 .py 文件
            candidate = src_dir / mode / variant / f"{file_stem}.py"
        if candidate.is_file():
            found = True
            break

    if not found:
        raise ImportError(
            f"Failed to resolve {name}/{mode}/{variant}/{file_stem}: file not found"
        )

    # 内置源用 import_module，私有源用 spec_from_file_location
    if src_dir == _sources[0]:
        if variant == "default":
            module_path = f"novelbase.sources.{name}.{mode}.{file_stem}"
        else:
            module_path = f"novelbase.sources.{name}.{mode}.{variant}.{file_stem}"
        try:
            module = import_module(module_path)
            fn = getattr(module, file_stem)
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Failed to resolve {module_path}: {e}") from e
    else:
        # 私有源：从文件路径加载
        module_name = f"novelbase_private.sources.{name}.{mode}"
        if variant != "default":
            module_name += f".{variant}"
        module_name += f".{file_stem}"
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
