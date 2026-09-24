"""书源 `source.json` 的加载与校验。

一个书源 = `novelbase/sources/{dir}/`，内含：
- `__init__.py`（空，包标记）
- `source.json`（身份 + 出厂配置）
- 能力文件 `search.py` / `novel_info.py` / `chapter_list.py` / `chapter_content.py`（按需）
"""

import json
from pathlib import Path
from typing import Any

IDENTITY_FIELDS = ("source_name", "enabled")

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
    if not isinstance(manifest["enabled"], bool):
        raise ManifestError(f"{path} 的 enabled 必须是布尔值")

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


def _capability_names() -> tuple[str, ...]:
    from .contracts import CAPABILITY_META
    return tuple(CAPABILITY_META)
