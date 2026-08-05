"""Source 能力发现与动态分发（公共 API）。

本模块提供 source 开发者和使用者需要的入口：
- capabilities(name) → 返回统一结构的可用能力矩阵
- resolve(name, mode, function, variant=None) → 动态 import 并返回同步函数
- list_sources() → 列出所有可用源名称
- register_source() → 返回已注册 source 元数据

新增源平台：直接在 sources/ 下创建目录/文件即可，零注册表修改。
"""

from importlib import import_module
from inspect import signature
from pathlib import Path

from .sources.contracts import CAPABILITY_META
from .utils.registry import list_sources, register_source  # noqa: F401 — 重导出


__all__ = ["capabilities", "resolve", "list_sources", "register_source"]


def capabilities(name: str) -> dict[str, dict[str, list[str]]]:
    """扫描 sources/{name}/ 目录，返回可用能力矩阵。

    返回结构统一为 {mode: {variant: [functions]}}。
    无 variant 子目录的 mode 使用 "default" 作为 variant key。

    >>> capabilities("fanqie")
    {"api": {"oiapi": ["search", "novel_info", "chapter_list", "chapter_content"],
             "rain": ["search", "novel_info", "chapter_list", "chapter_content"]},
     "browser": {"default": ["search", "novel_info", "chapter_list", "chapter_content"]},
     "requests": {"default": ["search", "novel_info", "chapter_list", "chapter_content"]}}

    无该 mode 则不出现 key；source 不存在返回空 dict。
    """
    pkg_dir = Path(__file__).parent / "sources" / name
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

        # 检查 mode 目录自身是否有 .py 文件（无 variant 子目录模式）
        direct_funcs: list[str] = []
        for func_name, meta in CAPABILITY_META.items():
            if (mode_dir / f"{meta['file_stem']}.py").exists():
                direct_funcs.append(func_name)

        if variants:
            result[mode] = variants
        elif direct_funcs:
            result[mode] = {"default": direct_funcs}

    return result


def resolve(name: str, mode: str, function: str, variant: str | None = None):
    """动态 import 并返回同步函数。

    >>> fn = resolve("fanqie", "api", "search", "oiapi")
    >>> results = fn("关键词", engine)

    variant 为 None 时优先取 "default"，无 "default" 则取第一个可用 variant；
    无 variant 子目录的 mode 使用 "default" 或省略 variant。
    """
    caps = capabilities(name)
    if mode not in caps:
        raise ValueError(f"mode {mode!r} not available for {name!r}. Available: {list(caps)}")

    mode_caps = caps[mode]  # dict[str, list[str]]
    variant_keys = list(mode_caps.keys())

    if variant is None:
        variant = "default" if "default" in mode_caps else variant_keys[0]
    elif variant not in mode_caps:
        raise ValueError(f"variant {variant!r} not available for {name}/{mode}. Available: {variant_keys}")

    meta = CAPABILITY_META.get(function)
    if meta is None:
        raise ValueError(f"unknown function {function!r}. Known: {list(CAPABILITY_META)}")
    file_stem = meta["file_stem"]

    # "default" 表示无 variant 子目录，模块路径不包含 variant 段
    if variant == "default":
        module_path = f"novelbase.sources.{name}.{mode}.{file_stem}"
    else:
        module_path = f"novelbase.sources.{name}.{mode}.{variant}.{file_stem}"

    try:
        module = import_module(module_path)
        fn = getattr(module, file_stem)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Failed to resolve {module_path}: {e}") from e

    # 运行时签名校验：确保函数接受必需参数
    sig = signature(fn)
    missing = [p for p in meta["required_params"] if p not in sig.parameters]
    if missing:
        raise ValueError(
            f"{module_path} 签名缺少参数: {missing}. "
            f"当前签名: {list(sig.parameters)}"
        )
    return fn
