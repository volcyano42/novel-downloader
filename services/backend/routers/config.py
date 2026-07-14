"""Config 路由 — 拆分 config / groups / sites / formats 四个子资源。"""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from services.backend.services import config_service

router = APIRouter(prefix="/api/v2/config", tags=["config"])

_cfg_dir = config_service._config_dir  # noqa: SLF001

# ── config.yaml ────────────────────────────────────

@router.get("")
async def get_config():
    raw = config_service.load_config()
    log = raw.get("log", {}) or {}
    dl = raw.get("download", {}) or {}
    return {
        "name": raw.get("name", config_service.GLOBAL_DEFAULTS["name"]),
        "mode": raw.get("mode", config_service.GLOBAL_DEFAULTS["mode"]),
        "max_workers": dl.get("max_workers", config_service.GLOBAL_DEFAULTS["max_workers"]),
        "log_level": log.get("level", config_service.GLOBAL_DEFAULTS["log_level"]),
        "notify": config_service.deep_merge(
            config_service.GLOBAL_DEFAULTS["notify"], dl.get("notify", {}),
        ),
    }


@router.put("")
async def save_config(body: dict):
    raw = config_service.load_config()
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
        config_service.save_yaml(_cfg_dir / "config.yaml", raw)
    return {"status": "ok"}


# ── groups.yaml ─────────────────────────────────────

@router.get("/groups")
async def get_groups():
    return config_service.load_yaml(_cfg_dir / "groups.yaml")


@router.put("/groups")
async def save_groups(body: dict):
    config_service.save_yaml(_cfg_dir / "groups.yaml", body)
    return {"status": "ok"}


# ── sites/{website}.yaml ────────────────────────────

@router.get("/sites/{website}")
async def get_site(website: str):
    raw = config_service.load_yaml(_cfg_dir / "sites" / f"{website}.yaml")
    entry: dict = {}
    for mode in ("browser", "requests", "api"):
        entry[mode] = config_service.deep_merge(
            config_service.ENGINE_DEFAULTS[mode], raw.get(mode, {}),
        )
    api_section = raw.get("api", {}) if isinstance(raw.get("api"), dict) else {}
    entry["api_providers"] = [k for k, v in api_section.items() if isinstance(v, dict)]
    return entry


@router.put("/sites/{website}")
async def save_site(website: str, body: dict):
    existing = config_service.load_yaml(_cfg_dir / "sites" / f"{website}.yaml")
    for mode in ("browser", "requests", "api"):
        if mode in body and isinstance(body[mode], dict):
            existing[mode] = config_service.deep_merge(
                existing.get(mode, {}), body[mode],
            )
    config_service.save_yaml(_cfg_dir / "sites" / f"{website}.yaml", existing)
    return {"status": "ok"}


# ── formats/{format}.yaml ───────────────────────────

@router.get("/formats/{format}")
async def get_format(format: str):
    if format not in config_service.FMT_DEFAULTS:
        raise HTTPException(404, f"Unknown format: {format}")
    raw = config_service.load_yaml(_cfg_dir / "formats" / f"{format}.yaml")
    fmt_data = raw.get(format, {}) if isinstance(raw, dict) else {}
    return config_service.deep_merge(config_service.FMT_DEFAULTS[format], fmt_data)


@router.put("/formats/{format}")
async def save_format(format: str, body: dict):
    if format not in config_service.FMT_DEFAULTS:
        raise HTTPException(404, f"Unknown format: {format}")
    config_service.save_yaml(
        _cfg_dir / "formats" / f"{format}.yaml", {format: body},
    )
    return {"status": "ok"}
