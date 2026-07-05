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

def _get_engine(engine_id: str):
    if engine_id not in _engines:
        _engines[engine_id] = create_engine(Options().set_mode("browser").set_browser_options(headless=True))
    return _engines[engine_id]

@router.get("/search")
async def search_novels(platform: str | None = Query(None), query: str = Query(...), page: int = Query(1), engine_id: str = Query("default")):
    if not platform:
        platform = load_config().get("platform", "fanqie")
    engine = _get_engine(engine_id)
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
async def get_remote_novel(novel_id: str, engine_id: str = Query("default")):
    from nldlder import get_fetcher_for_id
    fc = get_fetcher_for_id(novel_id)
    if fc is None: raise HTTPException(400, f"无法识别 novel_id: {novel_id}")
    url = f"https://fanqienovel.com/page/{novel_id}" if fc.__name__ == "FanqieFetcher" else f"https://www.qidian.com/book/{novel_id}/"
    engine = _get_engine(engine_id); dl = NovelDownloader(engine); novel = dl.fetch_meta(url)
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count}

@router.get("/novel/{novel_id}/chapters")
async def fetch_chapter_list(novel_id: str, engine_id: str = Query("default")):
    from nldlder import get_fetcher_for_id
    fc = get_fetcher_for_id(novel_id)
    if fc is None: raise HTTPException(400, f"无法识别 novel_id: {novel_id}")
    url = f"https://fanqienovel.com/page/{novel_id}" if fc.__name__ == "FanqieFetcher" else f"https://www.qidian.com/book/{novel_id}/"
    engine = _get_engine(engine_id); dl = NovelDownloader(engine); chapters = dl.fetch_chapter_list(url)
    return [ChapterBrief(id=ch.id, url=ch.url, index_url=ch.index_url, title=ch.title,
                         order=ch.order, volume=ch.volume, count=ch.count, is_complete=ch.is_complete) for ch in chapters]

@router.post("/novel/{novel_id}/chapter")
async def download_chapters(novel_id: str, body: list[DownloadChapterRequest], engine_id: str = Query("default")):
    from nldlder.models.novel import Chapter, Chapters, Novel
    from nldlder import LocalStorage
    from nldlder.core.options import StorageOptions
    engine = _get_engine(engine_id); dl = NovelDownloader(engine)
    chapters = Chapters([Chapter(id=ch.id, url=ch.url, index_url=ch.index_url, title=ch.title, order=ch.order, volume=ch.volume) for ch in body])
    try: result = dl.resolve_chapters(chapters)
    except Exception as e: raise HTTPException(500, str(e))
    base_dir = Path(__file__).parent.parent.parent / "app_data" / "storage"
    store = LocalStorage(StorageOptions(base_dir=base_dir))
    novel = Novel(title="", url="", id=novel_id, serial=0, author="", description="")
    store.save_chapter(novel, result)
    return {"downloaded": len(result), "chapters": [{"id": ch.id, "title": ch.title, "order": ch.order, "is_complete": ch.is_complete} for ch in result]}

@router.get("/platform")
async def list_platforms():
    return [{"id": name, "label": cls.__name__ if hasattr(cls, "__name__") else name} for name, cls in get_fetchers().items()]


