"""配置服务 — YAML 读写、默认值、深合并、平台/格式配置加载。"""
from pathlib import Path
import yaml

_config_dir = Path(__file__).parent.parent.parent / "app_data" / "config"


# ═══════════════════════════════════════════════════════════════════
# 默认值
# ═══════════════════════════════════════════════════════════════════

ENGINE_DEFAULTS = {
    "browser": {
        "headless": False,
        "browser_type": "chromium",
        "user_data_dir": "app_data/browser/Chromium/User Data",
        "viewport": {"width": 1280, "height": 720},
        "delay": [3.0, 5.0],
        "timeout": 30.0,
        "retry_times": 3,
        "backoff_factor": 2.0,
    },
    "requests": {
        "headers": {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        "cookies": {},
        "proxies": {},
        "delay": [3.0, 5.0],
        "timeout": 30.0,
        "retry_times": 3,
        "backoff_factor": 2.0,
    },
    "api": {
        "delay": [3.0, 5.0],
        "timeout": 30.0,
        "retry_times": 3,
        "backoff_factor": 2.0,
    },
}

GLOBAL_DEFAULTS = {
    "name": "Novel下载器",
    "mode": "browser",
    "max_workers": 3,
    "log_level": "DEBUG",
    "notify": {
        "on_complete": True,
        "on_incomplete": True,
        "sound": "bell",
    },
}

FMT_DEFAULTS = {
    "txt": {"enabled": True, "encoding": "utf-8"},
    "epub": {
        "enabled": True,
        "compression": "deflate",
        "compresslevel": 9,
        "optimize_images": True,
        "jpeg_quality": 85,
        "max_image_width": 0,
        "include_toc": True,
    },
    "img": {"enabled": True, "output_format": "original"},
}


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════

def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)


def load_config() -> dict:
    return load_yaml(_config_dir / "config.yaml")


# ═══════════════════════════════════════════════════════════════════
# 平台配置
# ═══════════════════════════════════════════════════════════════════

def load_platform_configs() -> dict[str, dict]:
    """读取所有 sites/{platform}.yaml，返回 {platform: {browser, requests, api}}。"""
    result: dict[str, dict] = {}
    sites_dir = _config_dir / "sites"
    if not sites_dir.is_dir():
        return result
    for p in sites_dir.glob("*.yaml"):
        platform = p.stem
        raw = load_yaml(p)
        entry: dict = {}
        for mode in ("browser", "requests", "api"):
            entry[mode] = deep_merge(ENGINE_DEFAULTS[mode], raw.get(mode, {}))
        api_section = raw.get("api", {}) if isinstance(raw.get("api"), dict) else {}
        entry["api_providers"] = [k for k, v in api_section.items() if isinstance(v, dict)]
        result[platform] = entry
    return result


def load_platform_raw(platform: str) -> dict:
    """读取单个平台的原始 YAML 配置（用于合并写入）。"""
    return load_yaml(_config_dir / "sites" / f"{platform}.yaml")


def load_site_config(platform: str) -> dict:
    """加载 app_data/config/sites/{platform}.yaml"""
    return load_platform_raw(platform)


def find_provider_options(provider: str) -> dict | None:
    """在所有站点配置中查找指定 API provider 的选项（返回第一个启用的）。"""
    sites_dir = _config_dir / "sites"
    if not sites_dir.is_dir():
        return None
    for p in sites_dir.glob("*.yaml"):
        site = load_yaml(p)
        api = site.get("api", {})
        if isinstance(api, dict) and provider in api:
            prov_cfg = api[provider]
            if isinstance(prov_cfg, dict) and prov_cfg.get("enabled", True):
                return prov_cfg
    return None


# ═══════════════════════════════════════════════════════════════════
# 格式配置
# ═══════════════════════════════════════════════════════════════════

def load_format_configs() -> dict[str, dict]:
    """读取 formats/{fmt}.yaml，合并默认值。"""
    result: dict[str, dict] = {}
    for fmt_key, defaults in FMT_DEFAULTS.items():
        raw = load_yaml(_config_dir / "formats" / f"{fmt_key}.yaml")
        fmt_data = raw.get(fmt_key, {}) if isinstance(raw, dict) else {}
        result[fmt_key] = deep_merge(defaults, fmt_data)
    return result


def save_format_config(fmt_key: str, data: dict):
    """保存格式配置到 formats/{fmt}.yaml。"""
    save_yaml(_config_dir / "formats" / f"{fmt_key}.yaml", {fmt_key: data})
