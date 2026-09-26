"""Config 路由 — 拆分 config / groups / favorites / sources / formats 子资源。"""

from fastapi import APIRouter, HTTPException

import shared.config as config_service
from novelbase.source import capabilities
from shared.config import effective_capabilities, is_source_available, platform, supported_modes
from backend.services.source_guard import (require_available_source, require_known_source,
                                          require_supported_mode)

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


@router.get("/environment")
async def get_environment():
    """运行环境：`platform`（desktop/android）与本环境可用的引擎 mode。

    前端据此裁剪「书源 mode 下拉」的选项（Android 下不出现 Browser）；
    唯一真源是 `shared.config.supported_modes()`。
    """
    return {
        "platform": platform(),
        "supported_modes": list(supported_modes()),
    }


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

    形状：`{source_name, enabled, capabilities: {cap: 有效mode}, declared_capabilities: {cap: 声明mode},
    config: {cap: {…完整合并字段（含 mode）…}}}`。
    `capabilities` 为**有效 mode**（用户层 `{cap}.mode` 覆盖书源声明），
    `declared_capabilities` 为书源声明值（前端「恢复默认」用）。
    """
    require_known_source(source_name)
    return {
        "source_name": source_name,
        "enabled": config_service.is_source_enabled(source_name),
        "concurrency": config_service.source_concurrency(source_name),
        "capabilities": effective_capabilities(source_name),
        "declared_capabilities": capabilities(source_name),
        "available": is_source_available(source_name),
        "config": config_service.merged_source_config(source_name),
    }


@router.put("/sources/{source_name}")
async def save_source_config(source_name: str, body: dict):
    """只写用户层 `sites/{source_name}.yaml`：顶层 `enabled` + 逐能力段 `deep_merge`。

    不把三层合并后的全量写回（否则用户层被灌满出厂/系统默认值）。
    能力段的 `mode` 键特判：传入字符串 → 覆盖；传入 `null` → 删除该键（恢复书源声明）。
    """
    require_known_source(source_name)
    # 写入口的可用性校验（Android 上不得启用 / 覆盖成 browser）；校验先于落盘，
    # 任一 mode 不合法就整体拒绝，避免半写。
    if body.get("enabled") is True:
        require_available_source(source_name)
    cfg_body = body.get("config")
    if isinstance(cfg_body, dict):
        for cap, partial in cfg_body.items():
            if isinstance(partial, dict) and partial.get("mode") is not None:
                require_supported_mode(partial["mode"], source_name=source_name, capability=cap)
    path = config_service.CONFIG_DIR / "sites" / f"{source_name}.yaml"
    existing = config_service.load_yaml(path)
    if isinstance(body.get("enabled"), bool):
        existing["enabled"] = body["enabled"]
    # 顶层 concurrency 与 enabled 同级：正整数写入用户层，非法值忽略（不写坏 yaml）
    if "concurrency" in body and config_service._is_positive_int(body["concurrency"]):
        existing["concurrency"] = body["concurrency"]
    cfg_body = body.get("config")
    if isinstance(cfg_body, dict):
        for cap, partial in cfg_body.items():
            if not isinstance(partial, dict):
                continue
            section = existing.get(cap)
            section = dict(section) if isinstance(section, dict) else {}
            mode = partial.get("mode")
            if mode is None and "mode" in partial:
                section.pop("mode", None)        # 恢复默认：删掉覆盖
            section = config_service.deep_merge(
                section, {k: v for k, v in partial.items() if k != "mode"})
            if mode is not None:
                section["mode"] = mode
            if section:
                existing[cap] = section
            else:
                existing.pop(cap, None)
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
