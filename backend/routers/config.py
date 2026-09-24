"""Config 路由 — 拆分 config / groups / favorites / sources / formats 子资源。"""

from fastapi import APIRouter, HTTPException

import shared.config as config_service
from novelbase.source import capabilities

router = APIRouter(prefix="/api/v2/config", tags=["config"])

_cfg_dir = config_service.CONFIG_DIR

# ── config.yaml ────────────────────────────────────

@router.get("")
async def get_config():
    raw = config_service.load_config()
    dl = raw.get("download", {}) or {}
    return {
        "max_workers": dl.get("max_workers", config_service.GLOBAL_DEFAULTS["max_workers"]),
        "notify": config_service.deep_merge(
            config_service.GLOBAL_DEFAULTS["notify"], dl.get("notify", {}),
        ),
    }


@router.put("")
async def save_config(body: dict):
    raw = config_service.load_config()
    changed = False
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


# ── sources/{source_name}.yaml（按书源）──────────────

@router.get("/sources/{source_name}")
async def get_source_config(source_name: str):
    """三层合并后的书源配置 + 启用状态 + 能力映射。

    形状：`{source_name, enabled, capabilities: {cap: mode}, config: {cap: {…完整合并字段…}}}`。
    `config[cap]` 含 mode（恒取书源声明），`enabled` 走用户层顶层 `enabled` → 出厂值。
    """
    return {
        "source_name": source_name,
        "enabled": config_service.is_source_enabled(source_name),
        "capabilities": capabilities(source_name),
        "config": config_service.merged_source_config(source_name),
    }


@router.put("/sources/{source_name}")
async def save_source_config(source_name: str, body: dict):
    """只写用户层 `sites/{source_name}.yaml`：顶层 `enabled` + 逐能力段 `deep_merge`。

    不把三层合并后的全量写回（否则用户层被灌满出厂/系统默认值）。
    """
    path = config_service.CONFIG_DIR / "sites" / f"{source_name}.yaml"
    existing = config_service.load_yaml(path)
    if isinstance(body.get("enabled"), bool):
        existing["enabled"] = body["enabled"]
    cfg_body = body.get("config")
    if isinstance(cfg_body, dict):
        for cap, partial in cfg_body.items():
            if isinstance(partial, dict):
                base = existing.get(cap)
                existing[cap] = config_service.deep_merge(
                    base if isinstance(base, dict) else {}, partial)
    config_service.save_yaml(path, existing)
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
