"""Download 路由 — 8 条，对接 search + NovelDownloader + 后台下载任务管理。"""
from fastapi import APIRouter, HTTPException, Query
from services.backend.schemas import FetchMetaRequest, DownloadChapterRequest, SearchResultData, ChapterBrief
from services.backend.services.engine_manager import get_or_create_engine
from services.backend.services import task_manager
from services.backend.utils.cover import encode_cover
from nldlder import NovelDownloader, get_fetchers, search

router = APIRouter(prefix="/api/v1/download", tags=["download"])


@router.get("/search")
async def search_novels(platform: str = Query(...), query: str = Query(...),
                        page: int = Query(1), mode: str | None = Query(None),
                        provider: str | None = Query(None), engine_id: str = Query("default")):
    from nldlder.core.downloader import get_fetcher_for_url, get_fetcher_for_id

    engine = get_or_create_engine(engine_id, mode, provider=provider, platform=platform)

    if query.startswith("http://") or query.startswith("https://"):
        fetcher_cls = get_fetcher_for_url(query)
        if fetcher_cls:
            dl = NovelDownloader(engine)
            try:
                novel = dl.fetch_meta(query)
                return [SearchResultData(title=novel.title, author=novel.author,
                                         url=novel.url, description=novel.description)]
            except Exception as e:
                raise HTTPException(500, str(e))

    if query.isdigit():
        fetcher_cls = get_fetcher_for_id(query)
        if fetcher_cls:
            try:
                novel = fetcher_cls().fetch_novel_info(url=query, engine=engine)
                return [SearchResultData(title=novel.title, author=novel.author,
                                         url=novel.url, description=novel.description)]
            except Exception as e:
                raise HTTPException(500, str(e))

    try:
        results = search(platform, query, engine, page=page)
    except Exception as e:
        raise HTTPException(500, str(e))
    return [SearchResultData(title=r.title, author=r.author, url=r.url,
                             description=r.description) for r in results]


@router.post("/novel")
async def fetch_meta(body: FetchMetaRequest, mode: str | None = Query(None),
                     provider: str | None = Query(None)):
    engine = get_or_create_engine(body.engine_id, mode, provider=provider)
    dl = NovelDownloader(engine)
    try:
        novel = dl.fetch_meta(body.url)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count,
            "cover": encode_cover(novel.cover)}


@router.get("/novel/{novel_id}")
async def get_remote_novel(novel_id: str, url: str = Query(...),
                           engine_id: str = Query("default"),
                           mode: str | None = Query(None), provider: str | None = Query(None)):
    engine = get_or_create_engine(engine_id, mode, provider=provider)
    dl = NovelDownloader(engine)
    try:
        novel = dl.fetch_meta(url)
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count}


@router.get("/novel/{novel_id}/chapters")
async def fetch_chapter_list(novel_id: str, url: str = Query(...),
                             engine_id: str = Query("default"),
                             mode: str | None = Query(None), provider: str | None = Query(None)):
    engine = get_or_create_engine(engine_id, mode, provider=provider)
    dl = NovelDownloader(engine)
    try:
        chapters = dl.fetch_chapter_list(url)
    except Exception as e:
        raise HTTPException(500, str(e))
    return [ChapterBrief(id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title,
                         order=ch.order, volume=ch.volume, count=ch.count) for ch in chapters]


@router.post("/novel/{novel_id}/chapter")
async def download_chapters(novel_id: str, body: list[DownloadChapterRequest],
                            title: str = Query(""), engine_id: str = Query("default"),
                            mode: str | None = Query(None), provider: str | None = Query(None),
                            novel_url: str = Query("")):
    chapters_data = [{"id": ch.id, "url": ch.url, "title": ch.title,
                       "order": ch.order, "volume": ch.volume} for ch in body]
    return task_manager.create_task(novel_id, chapters_data, title, engine_id,
                                    mode, provider, novel_url)


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
