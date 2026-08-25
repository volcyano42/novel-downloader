# shared/config.py
"""配置加载 — 单一数据源：默认值从 novelbase.core.options 派生。"""
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import MISSING, fields
from pathlib import Path

import yaml

from novelbase.core.options import BrowserOptions, RequestsOptions


# ── 路径 ──
def _get_app_data_dir() -> Path:
    env = os.environ.get("NLD_APP_DATA")
    if env:
        return Path(env).resolve()
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        app_data = exe_dir / "app_data"
        if not app_data.exists():
            meipass = Path(sys._MEIPASS)
            src = meipass / "app_data"
            if src.exists():
                try:
                    _copy_dir(src, app_data)
                except (OSError, PermissionError):
                    app_data.mkdir(parents=True, exist_ok=True)
            else:
                app_data.mkdir(parents=True, exist_ok=True)
        return app_data
    return Path(__file__).resolve().parent.parent / "app_data"

def _copy_dir(src: Path, dst: Path, _max_depth: int = 10) -> None:
    if _max_depth < 0:
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copy_dir(item, target, _max_depth - 1)
        elif not target.exists():
            shutil.copy2(item, target)

APP_DATA = _get_app_data_dir()
CONFIG_DIR = APP_DATA / "config"

# ── 默认值单一数据源：从 dataclass 字段默认值派生 ──
def _dataclass_defaults(cls) -> dict:
    result = {}
    for f in fields(cls):
        if f.default is not MISSING:
            result[f.name] = f.default
        elif f.default_factory is not MISSING:
            result[f.name] = f.default_factory()
    return result

ENGINE_DEFAULTS = {
    "browser": _dataclass_defaults(BrowserOptions),
    "requests": _dataclass_defaults(RequestsOptions),
    "api": {},
}

GLOBAL_DEFAULTS = {
    "mode": "browser",
    "max_workers": 3,
    "notify": {"on_complete": True, "on_incomplete": True, "sound": "bell"},
}

FMT_DEFAULTS = {
    "txt": {"enabled": True, "encoding": "utf-8"},
    "epub": {"enabled": True, "compression": "deflate", "compresslevel": 9,
             "optimize_images": True, "jpeg_quality": 85, "max_image_width": 0, "include_toc": True},
    "img": {"enabled": True, "output_format": "original"},
}

# ── 工具 ──
def deep_merge(base, override):
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def load_yaml(path):
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def save_yaml(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)

def _resolve_paths(value):
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

# ── config.yaml ──
def load_main_config():
    path = CONFIG_DIR / "config.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})

def load_config() -> dict:
    """别名，兼容 backend 路由的旧调用名。"""
    return load_main_config()

