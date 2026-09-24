"""Download 路由 — 对接 search + resolve_meta/resolve_chapter_list + 后台下载任务管理。"""

from fastapi import APIRouter, HTTPException, Query

from backend.routers.storage import _cover_to_response as encode_cover
from backend.schemas import FetchMetaRequest, DownloadChapterRequest, SearchResultData, ChapterBrief
from backend.services import task_manager
from backend.services.engine_manager import get_cached_engine
from novelbase import resolve_meta, resolve_chapter_list, search
from novelbase.core.exceptions import FeatureNotSupportedError
from novelbase.source import resolve_book_url, list_sources

router = APIRouter(prefix="/api/v2/download", tags=["download"])


def _pick_source(platform: str, mode: str | None, variant: str | None) -> str:
    """把请求中的 platform 标识解析为确定的 source_name。

    最小过渡：书源名 = `platform` 直通（T7 会把本函数整体删除、`source` Query 直通
    `source_name`，届时对旧「站点名 + mode/variant」的兼容彻底消失）。
    """
    return platform


def _require_source(source: str | None, url: str) -> str:
    """URL 无法自动推断书源（core 已删 platform_from_url）——需用户显式指定 source。"""
    if not source:
        raise HTTPException(400, f"无法自动识别书源 URL，请显式指定 source（书源名）: {url}")
    return source


def _engines_for(source_name: str):
    """构造 engines(mode)->engine（按书源名 + mode 懒建并缓存）。"""
    return lambda mode: get_cached_engine(source_name, mode)


def _resolve_url(raw: str) -> str:
    """将输入转为完整 URL（数据驱动）。"""
    try:
        return resolve_book_url(raw)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/search")
async def search_novels(platform: str = Query(...), query: str = Query(...),
                        mode: str = Query("browser"),
                        variant: str | None = Query(None)):
    if query.startswith("http://") or query.startswith("https://"):
        source_name = _pick_source(platform, mode, variant)
        try:
            url = _resolve_url(query)
            novel = await resolve_meta(url, source_name, _engines_for(source_name))
            return [SearchResultData(title=novel.title, author=novel.author,
                                     url=novel.url, description=novel.description,
                                     extra=dict(novel.extra) if getattr(novel, "extra", None) else None)]
        except Exception as e:
            raise HTTPException(500, str(e))

    # "all" → 全部书源（复刻旧 search(platform="all") 语义）；否则单书源。
    if platform == "all":
        sources = list_sources()
        engines = lambda m: get_cached_engine("fanqie", m)
    else:
        source_name = _pick_source(platform, mode, variant)
        sources = [source_name]
        engines = _engines_for(source_name)
    try:
        results = await search(sources, query, engines)
    except FeatureNotSupportedError as e:
        # 该平台/模式组合不支持搜索（如 qidian requests）→ 400 友好提示，而非 500
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
    return [SearchResultData(title=r.title, author=r.author, url=r.url,
                             description=r.description,
                             source_name=getattr(r, 'source_name', ''),
                             cover_url=getattr(r, 'cover_url', None),
                             extra=dict(r.extra) if getattr(r, 'extra', None) else None)
            for r in results]


@router.post("/novel")
async def resolve_meta_route(body: FetchMetaRequest, mode: str = Query("browser"),
                     variant: str | None = Query(None),
                     source: str | None = Query(None)):
    url = _resolve_url(body.url)
    source_name = _pick_source(_require_source(source, url), mode, variant)
    try:
        novel = await resolve_meta(url, source_name, _engines_for(source_name))
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count,
            "cover": encode_cover(novel.cover),
            "extra": dict(novel.extra) if getattr(novel, "extra", None) else None}


@router.get("/novel/{novel_id}")
async def get_remote_novel(novel_id: str, url: str = Query(...),
                           mode: str = Query("browser"), variant: str | None = Query(None),
                           source: str | None = Query(None)):
    url = _resolve_url(url)
    source_name = _pick_source(_require_source(source, url), mode, variant)
    try:
        novel = await resolve_meta(url, source_name, _engines_for(source_name))
    except Exception as e:
        raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count,
            "extra": dict(novel.extra) if getattr(novel, "extra", None) else None}


@router.get("/novel/{novel_id}/chapters")
async def resolve_chapter_list_route(novel_id: str, url: str = Query(...),
                             mode: str = Query("browser"), variant: str | None = Query(None),
                             source: str | None = Query(None)):
    url = _resolve_url(url)
    source_name = _pick_source(_require_source(source, url), mode, variant)
    try:
        chapters = await resolve_chapter_list(url, source_name, _engines_for(source_name))
    except Exception as e:
        raise HTTPException(500, str(e))
    return [ChapterBrief(id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title,
                         order=ch.order, volume=ch.volume, count=ch.count) for ch in chapters]


@router.post("/novel/{novel_id}/chapter")
async def download_chapters(novel_id: str, body: list[DownloadChapterRequest],
                            title: str = Query(""), mode: str = Query("browser"),
                            variant: str | None = Query(None),
                            novel_url: str = Query(""),
                            platform: str = Query("fanqie")):
    chapters_data = [{"id": ch.id, "url": ch.url, "title": ch.title,
                       "order": ch.order, "volume": ch.volume} for ch in body]
    return task_manager.create_task(novel_id, chapters_data, title,
                                    mode, variant, novel_url, platform)


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
    from novelbase.source import list_sources
    return [{"id": name, "label": name} for name in list_sources()]


@router.get("/sources")
async def list_all_sources():
    """返回所有 source 及其完整能力矩阵。"""
    from novelbase.source import list_sources
    from novelbase.source import capabilities as _caps
    result = {}
    for name in list_sources():
        result[name] = {
            "hosts": [],
            "show_name": name,
            "capabilities": _caps(name),
        }
    return result


# ── Detect ────────────────────────────────────────────

@router.post("/detect")
async def detect_platform(body: dict):
    """根据 URL 或 ID 推断平台和完整 URL。前端 URL 猜测逻辑的后端实现。"""
    raw: str = body.get("raw", "")
    if not raw:
        raise HTTPException(400, "缺少 raw 字段")
    from novelbase.source import resolve_book_url
    # core 已删 platform_from_url：无法自动识别书源，仅返回规范化 URL
    try:
        url = resolve_book_url(raw)
        return {"platform": None, "url": url}
    except ValueError:
        return {"platform": None}
