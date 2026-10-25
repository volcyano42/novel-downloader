"""书源 `source.json` 的加载与校验。

一个书源 = `novelbase/sources/{dir}/`，内含：
- `__init__.py`（空，包标记）
- `source.json`（身份 + 出厂配置）
- 能力文件 `search.py` / `novel_info.py` / `chapter_list.py` / `chapter_content.py`（按需）
"""

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

IDENTITY_FIELDS = ("source_name",)

# 字段集按 mode 划分，与 novelbase/core/options.py 的三个 dataclass 一一对应
_MODE_COMMON = ("mode", "timeout", "retry_times", "delay", "backoff_factor")
MODE_FIELDS: dict[str, tuple[str, ...]] = {
    "api":      _MODE_COMMON + ("key", "params"),
    "requests": _MODE_COMMON + ("headers", "cookies", "proxies"),
    "browser":  _MODE_COMMON + ("browser_type", "headless", "user_data_dir",
                                "viewport", "extra_args", "auto_reconnect"),
}

MANIFEST_NAME = "source.json"


class ManifestError(ValueError):
    """`source.json` 缺失、字段非法或与目录内容不一致。"""


class DuplicateSourceNameError(ManifestError):
    """同一个 `source_name` 被两个书源目录声明（全局唯一被破坏）。"""


def load_manifest(source_dir: Path) -> dict[str, Any]:
    """读取并校验 `source_dir/source.json`。

    格式（2026-10-25 起，**唯一格式**）：一个书源只有**一个 mode 和一套字段**，
    不再按能力分化::

        {"source_name": "x", "mode": "requests", "timeout": 30, "headers": {...}, ...}

    旧的分段写法（`common` + `default_config.{能力}`）**已废弃，不做兼容**——
    novelbase 为预览版，允许破坏性变更；遇到旧写法会报错而不是静默猜。

    解析后归一化成 `manifest["default_config"] = {能力: 同一套完整字段(含 mode)}`，
    下游 `capabilities()` / `merged_source_config()` 无需感知具体格式。
    """
    path = Path(source_dir) / MANIFEST_NAME
    if not path.is_file():
        raise ManifestError(f"缺少 {MANIFEST_NAME}: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ManifestError(f"{path} 不是合法 JSON: {e}") from e
    if not isinstance(manifest, dict):
        raise ManifestError(f"{path} 顶层必须是对象")

    for field in IDENTITY_FIELDS:
        if field not in manifest:
            raise ManifestError(f"{path} 缺少必填字段 {field}")
    if not isinstance(manifest["source_name"], str) or not manifest["source_name"]:
        raise ManifestError(f"{path} 的 source_name 必须是非空字符串")
    for optional in ("source_alias", "source_group"):
        if optional in manifest and not (isinstance(manifest[optional], str) and manifest[optional].strip()):
            raise ManifestError(f"{path} 的 {optional} 必须是非空字符串")

    return _normalize_flat(manifest, path)


def _normalize_flat(manifest: dict[str, Any], path: Path) -> dict[str, Any]:
    """平铺格式：顶层 `mode` + 该 mode 允许的全部字段。"""
    mode = manifest.get("mode")
    if mode not in MODE_FIELDS:
        raise ManifestError(
            f"{path} 的 mode 非法或缺失: {mode!r}（可选 {list(MODE_FIELDS)}）"
        )
    allowed = set(MODE_FIELDS[mode])
    fields: dict[str, Any] = {}
    for key, value in manifest.items():
        if key in IDENTITY_FIELDS or key in ("source_alias", "source_group") or key == "mode":
            continue
        if key not in allowed:
            raise ManifestError(
                f"{path} 的字段 {key!r} 不属于 mode={mode}（可选 {sorted(allowed)}）"
            )
        fields[key] = value

    # 归一化：**按目录里实际存在的能力文件**生成能力段（能力由文件系统发现，
    # 不在 manifest 里声明）。只实现了部分能力的书源（如只有 search.py）就只暴露那一项。
    #
    # 注意：目录里一个能力文件都没有时**不在此报错** —— 那会让 `scan_source_names()`
    # 在扫描阶段就静默跳过该目录（strict=False），下游只能看到 KeyError。
    # “没任何能力”由 `check_capability_files()` 在 `get_manifest()` 时报。
    caps = tuple(c for c in _capability_names() if (path.parent / f"{c}.py").is_file())
    section = {"mode": mode, **fields}
    manifest["default_config"] = {cap: dict(section) for cap in caps}
    return manifest


def check_capability_files(source_dir: Path, manifest: dict[str, Any]) -> None:
    """书源目录必须至少实现一个能力，且归一化后的能力段与文件严格对应。

    能力由文件系统发现（`_normalize_flat` 按 `.py` 存在性生成能力段），所以
    `declared` 天然 ⊆ `present`；这里主要拦“一个能力文件都没有”的目录。
    """
    source_dir = Path(source_dir)
    declared = set(manifest.get("default_config", {}))
    present = {
        name for name in _capability_names()
        if (source_dir / f"{name}.py").is_file()
    }
    if not declared:
        raise ManifestError(
            f"{source_dir} 没有任何能力文件（至少需要 {list(_capability_names())} 之一）"
        )
    missing = declared - present
    if missing:
        raise ManifestError(
            f"{source_dir} 声明了能力段但缺少文件: {sorted(f'{m}.py' for m in missing)}"
        )
    extra = present - declared
    if extra:
        raise ManifestError(
            f"{source_dir} 有文件但 default_config 未声明: {sorted(extra)}"
        )


def scan_source_names(roots: Iterable[Path], *, strict: bool = False) -> dict[str, Path]:
    """扫多个根下的书源目录，返回 `{source_name: 目录}`。

    `source_name` 是全局唯一 id：内置根与私有根是同一命名空间，同一个名字出现
    第二次（含跨根）即抛 `DuplicateSourceNameError`。

    - 非目录项、`_` 开头的目录、无 `source.json` 的目录 → 跳过
    - 单源 `load_manifest()` 抛 `ManifestError`：`strict=True` 冒泡，否则跳过该目录
      （沿用运行时容错；构建期用 `strict=True` 保证不漏）
    - 根不存在或不是目录 → 跳过该根
    - `roots` 有序，先出现的目录先占名（报错消息里是「先占者 vs 后来者」）
    """
    found: dict[str, Path] = {}
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("_"):
                continue
            if not (entry / MANIFEST_NAME).is_file():
                continue
            try:
                manifest = load_manifest(entry)
            except ManifestError:
                if strict:
                    raise
                continue
            name = manifest["source_name"]
            if name in found:
                raise DuplicateSourceNameError(
                    f"source_name {name!r} 重复：{found[name]} 与 {entry} 都声明了它。"
                    f"请给其中一个书源换 source_name（目录名可不变，二者本就解耦）"
                )
            found[name] = entry
    return found


def _capability_names() -> tuple[str, ...]:
    from .contracts import CAPABILITY_META
    return tuple(CAPABILITY_META)
