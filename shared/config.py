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

def _user_site_cfg(source_name: str) -> dict:
    """读取用户层 sites/{source_name}.yaml（原始 dict，不做 app_data 路径解析）。"""
    return load_yaml(CONFIG_DIR / "sites" / f"{source_name}.yaml")


def merged_source_config(source_name: str) -> dict[str, dict]:
    """三层合并某书源的逐能力配置。

    返回 `{capability: 该能力段三层合并后的完整字段}`；未知书源返回 `{}`。
    三层：ENGINE_DEFAULTS[mode]（系统默认）→ `source.json.default_config[cap]`（书源出厂，
    已含 `common` 合并）→ `sites/{source_name}.yaml[cap]`（用户层）。
    用户层不决定 mode：合并前从用户层段剔除 `mode` 键，mode 恒取书源声明。
    """
    from novelbase.source import capabilities, get_manifest
    caps = capabilities(source_name)
    if not caps:
        return {}
    manifest = get_manifest(source_name)
    user = _user_site_cfg(source_name)
    out: dict[str, dict] = {}
    for cap, mode in caps.items():
        base = deep_merge(ENGINE_DEFAULTS.get(mode, {}), manifest["default_config"][cap])
        user_cap = user.get(cap) if isinstance(user.get(cap), dict) else {}
        user_cap = {k: v for k, v in user_cap.items() if k != "mode"}  # mode 恒取书源声明
        out[cap] = deep_merge(base, user_cap)
    return out


def is_source_enabled(source_name: str) -> bool:
    """书源是否启用：用户层顶层 `enabled` 覆盖 `source.json` 的出厂值。"""
    from novelbase.source import get_manifest
    user = _user_site_cfg(source_name)
    if isinstance(user.get("enabled"), bool):
        return user["enabled"]
    return bool(get_manifest(source_name).get("enabled", False))


def enabled_source_names() -> list[str]:
    """排序后的启用书源 source_name 列表（「启用集」的唯一入口）。"""
    from novelbase.source import list_sources
    return sorted(n for n in list_sources() if is_source_enabled(n))

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

# ── build_options（按 source_name + mode 从三层合并配置组 Options）──
def build_options(source_name: str, mode: str) -> Options:
    """按书源名 + mode 组 Options，字段取自 `merged_source_config(source_name)` 的对应能力段。

    能力段由 mode 反查（`capabilities(source_name)` 里 mode 匹配的能力段；一个书源的各
    能力段通常同 mode）。未知书源 / 无匹配段时退回 `ENGINE_DEFAULTS[mode]`。
    """
    from novelbase.core.options import Options
    from novelbase.source import capabilities

    merged = merged_source_config(source_name)
    caps = capabilities(source_name)
    cfg: dict = {}
    for cap, cap_mode in caps.items():
        if cap_mode == mode:
            cfg = merged.get(cap, {})
            break
    if not cfg:
        cfg = dict(ENGINE_DEFAULTS.get(mode, {}))

    options = Options().set_mode(mode)
    if mode == "browser":
        user_data_dir = cfg.get("user_data_dir", "")
        if user_data_dir:
            ud_path = Path(user_data_dir)
            if not ud_path.is_absolute():
                ud_path = Path(__file__).parent.parent / ud_path
        else:
            ud_path = None
        options.set_browser_options(
            headless=cfg.get("headless", False),
            user_data_dir=str(ud_path) if ud_path else None,
            timeout=cfg.get("timeout", 30),
            retry_times=cfg.get("retry_times", 3),
            backoff_factor=cfg.get("backoff_factor", 2),
            delay=tuple(cfg.get("delay", [3, 5])),
            viewport=cfg.get("viewport"),
            auto_reconnect=cfg.get("auto_reconnect", False),
        )
    elif mode == "api":
        options.set_api_options(
            key=cfg.get("key", ""),
            timeout=cfg.get("timeout", 30),
            retry_times=cfg.get("retry_times", 3),
            backoff_factor=cfg.get("backoff_factor", 2),
            delay=tuple(cfg.get("delay", [3, 5])),
            params=cfg.get("params", {}),
        )
    elif mode == "requests":
        cookies_val = cfg.get("cookies")
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
            headers=cfg.get("headers"),
            cookies=cookies_val,
            proxies=cfg.get("proxies"),
            timeout=cfg.get("timeout", 30),
            retry_times=cfg.get("retry_times", 3),
            backoff_factor=cfg.get("backoff_factor", 2),
            delay=tuple(cfg.get("delay", [3, 5])),
        )

    options.set_storage_options(backend="sqlite", database_url=get_database_url())
    return options
