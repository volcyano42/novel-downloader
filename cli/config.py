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

from shared.config import get_mode_variant_config

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


def mode_variants(site_cfg: dict, mode: str) -> list[str]:
    """返回 site 配置中某 mode 的 variant 名列表（仅 dict 值）。"""
    from shared.config import mode_variants as _mv
    return _mv(site_cfg, mode)


def resolve_variant(site_cfg: dict, mode: str, variant: str | None = None) -> str | None:
    """解析应使用的 variant 名（与 mode 无关的通用规则）。

    - variant 显式指定：校验存在，不存在抛 ValueError（列出可用项）
    - 未指定且数量 ≤ 1：返回唯一 variant（无则 None）
    - 未指定且数量 > 1：返回 None，由调用方决策（交互询问 / 非交互提示 --variant）
    """
    variants = mode_variants(site_cfg, mode)
    if variant is not None:
        if variant not in variants:
            raise ValueError(
                f"variant '{variant}' 不可用于 {mode} 模式，可用: {variants or '无'}")
        return variant
    if len(variants) == 1:
        return variants[0]
    return None


def build_options(cfg: dict, site_cfg: dict, variant: str | None = None) -> Options:
    """Build Options from config dict — mode-specific branching like the original.

    variant: 显式指定 browser/requests/api 的 variant 名；None 时保持原行为
    （browser/requests 优先 "default"，api 取第一个启用 provider）。
    """
    options = Options()
    mode = cfg.get("mode") or site_cfg.get("mode", "browser")
    options.set_mode(mode)

    if mode == "browser":
        browser_cfg = get_mode_variant_config(site_cfg, "browser", variant)
        user_data_dir = browser_cfg.get("user_data_dir", "")
        if user_data_dir:
            ud_path = Path(user_data_dir)
            if not ud_path.is_absolute():
                ud_path = Path(__file__).parent.parent / ud_path
        else:
            ud_path = None
        options.set_browser_options(
            headless=browser_cfg.get("headless", False),
            user_data_dir=str(ud_path) if ud_path else None,
            timeout=browser_cfg.get("timeout", 30),
            retry_times=browser_cfg.get("retry_times", 3),
            backoff_factor=browser_cfg.get("backoff_factor", 2),
            delay=tuple(browser_cfg.get("delay", [3, 5])),
            viewport=browser_cfg.get("viewport"),
            auto_reconnect=browser_cfg.get("auto_reconnect", False),
        )

    elif mode == "api":
        api_section = site_cfg.get("api", {})
        if variant is not None:
            provider = api_section.get(variant)
            if not isinstance(provider, dict):
                raise ValueError(
                    f"API variant '{variant}' 不存在，可用: {list(api_section.keys())}")
            providers = [(variant, provider)]
        else:
            providers = [(n, p) for n, p in api_section.items() if isinstance(p, dict)]
        for name, provider in providers:
            if provider.get("enabled", True):
                env_key_name = f"{name.upper()}_API_KEY"
                api_key = os.environ.get(env_key_name) or provider.get("key", "")
                options.set_api_options(
                    name=name,
                    key=api_key,
                    timeout=provider.get("timeout", 30),
                    retry_times=provider.get("retry_times", 3),
                    backoff_factor=provider.get("backoff_factor", 2),
                    delay=tuple(provider.get("delay", [3, 5])),
                    params=provider.get("params", {}),
                )
                break

    elif mode == "requests":
        req_cfg = get_mode_variant_config(site_cfg, "requests", variant)
        cookies_val = req_cfg.get("cookies")
        if isinstance(cookies_val, str) and cookies_val:
            cookies_dict = {}
            for item in cookies_val.split(";"):
                item = item.strip()
                if "=" in item:
                    k, v = item.split("=", 1)
                    cookies_dict[k.strip()] = v.strip()
            cookies_val = cookies_dict
        elif not isinstance(cookies_val, dict):
            cookies_val = None

        options.set_requests_options(
            headers=req_cfg.get("headers"),
            cookies=cookies_val,
            proxies=req_cfg.get("proxies"),
            timeout=req_cfg.get("timeout", 30),
            retry_times=req_cfg.get("retry_times", 3),
            backoff_factor=req_cfg.get("backoff_factor", 2),
            delay=tuple(req_cfg.get("delay", [3, 5])),
        )

    # Storage
    from shared.config import get_database_url
    storage_cfg = cfg.get("storage", {})
    database_url = storage_cfg.get("database_url", "") or get_database_url()
    options.set_storage_options(backend="sqlite", database_url=database_url)

    return options
