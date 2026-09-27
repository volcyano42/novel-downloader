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
    """读取并校验 `source_dir/source.json`。"""
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

    config = manifest.get("default_config", {})
    if not isinstance(config, dict):
        raise ManifestError(f"{path} 的 default_config 必须是对象")
    common = manifest.get("common", {})
    if not isinstance(common, dict):
        raise ManifestError(f"{path} 的 common 必须是对象")

    # 1) 定每个能力段的有效 mode（自身 mode 优先，否则继承 common.mode）
    effective: dict[str, str] = {}
    for capability, section in config.items():
        if capability not in _capability_names():
            raise ManifestError(f"{path} 的 default_config 含未知能力 {capability!r}")
        if not isinstance(section, dict):
            raise ManifestError(f"{path} 的能力段 {capability} 必须是对象")
        mode = section.get("mode", common.get("mode"))
        if mode not in MODE_FIELDS:
            raise ManifestError(
                f"{path} 的 {capability}.mode 非法或缺失: {mode!r}（可选 {list(MODE_FIELDS)}）"
            )
        effective[capability] = mode

    # 2) common 的字段必须对所有出现的能力 mode 都合法（各 mode 字段集的交集）
    if common:
        modes = set(effective.values())
        if not modes:
            # common 非空但 default_config 未声明任何能力段 → 无 mode 可校验
            raise ManifestError(
                f"{path} 的 common 非空但 default_config 未声明任何能力段"
            )
        allowed_common = set.intersection(*(set(MODE_FIELDS[m]) for m in modes))
        for key in common:
            if key not in allowed_common:
                raise ManifestError(
                    f"{path} 的 common 字段 {key!r} 对出现的 mode {sorted(modes)} 不都合法"
                    f"（公共字段只能是 {sorted(allowed_common)}）"
                )

    # 3) 合并 common（能力段覆盖），并逐段校验字段合法性
    merged: dict[str, dict] = {}
    for capability, section in config.items():
        mode = effective[capability]
        fields = {**common, **section}
        allowed = set(MODE_FIELDS[mode])
        for key in fields:
            if key not in allowed:
                raise ManifestError(
                    f"{path} 的 {capability} 段字段 {key!r} 不属于 mode={mode}（可选 {sorted(allowed)}）"
                )
        merged[capability] = fields

    manifest["default_config"] = merged
    return manifest


def check_capability_files(source_dir: Path, manifest: dict[str, Any]) -> None:
    """能力段存在 ⇔ 对应 `.py` 文件存在（双向）。"""
    source_dir = Path(source_dir)
    declared = set(manifest.get("default_config", {}))
    present = {
        name for name in _capability_names()
        if (source_dir / f"{name}.py").is_file()
    }
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
