"""Download 路由 — 6 条，对接 search + NovelDownloader。"""
from base64 import b64encode
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from backend.schemas import FetchMetaRequest, DownloadChapterRequest, SearchResultData, ChapterBrief
from backend.routers.config import load_config
from nldlder import NovelDownloader, Options, create_engine, get_fetchers, search

router = APIRouter(prefix="/api/v1/download", tags=["download"])

_engines: dict[str, object] = {}

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

def _get_engine(engine_id: str, mode: str | None = None):
    if mode is None:
        cfg = load_config()
        mode = cfg.get("mode", "browser")
    cache_key = f"{engine_id}:{mode}"
    if cache_key not in _engines:
        opts = Options().set_mode(mode)
        if mode == "browser":
            opts = opts.set_browser_options(headless=True)
        _engines[cache_key] = create_engine(opts)
    return _engines[cache_key]

@router.get("/search")
async def search_novels(platform: str = Query(...), query: str = Query(...), page: int = Query(1), mode: str | None = Query(None), engine_id: str = Query("default")):
    engine = _get_engine(engine_id, mode)
    try: results = search(platform, query, engine, page=page)
    except Exception as e: raise HTTPException(500, str(e))
    return [SearchResultData(title=r.title, author=r.author, url=r.url, description=r.description) for r in results]

@router.post("/novel")
async def fetch_meta(body: FetchMetaRequest):
    engine = _get_engine(body.engine_id); dl = NovelDownloader(engine)
    try: novel = dl.fetch_meta(body.url)
    except Exception as e: raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count,
            "cover": _encode_cover(novel.cover)}

@router.get("/novel/{novel_id}")
async def get_remote_novel(novel_id: str, url: str = Query(...), engine_id: str = Query("default")):
    engine = _get_engine(engine_id); dl = NovelDownloader(engine)
    try: novel = dl.fetch_meta(url)
    except Exception as e: raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count}

@router.get("/novel/{novel_id}/chapters")
async def fetch_chapter_list(novel_id: str, url: str = Query(...), engine_id: str = Query("default")):
    engine = _get_engine(engine_id); dl = NovelDownloader(engine)
    try: chapters = dl.fetch_chapter_list(url)
    except Exception as e: raise HTTPException(500, str(e))
    return [ChapterBrief(id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title,
                         order=ch.order, volume=ch.volume, count=ch.count) for ch in chapters]

@router.post("/novel/{novel_id}/chapter")
async def download_chapters(novel_id: str, body: list[DownloadChapterRequest], engine_id: str = Query("default")):
    from nldlder.models.novel import Chapter, Chapters, Novel
    from nldlder import LocalStorage
    from nldlder.core.options import StorageOptions
    engine = _get_engine(engine_id); dl = NovelDownloader(engine)
    chapters = [Chapter(id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title, order=ch.order, volume=ch.volume) for ch in body]
    try:
        results = []
        for ch in chapters:
            result = dl.resolve_chapter(ch)
            results.extend(result)
        result = Chapters(results)
    except Exception as e: raise HTTPException(500, str(e))
    base_dir = Path(__file__).parent.parent.parent / "app_data" / "storage"
    store = LocalStorage(StorageOptions(base_dir=base_dir))
    novel = Novel(title="", url="", id=novel_id, serial=0, author="", description="")
    store.save_chapter(novel, result)
    return {"downloaded": len(result), "chapters": [{"id": ch.id, "title": ch.title, "order": ch.order, "is_complete": ch.is_complete} for ch in result]}

@router.get("/platform")
async def list_platforms():
    return [{"id": name, "label": cls.__name__ if hasattr(cls, "__name__") else name} for name, cls in get_fetchers().items()]
