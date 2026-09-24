# -*- coding: utf-8 -*-
"""Config loader: paths, config.yaml, groups.yaml, site configs."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from novelbase.core.options import Options
from novelbase.utils.logger import get_logger

_log = get_logger("cli.config")

APP_DATA: Path | None = None
CONFIG_DIR: Path | None = None


def _get_app_data_dir() -> Path:
    """Get app_data directory.

    Priority: NLD_APP_DATA env > executable dir (frozen) > script dir.
    """
    env = os.environ.get("NLD_APP_DATA")
    if env:
        return Path(env).resolve()
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        app_data = exe_dir / "app_data"
        if not app_data.exists():
            # 首次运行，从 _MEIPASS 复制默认配置
            _meipass = Path(sys._MEIPASS)
            if (_meipass / "app_data").exists():
                _copy_dir(_meipass / "app_data", app_data)
            else:
                app_data.mkdir(parents=True, exist_ok=True)
        return app_data
    return Path(__file__).parent.parent / "app_data"


def _copy_dir(src: Path, dst: Path) -> None:
    """Recursively copy directory. Preserves existing files."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copy_dir(item, target)
        elif not target.exists():
            shutil.copy2(item, target)


def _resolve_paths(value: Any) -> Any:
    """Recursively replace 'app_data/' or 'app_data\\' with actual APP_DATA path."""
    app_data_str = str(APP_DATA)
    if isinstance(value, str):
        if value.startswith("app_data/") or value.startswith("app_data\\"):
            return value.replace("app_data", app_data_str, 1)
        return value
    if isinstance(value, list):
        return [_resolve_paths(v) for v in value]
    if isinstance(value, dict):
        return {k: _resolve_paths(v) for k, v in value.items()}
    return value


def init_paths() -> None:
    """Initialize global path constants (called once at module import)."""
    global APP_DATA, CONFIG_DIR
    if APP_DATA is not None:
        return
    APP_DATA = _get_app_data_dir()
    CONFIG_DIR = APP_DATA / "config"


init_paths()


def load_main_config() -> dict:
    """Load app_data/config/config.yaml."""
    path = CONFIG_DIR / "config.yaml"
    if not path.exists():
        _log.warning("config not found: %s", path)
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})


def save_main_config(cfg: dict) -> None:
    """Save app_data/config/config.yaml."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = CONFIG_DIR / "config.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)


def load_groups() -> dict:
    """Load groups from user_data.db (migrated from groups.yaml).

    Returns: {group_name: {novel_id: {"pending_export": bool}, ...}, ...}
    """
    from shared.user_data import load_groups as _db_load
    return _db_load()


def save_groups(groups: dict) -> None:
    """Save groups to user_data.db."""
    from shared.user_data import save_groups as _db_save
    _db_save(groups)


def load_site_config(platform: str) -> dict:
    """Load app_data/config/sites/{platform}.yaml."""
    path = CONFIG_DIR / "sites" / f"{platform}.yaml"
    if not path.exists():
        _log.warning("site config not found: %s", path)
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})


def save_site_config(platform: str, site_cfg: dict) -> None:
    """Save app_data/config/sites/{platform}.yaml."""
    (CONFIG_DIR / "sites").mkdir(parents=True, exist_ok=True)
    path = CONFIG_DIR / "sites" / f"{platform}.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(site_cfg, f, allow_unicode=True, default_flow_style=False)


def load_format_configs() -> dict[str, dict]:
    """Load app_data/config/formats/*.yaml.

    Returns: {fmt_name: config_dict} e.g. {"txt": {"enabled": true, "output_path": ...}}
    """
    fmt_dir = CONFIG_DIR / "formats"
    if not fmt_dir.exists():
        return {}
    result = {}
    for p in sorted(fmt_dir.glob("*.yaml")):
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            # handle both flat and nested formats
            if isinstance(data, dict):
                for name, cfg in data.items():
                    result[name] = _resolve_paths(cfg) if isinstance(cfg, dict) else cfg
                if not data:
                    result[p.stem] = {}
            else:
                result[p.stem] = {}
    return result


def save_fmt_config(fmt_name: str, data: dict) -> None:
    """Save app_data/config/formats/{fmt_name}.yaml."""
    (CONFIG_DIR / "formats").mkdir(parents=True, exist_ok=True)
    path = CONFIG_DIR / "formats" / f"{fmt_name}.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def load_fmt_config(fmt_name: str) -> dict:
    """Load app_data/config/formats/{fmt_name}.yaml."""
    path = CONFIG_DIR / "formats" / f"{fmt_name}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})


def get_novel_group(novel_id: str, groups: dict | None = None) -> str | None:
    """Return group name for novel_id, or None if not found."""
    from shared.user_data import get_novel_group as _db_get
    return _db_get(novel_id)


def ensure_novel_in_group(novel_id: str) -> None:
    """Add novel to 'default' group if not already in any group."""
    if get_novel_group(novel_id) is None:
        add_novel_to_group(novel_id, "default")


def add_novel_to_group(novel_id: str, group: str) -> bool:
    """Add novel_id to group in user_data.db (auto-dedup).

    If the novel is already in another group, remove it first.
    Returns True if newly added, False if already in target group.
    """
    from shared.user_data import add_novel_to_group as _db_add
    return _db_add(novel_id, group)


def build_options(source_name: str, mode: str) -> Options:
    """按书源名 + mode 组 Options。

    薄封装 `shared.config.build_options`：字段来自三层合并后的书源配置，
    storage 恒取共享 `get_database_url()`（单一来源，不再按站点/模式分）。
    """
    from shared.config import build_options as _build_options
    return _build_options(source_name, mode)