def save_main_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with (CONFIG_DIR / "config.yaml").open("w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)

# ── sites ──
def load_site_config(platform):
    path = CONFIG_DIR / "sites" / f"{platform}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})

def save_site_config(platform, site_cfg):
    (CONFIG_DIR / "sites").mkdir(parents=True, exist_ok=True)
    with (CONFIG_DIR / "sites" / f"{platform}.yaml").open("w", encoding="utf-8") as f:
        yaml.dump(site_cfg, f, allow_unicode=True, default_flow_style=False)

def load_platform_configs():
    result = {}
    sites_dir = CONFIG_DIR / "sites"
    if not sites_dir.is_dir():
        return result
    for p in sites_dir.glob("*.yaml"):
        platform = p.stem
        raw = load_yaml(p)
        entry = {}
        for mode in ("browser", "requests"):
            entry[mode] = {
                v: deep_merge(ENGINE_DEFAULTS[mode], get_mode_variant_config(raw, mode, v))
                for v in mode_variants(raw, mode)
            }
        api_section = raw.get("api", {}) if isinstance(raw.get("api"), dict) else {}
        entry["api"] = {k: v for k, v in api_section.items() if isinstance(v, dict)}
        entry["api_variants"] = list(entry["api"].keys())
        result[platform] = entry
    return result

def load_platform_raw(platform):
    return load_yaml(CONFIG_DIR / "sites" / f"{platform}.yaml")

def get_mode_variant_config(site_cfg, mode, variant=None) -> dict:
    """取 site 配置中某 mode 的 variant 配置。

    variant=None → 优先 "default"，无 "default" 取第一个 dict 值。
    非 dict 结构（扁平旧格式/标量）一律返回 {}（只支持新格式）。
    """
    mode_section = site_cfg.get(mode, {}) if isinstance(site_cfg, dict) else {}
    if not isinstance(mode_section, dict):
        return {}
    if variant is not None and variant in mode_section:
        cfg = mode_section[variant]
        return cfg if isinstance(cfg, dict) else {}
    if "default" in mode_section:
        cfg = mode_section["default"]
        return cfg if isinstance(cfg, dict) else {}
    for v, cfg in mode_section.items():
        if isinstance(cfg, dict):
            return cfg
    return {}


def load_mode_config(platform, mode, variant=None) -> dict:
    """从 sites/{platform}.yaml 加载某 mode 的 variant 配置（含 app_data 路径解析）。"""
    site = load_site_config(platform)
    return get_mode_variant_config(site, mode, variant)


def mode_variants(site_cfg, mode) -> list[str]:
    """返回某 mode 下的 variant 名列表（仅 dict 值）。"""
    mode_section = site_cfg.get(mode, {}) if isinstance(site_cfg, dict) else {}
    if not isinstance(mode_section, dict):
        return []
    return [k for k, v in mode_section.items() if isinstance(v, dict)]

def find_variant_options(variant):
    sites_dir = CONFIG_DIR / "sites"
    if not sites_dir.is_dir():
        return None
    for p in sites_dir.glob("*.yaml"):
        site = load_yaml(p)
        for mode in ("api", "browser", "requests"):
            cfg = get_mode_variant_config(site, mode, variant)
            if cfg:
                return cfg
    return None

# ── formats ──
def load_format_configs():
    result = {}
    for fmt_key, defaults in FMT_DEFAULTS.items():
        raw = load_yaml(CONFIG_DIR / "formats" / f"{fmt_key}.yaml")
        fmt_data = raw.get(fmt_key, {}) if isinstance(raw, dict) else {}
        result[fmt_key] = deep_merge(defaults, fmt_data)
    return result

def save_format_config(fmt_key, data):
    save_yaml(CONFIG_DIR / "formats" / f"{fmt_key}.yaml", {fmt_key: data})

def save_fmt_config(fmt_name, data):
    (CONFIG_DIR / "formats").mkdir(parents=True, exist_ok=True)
    save_yaml(CONFIG_DIR / "formats" / f"{fmt_name}.yaml", data)

def load_fmt_config(fmt_name):
    path = CONFIG_DIR / "formats" / f"{fmt_name}.yaml"
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return _resolve_paths(yaml.safe_load(f) or {})

# ── 数据库 URL ──
def get_database_url():
    # database_url 充当"目录定位器"：SQLiteStorage 取 parent 作为 base_dir，
    # 文件本身（.dir 占位）从不创建，真正的库是 base_dir 下每本小说的 <id>.db。
    return f"sqlite:///{APP_DATA / 'storage' / 'novels' / '.dir'}"

# ── build_options（从旧 cli_lib/config.py 迁移，改为 import shared.user_data）──
def build_options(cfg, site_cfg):
    from novelbase.core.options import Options
    options = Options()
    mode = cfg.get("mode") or site_cfg.get("mode", "browser")
    options.set_mode(mode)

    if mode == "browser":
        browser_cfg = get_mode_variant_config(site_cfg, "browser")
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
        )
    elif mode == "api":
        api_section = site_cfg.get("api", {})
        for name, provider in api_section.items():
            if isinstance(provider, dict) and provider.get("enabled", True):
                env_key_name = f"{name.upper()}_API_KEY"
                api_key = os.environ.get(env_key_name) or provider.get("key", "")
                options.set_api_options(
                    name=name, key=api_key,
                    timeout=provider.get("timeout", 30),
                    retry_times=provider.get("retry_times", 3),
                    backoff_factor=provider.get("backoff_factor", 2),
                    delay=tuple(provider.get("delay", [3, 5])),
                    params=provider.get("params", {}),
                )
                break
    elif mode == "requests":
        req_cfg = get_mode_variant_config(site_cfg, "requests")
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

    storage_cfg = cfg.get("storage", {})
    database_url = storage_cfg.get("database_url", "") or "sqlite:///app_data/storage/novels/.dir"
    options.set_storage_options(backend="sqlite", database_url=database_url)
    return options
