"""Config 路由 — 拆分 config / groups / sites / formats 四个子资源。"""

from fastapi import APIRouter, HTTPException

import shared.config as config_service

router = APIRouter(prefix="/api/v2/config", tags=["config"])

_cfg_dir = config_service.CONFIG_DIR

# ── config.yaml ────────────────────────────────────

@router.get("")
async def get_config():
    raw = config_service.load_config()
    dl = raw.get("download", {}) or {}
    return {
        "mode": raw.get("mode", config_service.GLOBAL_DEFAULTS["mode"]),
        "max_workers": dl.get("max_workers", config_service.GLOBAL_DEFAULTS["max_workers"]),
        "notify": config_service.deep_merge(
            config_service.GLOBAL_DEFAULTS["notify"], dl.get("notify", {}),
        ),
    }


@router.put("")
async def save_config(body: dict):
    raw = config_service.load_config()
    changed = False
    if "mode" in body and body["mode"] != raw.get("mode"):
        raw["mode"] = body["mode"]
        changed = True
    dl = raw.setdefault("download", {})
    if "max_workers" in body:
        dl["max_workers"] = body["max_workers"]
        changed = True
    if "notify" in body and isinstance(body["notify"], dict):
        merged = config_service.deep_merge(dl.get("notify", {}), body["notify"])
        defaults = config_service.GLOBAL_DEFAULTS["notify"]
        # 清理与默认值相同的字段，避免前端原样回传时把默认值实体化写入 config.yaml
        dl["notify"] = {k: v for k, v in merged.items() if k not in defaults or v != defaults[k]}
        changed = True
    if changed:
        config_service.save_yaml(_cfg_dir / "config.yaml", raw)
    return {"status": "ok"}


# ── groups（DB）──────────────────────────────────────

@router.get("/groups")
async def get_groups():
    from shared.user_data import load_groups
    return load_groups()


@router.put("/groups")
async def save_groups(body: dict):
    from shared.user_data import save_groups
    save_groups(body)
    return {"status": "ok"}


# ── favorites（DB）────────────────────────────────────

@router.get("/favorites")
async def get_favorites():
    from shared.user_data import load_favorites
    return {"favorites": load_favorites()}


@router.post("/favorites/{novel_id}")
async def add_favorite(novel_id: str):
    from shared.user_data import add_favorite
    ok = add_favorite(novel_id)
    return {"ok": ok, "favorited": ok}


@router.delete("/favorites/{novel_id}")
async def remove_favorite(novel_id: str):
    from shared.user_data import remove_favorite
    ok = remove_favorite(novel_id)
    return {"ok": ok, "removed": ok}


# ── sites/{website}.yaml ────────────────────────────

@router.get("/sites/{website}")
async def get_site(website: str):
    raw = config_service.load_yaml(_cfg_dir / "sites" / f"{website}.yaml")
    entry: dict = {}
    for mode in ("browser", "requests"):
        entry[mode] = {
            v: config_service.deep_merge(
                config_service.ENGINE_DEFAULTS[mode],
                config_service.get_mode_variant_config(raw, mode, v),
            )
            for v in config_service.mode_variants(raw, mode)
        }
    # api 是 variant 容器，不是模式配置
    api_section = raw.get("api", {}) if isinstance(raw.get("api"), dict) else {}
    entry["api"] = {k: v for k, v in api_section.items() if isinstance(v, dict)}
    entry["api_variants"] = list(entry["api"].keys())
    return entry


@router.put("/sites/{website}")
async def save_site(website: str, body: dict):
    existing = config_service.load_yaml(_cfg_dir / "sites" / f"{website}.yaml")
    for mode in ("browser", "requests"):
        if mode in body and isinstance(body[mode], dict):
            existing_mode = existing.get(mode, {}) if isinstance(existing.get(mode), dict) else {}
            for v, cfg in body[mode].items():
                if isinstance(cfg, dict):
                    existing_mode[v] = config_service.deep_merge(
                        existing_mode.get(v, {}), cfg,
                    )
            existing[mode] = existing_mode
    # api mode 只保留 variant 子 dict，过滤标量字段
    if "api" in body and isinstance(body["api"], dict):
        api_existing = existing.get("api", {}) if isinstance(existing.get("api"), dict) else {}
        for k, v in body["api"].items():
            if isinstance(v, dict):
                api_existing[k] = config_service.deep_merge(api_existing.get(k, {}), v)
        existing["api"] = {k: v for k, v in api_existing.items() if isinstance(v, dict)}
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
