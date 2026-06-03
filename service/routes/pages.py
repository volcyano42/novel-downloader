"""页面路由（GET 渲染）。"""
from __future__ import annotations

import yaml
from fastapi import APIRouter, Request

from .. import render, state
from ..config import CONFIG_DIR
from ..core import get_stored_novels

router = APIRouter()


@router.get("/")
async def index_page(request: Request):
    novels = get_stored_novels(state.storage)
    plat_label = state.PLATFORM_LABELS.get(state.platform, state.platform)

    fmt_dir = CONFIG_DIR / "formats"
    available_formats = []
    if fmt_dir.exists():
        for f in fmt_dir.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            for name, fc in data.items():
                if fc.get("enabled", True):
                    available_formats.append(name)

    return render("index.html",
        request=request,
        platform_label=plat_label,
        platform=state.platform,
        platforms=state.PLATFORM_LABELS,
        mode=state.mode,
        group=state.group,
        novel_count=len(novels),
        available_formats=available_formats,
    )


@router.get("/settings")
async def settings_page(request: Request):
    max_workers = state.cfg.get("download", {}).get("max_workers", 3)

    return render("settings.html",
        request=request,
        mode=state.mode,
        group=state.group,
        platform=state.platform,
        platforms=state.PLATFORM_LABELS,
        platform_labels=state.PLATFORM_LABELS,
        max_workers=max_workers,
        flash=None,
    )


@router.get("/settings/site/{site_platform}")
async def site_config_page(request: Request, site_platform: str):
    site_path = CONFIG_DIR / "sites" / f"{site_platform}.yaml"
    sc = yaml.safe_load(site_path.read_text(encoding="utf-8")) if site_path.exists() else {}
    bc = sc.get("browser", {})
    ac = sc.get("api", {}).get("oiapi", {})
    rc = sc.get("requests", {})
    plat_label = state.PLATFORM_LABELS.get(site_platform, site_platform)

    return render("site_config.html",
        request=request,
        site_platform=site_platform,
        plat_label=plat_label,
        bc=bc,
        ac=ac,
        rc=rc,
        flash=None,
    )
