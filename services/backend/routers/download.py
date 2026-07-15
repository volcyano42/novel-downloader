"""Download 路由 — 对接 search + fetch_meta/fetch_chapter_list + 后台下载任务管理。"""
import asyncio
from functools import partial

from fastapi import APIRouter, HTTPException, Query
from services.backend.schemas import FetchMetaRequest, DownloadChapterRequest, SearchResultData, ChapterBrief
from services.backend.services.engine_manager import get_cached_engine, _browser_executor, _requests_executor
from services.backend.services import task_manager
from services.backend.routers.storage import _cover_to_response as encode_cover
from novelbase import fetch_meta, fetch_chapter_list, get_fetchers, search

router = APIRouter(prefix="/api/v2/download", tags=["download"])


def _platform_from_url(url: str) -> str:
    """从 URL 推断平台。"""
    if "fanqienovel.com" in url:
        return "fanqie"
    if "qidian.com" in url:
        return "qidian"
    if "qimao.com" in url:
        return "qimao"
    return "fanqie"  # 默认


def _pick_executor(mode: str):
    return _browser_executor if mode == "browser" else _requests_executor


@router.get("/search")
async def search_novels(platform: str = Query(...), query: str = Query(...),
                        page: int = Query(1), mode: str = Query("browser"),
                        provider: str | None = Query(None)):
    from novelbase.core.downloader import get_fetcher_for_url, get_fetcher_for_id

    engine = get_cached_engine(platform, mode, provider=provider)
    executor = _pick_executor(mode)
    loop = asyncio.get_event_loop()

    if query.startswith("http://") or query.startswith("https://"):
        fetcher_cls = get_fetcher_for_url(query)
        if fetcher_cls:
            try:
                novel = await loop.run_in_executor(executor, fetch_meta, query, engine)
                return [SearchResultData(title=novel.title, author=novel.author,
                                         url=novel.url, description=novel.description,
                                         extras=dict(novel.extras) if getattr(novel, "extras", None) else None)]
            except Exception as e:
                raise HTTPException(500, str(e))

    if query.isdigit():
        fetcher_cls = get_fetcher_for_id(query)
        if fetcher_cls:
            try:
                novel = await loop.run_in_executor(
                    executor, partial(fetcher_cls().fetch_novel_info, url=query, engine=engine))
                return [SearchResultData(title=novel.title, author=novel.author,
                                         url=novel.url, description=novel.description,
                                         extras=dict(novel.extras) if getattr(novel, "extras", None) else None)]
            except Exception as e:
                raise HTTPException(500, str(e))

    try:
        results = await loop.run_in_executor(executor, search, platform, query, engine, page)
    except Exception as e:
        raise HTTPException(500, str(e))
    return [SearchResultData(title=r.title, author=r.author, url=r.url,
                             description=r.description,
                             extras=dict(r.extras) if getattr(r, 'extras', None) else None)
            for r in results]


@router.post("/novel")
async def fetch_meta_route(body: FetchMetaRequest, mode: str = Query("browser"),
                     provider: str | None = Query(None)):
    platform = _platform_from_url(body.url)
    engine = get_cached_engine(platform, mode, provider=provider)
    executor = _pick_executor(mode)
    loop = asyncio.get_event_loop()
    try:
        novel = await loop.run_in_executor(executor, fetch_meta, body.url, engine)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count,
            "cover": encode_cover(novel.cover),
            "extras": dict(novel.extras) if getattr(novel, "extras", None) else None}


@router.get("/novel/{novel_id}")
async def get_remote_novel(novel_id: str, url: str = Query(...),
                           mode: str = Query("browser"), provider: str | None = Query(None)):
    platform = _platform_from_url(url)
    engine = get_cached_engine(platform, mode, provider=provider)
    executor = _pick_executor(mode)
    loop = asyncio.get_event_loop()
    try:
        novel = await loop.run_in_executor(executor, fetch_meta, url, engine)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count,
            "extras": dict(novel.extras) if getattr(novel, "extras", None) else None}


@router.get("/novel/{novel_id}/chapters")
async def fetch_chapter_list_route(novel_id: str, url: str = Query(...),
                             mode: str = Query("browser"), provider: str | None = Query(None)):
    platform = _platform_from_url(url)
    engine = get_cached_engine(platform, mode, provider=provider)
    executor = _pick_executor(mode)
    loop = asyncio.get_event_loop()
    try:
        chapters = await loop.run_in_executor(executor, fetch_chapter_list, url, engine)
    except Exception as e:
        raise HTTPException(500, str(e))
    return [ChapterBrief(id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title,
                         order=ch.order, volume=ch.volume, count=ch.count) for ch in chapters]


@router.post("/novel/{novel_id}/chapter")
async def download_chapters(novel_id: str, body: list[DownloadChapterRequest],
                            title: str = Query(""), mode: str = Query("browser"),
                            provider: str | None = Query(None),
                            novel_url: str = Query(""),
                            platform: str = Query("fanqie")):
    chapters_data = [{"id": ch.id, "url": ch.url, "title": ch.title,
                       "order": ch.order, "volume": ch.volume} for ch in body]
    return task_manager.create_task(novel_id, chapters_data, title,
                                    mode, provider, novel_url, platform)


@router.get("/tasks")
async def list_tasks():
    return task_manager.list_tasks()


@router.post("/task/{task_id}/pause")
async def pause_task(task_id: str):
    if not task_manager.pause_task(task_id):
        raise HTTPException(404, "任务不存在或不可暂停")
    return {"status": "ok"}


@router.post("/task/{task_id}/resume")
async def resume_task(task_id: str):
    if not task_manager.resume_task(task_id):
        raise HTTPException(404, "任务不存在或不可恢复")
    return {"status": "ok"}


@router.delete("/task/{task_id}")
async def delete_task(task_id: str):
    if not task_manager.delete_task(task_id):
        raise HTTPException(404, "任务不存在")
    return {"status": "ok"}


@router.get("/platform")
async def list_platforms():
    return [{"id": name, "label": cls.__name__ if hasattr(cls, "__name__") else name}
            for name, cls in get_fetchers().items()]
