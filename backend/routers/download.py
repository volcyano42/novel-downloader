"""Download 路由 — 6 条，对接 search + NovelDownloader。"""
import hashlib
import json
from base64 import b64encode
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from backend.schemas import FetchMetaRequest, DownloadChapterRequest, SearchResultData, ChapterBrief
from backend.routers.config import load_config
from nldlder import NovelDownloader, Options, create_engine, get_fetchers, search

router = APIRouter(prefix="/api/v1/download", tags=["download"])

_engines: dict[str, tuple[object, str]] = {}

def _mode_fingerprint(mode_cfg: dict) -> str:
    """对模式配置做哈希，用于检测选项变更。"""
    return hashlib.md5(json.dumps(mode_cfg, sort_keys=True, default=str).encode()).hexdigest()

def _encode_cover(cover) -> dict | None:
    if not cover: return None
    if not cover.raw_data: return {"raw_data": None, "alt": cover.alt, "url": cover.url, "format": cover.image_format}

    fmt = cover.image_format
    if fmt in ("heic", "heif"):
        converted = cover.convert("jpeg", quality=90)
        if converted.image_format != "jpeg":
            return {"raw_data": None, "alt": cover.alt, "url": cover.url, "format": fmt}
        cover = converted
        fmt = "jpeg"

    return {"raw_data": b64encode(cover.raw_data).decode(), "alt": cover.alt, "url": cover.url, "format": fmt}

def _load_site_cfg(platform: str) -> dict:
    """加载 app_data/config/sites/{platform}.yaml"""
    import yaml
    site_path = Path(__file__).parent.parent.parent / "app_data" / "config" / "sites" / f"{platform}.yaml"
    if site_path.exists():
        with open(site_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def _find_provider_options(provider: str) -> dict | None:
    """在所有站点配置中查找指定 API provider 的选项（返回第一个启用的）。"""
    import yaml
    sites_dir = Path(__file__).parent.parent.parent / "app_data" / "config" / "sites"
    if not sites_dir.is_dir():
        return None
    for p in sites_dir.glob("*.yaml"):
        with open(p, encoding="utf-8") as f:
            site = yaml.safe_load(f) or {}
        api = site.get("api", {})
        if isinstance(api, dict) and provider in api:
            prov_cfg = api[provider]
            if isinstance(prov_cfg, dict) and prov_cfg.get("enabled", True):
                return prov_cfg
    return None

def _get_engine(engine_id: str, mode: str | None = None, provider: str | None = None, platform: str | None = None):
    cfg = load_config()
    if mode is None:
        mode = cfg.get("mode", "browser")

    # ── API 模式：自动发现 platform 首个启用 provider ──
    if mode == "api" and not provider and platform:
        site = _load_site_cfg(platform)
        api_section = site.get("api", {}) if isinstance(site.get("api"), dict) else {}
        for name, prov in api_section.items():
            if isinstance(prov, dict) and prov.get("enabled", True):
                provider = name
                break

    # ── API 模式：一个 provider 一个 engine ──
    if mode == "api" and provider:
        prov_cfg = _find_provider_options(provider) or {}
        fp = _mode_fingerprint(prov_cfg)
        cache_key = f"{engine_id}:api:{provider}"
        if cache_key in _engines:
            stored_engine, stored_fp = _engines[cache_key]
            if stored_fp == fp:
                return stored_engine
            try:
                stored_engine.close()
            except Exception:
                pass
            del _engines[cache_key]

        opts = Options().set_mode("api").set_api_options(
            name=provider,
            key=prov_cfg.get("key", ""),
            delay=tuple(prov_cfg.get("delay", [3, 5])),
            timeout=prov_cfg.get("timeout", 30),
            retry_times=prov_cfg.get("retry_times", 3),
            backoff_factor=prov_cfg.get("backoff_factor", 2),
            params=prov_cfg.get("params"),
        )
        engine = create_engine(opts)
        _engines[cache_key] = (engine, fp)
        return engine

    # ── browser / requests / api(无provider) 模式 ──
    dl = cfg.get("download", {})
    mode_cfg = dl.get(mode, {})
    fp = _mode_fingerprint(mode_cfg)
    cache_key = f"{engine_id}:{mode}"

    if cache_key in _engines:
        stored_engine, stored_fp = _engines[cache_key]
        if stored_fp == fp:
            return stored_engine
        try:
            stored_engine.close()
        except Exception:
            pass
        del _engines[cache_key]

    opts = Options().set_mode(mode)
    if mode == "browser":
        opts = opts.set_browser_options(
            headless=mode_cfg.get("headless", True),
            browser_type=mode_cfg.get("browser_type", "chromium"),
            user_data_dir=mode_cfg.get("user_data_dir"),
            delay=tuple(mode_cfg.get("delay", [3, 5])),
            timeout=mode_cfg.get("timeout", 30),
            retry_times=mode_cfg.get("retry_times", 3),
            backoff_factor=mode_cfg.get("backoff_factor", 2),
        )
    elif mode == "requests":
        opts = opts.set_requests_options(
            delay=tuple(mode_cfg.get("delay", [3, 5])),
            timeout=mode_cfg.get("timeout", 30),
            retry_times=mode_cfg.get("retry_times", 3),
            backoff_factor=mode_cfg.get("backoff_factor", 2),
        )
    elif mode == "api":
        opts = opts.set_api_options(
            name=mode_cfg.get("name", "default"),
            delay=tuple(mode_cfg.get("delay", [3, 5])),
            timeout=mode_cfg.get("timeout", 30),
            retry_times=mode_cfg.get("retry_times", 3),
            backoff_factor=mode_cfg.get("backoff_factor", 2),
        )

    engine = create_engine(opts)
    _engines[cache_key] = (engine, fp)
    return engine

@router.get("/search")
async def search_novels(platform: str = Query(...), query: str = Query(...), page: int = Query(1), mode: str | None = Query(None), engine_id: str = Query("default")):
    engine = _get_engine(engine_id, mode, platform=platform)
    try: results = search(platform, query, engine, page=page)
    except Exception as e: raise HTTPException(500, str(e))
    return [SearchResultData(title=r.title, author=r.author, url=r.url, description=r.description) for r in results]

@router.post("/novel")
async def fetch_meta(body: FetchMetaRequest, mode: str | None = Query(None)):
    engine = _get_engine(body.engine_id, mode); dl = NovelDownloader(engine)
    try: novel = dl.fetch_meta(body.url)
    except Exception as e: raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count,
            "cover": _encode_cover(novel.cover)}

