"""Config 路由 — GET/PUT，委托 config_service 读写 + engine_manager 热更新。"""
from pathlib import Path

from fastapi import APIRouter
from services.backend.services import config_service
from services.backend.services.engine_manager import reload_engine_options

router = APIRouter(prefix="/config", tags=["config"])

_config_dir = config_service._config_dir  # noqa: SLF001


@router.get("")
async def get_config():
    raw = config_service.load_config()
    log = raw.get("log", {}) or {}
    dl = raw.get("download", {}) or {}

    platforms = config_service.load_platform_configs()
    formats = config_service.load_format_configs()

    api_providers: dict[str, list[str]] = {}
    for plat, cfg in platforms.items():
        if cfg.get("api_providers"):
            api_providers[plat] = cfg["api_providers"]

    return {
        "name": raw.get("name", config_service.GLOBAL_DEFAULTS["name"]),
        "mode": raw.get("mode", config_service.GLOBAL_DEFAULTS["mode"]),
        "max_workers": dl.get("max_workers", config_service.GLOBAL_DEFAULTS["max_workers"]),
        "log_level": log.get("level", config_service.GLOBAL_DEFAULTS["log_level"]),
        "notify": config_service.deep_merge(
            config_service.GLOBAL_DEFAULTS["notify"], dl.get("notify", {})),
        "platforms": platforms,
        "txt": formats.get("txt", config_service.FMT_DEFAULTS["txt"]),
        "epub": formats.get("epub", config_service.FMT_DEFAULTS["epub"]),
        "img": formats.get("img", config_service.FMT_DEFAULTS["img"]),
        "browser": platforms.get("fanqie", {}).get("browser",
                                                   config_service.ENGINE_DEFAULTS["browser"]),
        "requests": platforms.get("fanqie", {}).get("requests",
                                                    config_service.ENGINE_DEFAULTS["requests"]),
        "api": platforms.get("fanqie", {}).get("api",
                                               config_service.ENGINE_DEFAULTS["api"]),
        "api_providers": api_providers,
        "groups": config_service.load_yaml(_config_dir / "groups.yaml"),
    }


@router.put("")
async def save_config(body: dict):
    raw = config_service.load_config()

    # ── 平台引擎配置 → sites/{platform}.yaml ──
    platforms_body = body.get("platforms")
    changed_modes: set[str] = set()
    if isinstance(platforms_body, dict):
        for platform, plat_data in platforms_body.items():
            if not isinstance(plat_data, dict):
                continue
            site_raw = config_service.load_platform_raw(platform)
            for mode in ("browser", "requests", "api"):
                if mode in plat_data and isinstance(plat_data[mode], dict):
                    site_raw[mode] = config_service.deep_merge(
                        site_raw.get(mode, {}), plat_data[mode])
                    changed_modes.add(mode)
            config_service.save_yaml(_config_dir / "sites" / f"{platform}.yaml", site_raw)

    # ── 全局标量 → config.yaml ──
    changed = False
    for key in ("name", "mode"):
        if key in body and body[key] != raw.get(key):
            raw[key] = body[key]
            changed = True

    dl = raw.setdefault("download", {})
    if "max_workers" in body:
        dl["max_workers"] = body["max_workers"]
        changed = True
    if "notify" in body and isinstance(body["notify"], dict):
        dl["notify"] = config_service.deep_merge(dl.get("notify", {}), body["notify"])
        changed = True

    if "log_level" in body:
        raw.setdefault("log", {})["level"] = body["log_level"]
        changed = True

    if changed:
        config_service.save_yaml(_config_dir / "config.yaml", raw)

    # ── 格式配置 → formats/{fmt}.yaml ──
    for fmt_key in ("txt", "epub", "img"):
        if fmt_key in body and isinstance(body[fmt_key], dict):
            existing = config_service.load_yaml(
                _config_dir / "formats" / f"{fmt_key}.yaml")
            existing_fmt = existing.get(fmt_key, {}) if isinstance(existing, dict) else {}
            merged = config_service.deep_merge(existing_fmt, body[fmt_key])
            config_service.save_format_config(fmt_key, merged)

    # ── 热更新运行中引擎 ──
    for mode in changed_modes:
        reload_engine_options(mode)

    return {"status": "ok"}
