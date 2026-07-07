"""Config 路由 — 全局参数存 config.yaml，引擎参数按平台存 sites/{platform}.yaml。"""
from pathlib import Path
import yaml
from fastapi import APIRouter

router = APIRouter(prefix="/config", tags=["config"])

_config_dir = Path(__file__).parent.parent.parent / "app_data" / "config"

# ═══════════════════════════════════════════════════════════════════
# 默认值
# ═══════════════════════════════════════════════════════════════════

_ENGINE_DEFAULTS = {
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

_GLOBAL_DEFAULTS = {
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

_FMT_DEFAULTS = {
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

def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, default_flow_style=False)


def load_config() -> dict:
    return _load_yaml(_config_dir / "config.yaml")


# ═══════════════════════════════════════════════════════════════════
# 平台配置读取
# ═══════════════════════════════════════════════════════════════════

def _load_platform_configs() -> dict[str, dict]:
    """读取所有 sites/{platform}.yaml，返回 {platform: {browser, requests, api}}。"""
    result: dict[str, dict] = {}
    sites_dir = _config_dir / "sites"
    if not sites_dir.is_dir():
        return result
    for p in sites_dir.glob("*.yaml"):
        platform = p.stem
        raw = _load_yaml(p)
        entry: dict = {}
        for mode in ("browser", "requests", "api"):
            entry[mode] = _deep_merge(_ENGINE_DEFAULTS[mode], raw.get(mode, {}))
        # API providers 列表
        api_section = raw.get("api", {}) if isinstance(raw.get("api"), dict) else {}
        entry["api_providers"] = [k for k, v in api_section.items() if isinstance(v, dict)]
        result[platform] = entry
    return result


def _load_platform_raw(platform: str) -> dict:
    """读取单个平台的原始 YAML 配置（用于合并写入）。"""
    return _load_yaml(_config_dir / "sites" / f"{platform}.yaml")


# ═══════════════════════════════════════════════════════════════════
# 格式配置读取
# ═══════════════════════════════════════════════════════════════════

def _load_format_configs() -> dict[str, dict]:
    """读取 formats/{fmt}.yaml，合并默认值。"""
    result: dict[str, dict] = {}
    for fmt_key, defaults in _FMT_DEFAULTS.items():
        raw = _load_yaml(_config_dir / "formats" / f"{fmt_key}.yaml")
        # formats yaml 是嵌套结构 {fmt_key: {...}}
        fmt_data = raw.get(fmt_key, {}) if isinstance(raw, dict) else {}
        result[fmt_key] = _deep_merge(defaults, fmt_data)
    return result


def _save_format_config(fmt_key: str, data: dict):
    """保存格式配置到 formats/{fmt}.yaml。"""
    _save_yaml(_config_dir / "formats" / f"{fmt_key}.yaml", {fmt_key: data})


# ═══════════════════════════════════════════════════════════════════
# GET — 返回全部配置
# ═══════════════════════════════════════════════════════════════════

@router.get("")
async def get_config():
    raw = load_config()
    log = raw.get("log", {}) or {}
    dl = raw.get("download", {}) or {}

    # 平台配置
    platforms = _load_platform_configs()

    # 格式配置
    formats = _load_format_configs()

    # api_providers (对旧版兼容)
    api_providers: dict[str, list[str]] = {}
    for plat, cfg in platforms.items():
        if cfg.get("api_providers"):
            api_providers[plat] = cfg["api_providers"]

    return {
        "name": raw.get("name", _GLOBAL_DEFAULTS["name"]),
        "mode": raw.get("mode", _GLOBAL_DEFAULTS["mode"]),
        "max_workers": dl.get("max_workers", _GLOBAL_DEFAULTS["max_workers"]),
        "log_level": log.get("level", _GLOBAL_DEFAULTS["log_level"]),
        "notify": _deep_merge(_GLOBAL_DEFAULTS["notify"], dl.get("notify", {})),
        # 平台引擎配置（新）
        "platforms": platforms,
        # 格式配置
        "txt": formats.get("txt", _FMT_DEFAULTS["txt"]),
        "epub": formats.get("epub", _FMT_DEFAULTS["epub"]),
        "img": formats.get("img", _FMT_DEFAULTS["img"]),
        # 兼容旧版：用第一个平台的配置填充顶层 engine 字段
        "browser": platforms.get("fanqie", {}).get("browser", _ENGINE_DEFAULTS["browser"]),
        "requests": platforms.get("fanqie", {}).get("requests", _ENGINE_DEFAULTS["requests"]),
        "api": platforms.get("fanqie", {}).get("api", _ENGINE_DEFAULTS["api"]),
        "api_providers": api_providers,
        "groups": _load_yaml(_config_dir / "groups.yaml"),
    }


# ═══════════════════════════════════════════════════════════════════
# PUT — 按 key 路径分流写入
# ═══════════════════════════════════════════════════════════════════

@router.put("")
async def save_config(body: dict):
    raw = load_config()

    # ── 平台引擎配置: platforms.{platform}.{mode}.{key} → sites/{platform}.yaml ──
    platforms_body = body.get("platforms")
    if isinstance(platforms_body, dict):
        for platform, plat_data in platforms_body.items():
            if not isinstance(plat_data, dict):
                continue
            site_raw = _load_platform_raw(platform)
            for mode in ("browser", "requests", "api"):
                if mode in plat_data and isinstance(plat_data[mode], dict):
                    site_raw[mode] = _deep_merge(site_raw.get(mode, {}), plat_data[mode])
            _save_yaml(_config_dir / "sites" / f"{platform}.yaml", site_raw)

    # ── 全局标量: mode / name → config.yaml ──
    changed = False
    for key in ("name", "mode"):
        if key in body and body[key] != raw.get(key):
            raw[key] = body[key]
            changed = True

    # ── download 块: max_workers / notify → config.yaml ──
    dl = raw.setdefault("download", {})
    if "max_workers" in body:
        dl["max_workers"] = body["max_workers"]
        changed = True
    if "notify" in body and isinstance(body["notify"], dict):
        dl["notify"] = _deep_merge(dl.get("notify", {}), body["notify"])
        changed = True

    # ── log_level → config.yaml ──
    if "log_level" in body:
        raw.setdefault("log", {})["level"] = body["log_level"]
        changed = True

    if changed:
        _save_yaml(_config_dir / "config.yaml", raw)

    # ── 格式配置: txt / epub / img → formats/{fmt}.yaml ──
    for fmt_key in ("txt", "epub", "img"):
        if fmt_key in body and isinstance(body[fmt_key], dict):
            existing = _load_yaml(_config_dir / "formats" / f"{fmt_key}.yaml")
            existing_fmt = existing.get(fmt_key, {}) if isinstance(existing, dict) else {}
            merged = _deep_merge(existing_fmt, body[fmt_key])
            _save_format_config(fmt_key, merged)

    return {"status": "ok"}