@router.get("/novel/{novel_id}")
async def get_remote_novel(novel_id: str, url: str = Query(...), engine_id: str = Query("default"), mode: str | None = Query(None)):
    engine = _get_engine(engine_id, mode); dl = NovelDownloader(engine)
    try: novel = dl.fetch_meta(url)
    except Exception as e: raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count}

@router.get("/novel/{novel_id}/chapters")
async def fetch_chapter_list(novel_id: str, url: str = Query(...), engine_id: str = Query("default"), mode: str | None = Query(None)):
    engine = _get_engine(engine_id, mode); dl = NovelDownloader(engine)
    try: chapters = dl.fetch_chapter_list(url)
    except Exception as e: raise HTTPException(500, str(e))
    return [ChapterBrief(id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title,
                         order=ch.order, volume=ch.volume, count=ch.count) for ch in chapters]

@router.post("/novel/{novel_id}/chapter")
async def download_chapters(novel_id: str, body: list[DownloadChapterRequest], engine_id: str = Query("default"), mode: str | None = Query(None)):
    from nldlder.models.novel import Chapter, Chapters, Novel
    from nldlder.core.storage import SQLiteStorage
    from nldlder.core.options import StorageOptions
    engine = _get_engine(engine_id, mode); dl = NovelDownloader(engine)
    chapters = [Chapter(id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title, order=ch.order, volume=ch.volume) for ch in body]
    try:
        results = []
        for ch in chapters:
            downloaded = dl.resolve_chapter(ch)
            if downloaded is not None:
                results.append(downloaded)
        result = Chapters(chapters=results)
    except Exception as e: raise HTTPException(500, str(e))
    store = SQLiteStorage(StorageOptions(backend="sqlite", database_url="sqlite:///app_data/storage/novels.db"))
    novel = Novel(title="", url="", id=novel_id, serial=0, author="", description="")
    store.save_chapter(novel, result)
    return {"downloaded": len(result), "chapters": [{"id": ch.id, "title": ch.title, "order": ch.order, "downloaded": ch.content is not None} for ch in result]}

@router.get("/platform")
async def list_platforms():
    return [{"id": name, "label": cls.__name__ if hasattr(cls, "__name__") else name} for name, cls in get_fetchers().items()]
