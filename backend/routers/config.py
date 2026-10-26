"""Config 路由 — 拆分 config / groups / favorites / sources / formats 子资源。"""

from fastapi import APIRouter, HTTPException

import shared.config as config_service
from novelbase.source import capabilities
from shared.config import effective_capabilities
from backend.services.source_guard import require_known_source

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
#
# 2026-10-25 起：一个书源只有**一个 mode 和一套参数**，不再按能力分化。
# 用户层 yaml 就是顶层一套字段（mode / timeout / headers / ...），
# 因此原先的 common 段、能力段覆盖、converge 收敛机制全部删除。

# 顶层元信息键：不是引擎字段（见 shared/config.py 的 _SOURCE_META_KEYS）
_META_KEYS = ("concurrency", "source_group", "source_alias", "mode")

@router.get("/sources/{source_name}")
async def get_source_config(source_name: str):
    """三层合并后的书源配置 + 能力映射。

    形状：`{source_name, capabilities, declared_capabilities, source_group, source_alias,
    concurrency, config}`。

    `capabilities` 为**有效 mode**（用户层顶层 `mode` 覆盖书源声明），值全相同；
    `declared_capabilities` 为书源声明值（前端「恢复默认」用）。
    `config` 仍是 `{capability: 完整字段}` 形状（四份内容相同），仅为让按能力取用的
    下游写法不必改动。
    """
    require_known_source(source_name)
    return {
        "source_name": source_name,
        "concurrency": config_service.source_concurrency(source_name),
        "capabilities": effective_capabilities(source_name),
        "declared_capabilities": capabilities(source_name),
        "source_group": config_service.source_group(source_name),
        "source_alias": config_service.source_alias(source_name),
        "config": config_service.merged_source_config(source_name),
    }


@router.put("/sources/{source_name}")
async def save_source_config(source_name: str, body: dict):
    """只写用户层 `sources/{source_name}.yaml` 的**顶层字段**。

    body 可含：`concurrency`、`source_group`、`source_alias`、`mode`、以及引擎字段
    （timeout / retry_times / delay / headers / key / …，随 mode 而变）。

    不把三层合并后的全量写回（否则用户层被灌满出厂/系统默认值）。
    `mode: null` → 删除覆盖，恢复书源声明；字段传 `null` → 删除该键。
    """
    require_known_source(source_name)
    path = config_service.CONFIG_DIR / "sources" / f"{source_name}.yaml"
    existing = config_service.load_yaml(path)
    if not isinstance(existing, dict):
        existing = {}
    existing.pop("enabled", None)   # enabled 已废弃：顺手清理旧用户层残留键

    if "concurrency" in body and config_service._is_positive_int(body["concurrency"]):
        existing["concurrency"] = body["concurrency"]

    # 顶层元信息：strip 后非空才写入，空串 = 删除（回落出厂 / source_name）
    for key in ("source_group", "source_alias"):
        if key in body:
            raw = body[key]
            text = raw.strip() if isinstance(raw, str) else ""
            if text:
                existing[key] = text
            else:
                existing.pop(key, None)

    # mode 特判：字符串 → 覆盖；null → 删除（恢复书源声明）
    if "mode" in body:
        mode = body["mode"]
        if mode is None:
            existing.pop("mode", None)
        elif mode in config_service.VALID_MODES:
            existing["mode"] = mode

    # 引擎字段直接落到顶层；null 表示删除该键
    for key, value in body.items():
        if key in _META_KEYS:
            continue
        if value is None:
            existing.pop(key, None)
        else:
            existing = config_service.deep_merge(existing, {key: value})

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
