"""Download 路由 — 对接 search + resolve_meta/resolve_chapter_list + 后台下载任务管理。

契约（spec §3.1）：`source` Query 即 `source_name`；`/search` 的 `source` 为空时并发
全部启用书源（`shared.config.enabled_source_names()`）；MODE 由书源自声明，用户不再传。
"""

import asyncio

from fastapi import APIRouter, HTTPException, Query

from backend.routers.storage import _cover_to_response as encode_cover
from backend.schemas import FetchMetaRequest, DownloadChapterRequest, SearchResultData, ChapterBrief
from backend.services import task_manager
from backend.services.engine_manager import get_cached_engine
from backend.services.source_guard import require_known_source
from novelbase import resolve_meta, resolve_chapter_list, search
from novelbase.core.exceptions import FeatureNotSupportedError
from novelbase.source import resolve_book_url, list_sources, capabilities
from shared.config import enabled_source_names, is_source_enabled

router = APIRouter(prefix="/api/v2/download", tags=["download"])


def _require_source(source: str | None, url: str) -> str:
    """URL 无法自动推断书源（core 已删 platform_from_url）——需用户显式指定 source。"""
    if not source:
        raise HTTPException(400, f"无法自动识别书源 URL，请显式指定 source（书源名）: {url}")
    return require_known_source(source)


def _engines_for(source_name: str):
    """构造 engines(mode)->engine（按书源名 + 能力声明的 mode 懒建并缓存）。"""
    return lambda mode: get_cached_engine(source_name, mode)


def _resolve_url(raw: str) -> str:
    """将输入转为完整 URL（数据驱动）。"""
    try:
        return resolve_book_url(raw)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/search")
async def search_novels(query: str = Query(...), source: str = Query(""),
                        page: int = Query(1)):
    if query.startswith("http://") or query.startswith("https://"):
        # URL 直达：source 必填（core 无 URL→书源推断能力）。
        source_name = _require_source(source, query)
        url = _resolve_url(query)
        try:
            novel = await resolve_meta(url, source_name, _engines_for(source_name))
        except Exception as e:
            raise HTTPException(500, str(e))
        return [SearchResultData(title=novel.title, author=novel.author,
                                 url=novel.url, description=novel.description,
                                 source_name=source_name,
                                 extra=dict(novel.extra) if getattr(novel, "extra", None) else None)]

    # 关键字搜索：source 空 → 并发全部启用书源（每源各绑定自己的引擎）；否则单书源。
    if source:
        source_name = require_known_source(source)
        try:
            results = await search([source_name], query, _engines_for(source_name), page=page)
        except FeatureNotSupportedError as e:
            # 该书源/MODE 组合不支持搜索（如 qidian requests）→ 400 友好提示，而非 500
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(500, str(e))
    else:
        async def _search_one(name: str):
            # 每个源用自己的 _engines_for(name)，杜绝「同 mode 源共用首个源引擎」。
            try:
                return await search([name], query, _engines_for(name), page=page)
            except Exception:
                # 复刻 core.search 的「单源失败静默跳过」：某源出错不影响其它源。
                return ()
        groups = await asyncio.gather(*(_search_one(n) for n in enabled_source_names()))
        results = [r for group in groups for r in group]
    return [SearchResultData(title=r.title, author=r.author, url=r.url,
                             description=r.description,
                             source_name=getattr(r, 'source_name', ''),
                             cover_url=getattr(r, 'cover_url', None),
                             extra=dict(r.extra) if getattr(r, 'extra', None) else None)
            for r in results]


@router.post("/novel")
async def resolve_meta_route(body: FetchMetaRequest, source: str = Query("")):
    url = _resolve_url(body.url)
    source_name = _require_source(source, url)
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
async def get_remote_novel(novel_id: str, url: str = Query(...), source: str = Query("")):
    url = _resolve_url(url)
    source_name = _require_source(source, url)
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
                                     source: str = Query("")):
    url = _resolve_url(url)
    source_name = _require_source(source, url)
    try:
        chapters = await resolve_chapter_list(url, source_name, _engines_for(source_name))
    except Exception as e:
        raise HTTPException(500, str(e))
    return [ChapterBrief(id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title,
                         order=ch.order, volume=ch.volume, count=ch.count) for ch in chapters]


@router.post("/novel/{novel_id}/chapter")
async def download_chapters(novel_id: str, body: list[DownloadChapterRequest],
                            title: str = Query(""), source: str = Query(""),
                            novel_url: str = Query("")):
    source_name = _require_source(source, novel_url)
    chapters_data = [{"id": ch.id, "url": ch.url, "title": ch.title,
                       "order": ch.order, "volume": ch.volume} for ch in body]
    return task_manager.create_task(novel_id, chapters_data, title, source_name, novel_url)


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


@router.get("/sources")
async def list_all_sources():
    """返回全部书源（含未启用）的扁平能力矩阵与启用状态。

    `capabilities(name)` 直出 `{capability: mode}`；`enabled` = 三层读取结果
    （用户层覆盖出厂值，见 `shared.config.is_source_enabled`）。
    """
    return {
        name: {"capabilities": capabilities(name), "enabled": is_source_enabled(name)}
        for name in list_sources()
    }
