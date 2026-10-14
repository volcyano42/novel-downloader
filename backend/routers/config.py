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

def _user_sections(source_name: str) -> dict[str, dict]:
    """用户层 yaml 里的各能力段（排除 `common` 与顶层元信息键）。"""
    user = config_service.load_yaml(config_service.CONFIG_DIR / "sites" / f"{source_name}.yaml")
    return {k: v for k, v in user.items() if isinstance(v, dict) and k != "common"}


def _converge_candidates(source_name: str) -> tuple[list[dict], list[dict]]:
    """可收敛到 `common` 的键与需保留的键。

    条件（spec §4）：该键出现在**书源声明的全部能力**段里，且各段取值完全相同 ——
    只有这样才能保证搬到 common 后**不改变任何能力的生效值**（若只出现在部分段，
    其余段会从「继承出厂」变成「继承 common」，等于悄悄改了它们）。
    """
    sections = _user_sections(source_name)
    caps = list(capabilities(source_name))
    candidates: list[dict] = []
    kept: list[dict] = []
    if not caps:
        return candidates, kept
    for key in sorted({k for section in sections.values() for k in section}):
        if any(key not in sections.get(cap, {}) for cap in caps):
            kept.append({"key": key})
            continue
        first = sections[caps[0]][key]
        if all(sections[cap][key] == first for cap in caps):
            candidates.append({"key": key, "value": first})
        else:
            kept.append({"key": key})
    return candidates, kept


@router.get("/sources/{source_name}")
async def get_source_config(source_name: str):
    """三层合并后的书源配置 + 能力映射。

    形状：`{source_name, capabilities: {cap: 有效mode}, declared_capabilities: {cap: 声明mode},
    config: {cap: {…完整合并字段（含 mode）…}}}`。
    `capabilities` 为**有效 mode**（用户层 `{cap}.mode` 覆盖书源声明），
    `declared_capabilities` 为书源声明值（前端「恢复默认」用）。
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
        # 各能力段在用户层里**实际出现**的键（含 mode），供前端区分「继承常规」/「已覆盖」
        "user_overrides": {cap: sorted(section) for cap, section in _user_sections(source_name).items()},
        # 可一键收敛到 common 的键（各能力段都有且取值相同）
        "converge_candidates": _converge_candidates(source_name)[0],
    }


@router.put("/sources/{source_name}")
async def save_source_config(source_name: str, body: dict):
    """只写用户层 `sites/{source_name}.yaml`：顶层元信息 + 逐能力段 `deep_merge`。

    不把三层合并后的全量写回（否则用户层被灌满出厂/系统默认值）。
    能力段的 `mode` 键特判：传入字符串 → 覆盖；传入 `null` → 删除该键（恢复书源声明）。
    """
    require_known_source(source_name)
    path = config_service.CONFIG_DIR / "sites" / f"{source_name}.yaml"
    existing = config_service.load_yaml(path)
    existing.pop("enabled", None)   # enabled 已废弃：顺手清理旧用户层残留键
    # 顶层 concurrency：正整数写入用户层，非法值忽略（不写坏 yaml）
    if "concurrency" in body and config_service._is_positive_int(body["concurrency"]):
        existing["concurrency"] = body["concurrency"]
    # 顶层元信息：字符串写入用户层（strip 后非空），空串 = 删除该键（回落出厂 / source_name）
    for key in ("source_group", "source_alias"):
        if key in body:
            raw = body[key]
            text = raw.strip() if isinstance(raw, str) else ""
            if text:
                existing[key] = text
            else:
                existing.pop(key, None)
    # 顶层 common：跨能力共享字段。写入某键时**同时从各能力段删除同名键** ——
    # 否则用户层能力段的旧值优先级更高，用户会看到「改了常规但不生效」。
    common_body = body.get("common")
    if isinstance(common_body, dict):
        common = existing.get("common")
        common = dict(common) if isinstance(common, dict) else {}
        for key, value in common_body.items():
            if value is None:
                common.pop(key, None)              # 删除该共享键
                continue
            common[key] = value
            for section_name, section in existing.items():
                if section_name in ("common", "concurrency", "source_group", "source_alias", "enabled"):
                    continue
                if isinstance(section, dict):
                    section.pop(key, None)
        if common:
            existing["common"] = common
        else:
            existing.pop("common", None)
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


@router.post("/sources/{source_name}/converge")
async def converge_source_config(source_name: str):
    """把各能力段取值相同、且覆盖全部声明能力的共享键收敛到 `common`。

    收敛不改变任何能力的生效值（这正是 `_converge_candidates` 的入选条件）；
    各段不一致或只出现在部分能力段的键原样保留并在 `kept` 里回报。
    """
    require_known_source(source_name)
    path = config_service.CONFIG_DIR / "sites" / f"{source_name}.yaml"
    existing = config_service.load_yaml(path)
    candidates, kept = _converge_candidates(source_name)
    if candidates:
        common = existing.get("common")
        common = dict(common) if isinstance(common, dict) else {}
        for item in candidates:
            common[item["key"]] = item["value"]
        for item in candidates:
            for cap in list(_user_sections(source_name)):
                section = existing.get(cap)
                if not isinstance(section, dict):
                    continue
                section.pop(item["key"], None)
                if section:
                    existing[cap] = section
                else:
                    existing.pop(cap, None)
        existing["common"] = common
        config_service.save_yaml(path, existing)
    return {"status": "ok", "converged": candidates, "kept": kept}


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
