"""Storage 路由。"""
from base64 import b64encode

from fastapi import APIRouter, HTTPException, Query
from services.backend.schemas import BackendSwitch, NovelMeta, ChapterData, ChapterBrief
from nldlder.core.storage import create_storage
from nldlder.core.options import StorageOptions

router = APIRouter(prefix="/api/v1/storage", tags=["storage"])

_storage = None

def _get_storage():
    global _storage
    if _storage is None:
        _storage = create_storage(StorageOptions(
            backend="sqlite",
            database_url="sqlite:///app_data/storage/novels.db",
        ))
    return _storage

def _cover_to_response(cover) -> dict | None:
    """HEIC → JPEG 后 base64；PIL 缺失时退回不发送 raw_data。"""
    if not cover: return None
    if not cover.raw_data:
        return {"raw_data": None, "alt": cover.alt, "url": cover.url, "format": cover.image_format}

    fmt = cover.image_format
    if fmt in ("heic", "heif"):
        converted = cover.convert("jpeg", quality=90)
        if converted.image_format != "jpeg":
            # ponytail: PIL/pillow-heif 未安装，convert 是 no-op，退回到不发送 raw_data
            return {"raw_data": None, "alt": cover.alt, "url": cover.url, "format": fmt}
        cover = converted
        fmt = "jpeg"

    return {
        "raw_data": b64encode(cover.raw_data).decode(),
        "alt": cover.alt,
        "url": cover.url,
        "format": fmt,
    }

def _novel_to_meta(novel) -> NovelMeta:
    cover_data = _cover_to_response(novel.cover)
    return NovelMeta(
        title=novel.title, url=novel.url, id=novel.id, serial=novel.serial,
        author=novel.author, description=novel.description,
        tags=list(novel.tags) if novel.tags else None, count=novel.count, cover=cover_data,
    )

def _chapter_to_brief(ch) -> ChapterBrief:
    return ChapterBrief(id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title,
                        order=ch.order, volume=ch.volume, count=ch.count,
                        downloaded=ch.content is not None)

def _chapter_to_data(ch) -> ChapterData:
    return ChapterData(
        id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title, order=ch.order,
        volume=ch.volume, content=ch.content, time=ch.time, count=ch.count,
        images=[{"raw_data": b64encode(img.raw_data).decode() if img.raw_data else None,
                  "alt": img.alt, "insert": img.insert, "url": img.url} for img in ch.images],
    )

@router.get("/backend")
async def list_backends(): return {"backends": ["local", "sqlite"], "current": "sqlite"}

@router.put("/backend")
async def switch_backend(body: BackendSwitch): return {"backend": body.backend, "status": "switched"}

@router.get("/novel")
async def list_novels():
    store = _get_storage()
    result: list[dict] = []
    for novel in store.iter_metas():
        result.append({
            "title": novel.title, "url": novel.url, "id": novel.id,
            "serial": novel.serial, "author": novel.author,
            "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None,
            "count": novel.count,
            "cover": None,  # 书架列表不传封面，减少响应体积
        })
    return result

@router.get("/novel/{novel_id}/cover")
async def get_cover(novel_id: str):
    """只加载封面插图，不读整本小说 meta。"""
    store = _get_storage()
    novel = store.load_meta(novel_id)
    if not novel: raise HTTPException(404, "小说不存在")
    return _cover_to_response(novel.cover)

@router.get("/novel/{novel_id}/meta")
async def get_meta(novel_id: str):
    store = _get_storage(); novel = store.load_meta(novel_id)
    if not novel: raise HTTPException(404, "小说不存在")
    return _novel_to_meta(novel)

@router.put("/novel/{novel_id}/meta")
async def save_meta(novel_id: str, body: NovelMeta): return {"status": "ok", "novel_id": novel_id}

@router.delete("/novel/{novel_id}")
async def delete_novel(novel_id: str):
    store = _get_storage()
    if not store.load_meta(novel_id): raise HTTPException(404, "小说不存在")
    store.delete_novel(novel_id)
    return {"status": "deleted", "novel_id": novel_id}

@router.get("/novel/{novel_id}/chapters")
async def list_chapters(novel_id: str, order: str | None = Query(None), volume: str | None = Query(None),
                        status: str | None = Query(None), page: int = Query(1, ge=1), size: int = Query(100, ge=1, le=20000)):
    store = _get_storage(); chapters = store.load_chapters(novel_id)
    result = [_chapter_to_brief(ch) for ch in chapters]
    if order:
        parts = order.split("-"); lo = int(parts[0]) if parts[0] else 1
        hi = int(parts[1]) if len(parts) > 1 and parts[1] else len(result)
        result = [r for r in result if lo <= r.order <= hi]
    if volume: result = [r for r in result if r.volume == volume]
    # is_complete 字段已移除，status 过滤暂时不做
    if status: pass
    start = (page - 1) * size; return result[start:start + size]

@router.put("/novel/{novel_id}/chapters")
async def save_chapters(novel_id: str, body: list[ChapterData]): return {"status": "ok", "count": len(body)}

@router.get("/novel/{novel_id}/chapter/{chapter_id}")
async def get_chapter(novel_id: str, chapter_id: str):
    store = _get_storage(); ch = store.load_chapter(novel_id, chapter_id)
    if not ch: raise HTTPException(404, "章节不存在")
    return _chapter_to_data(ch)

@router.delete("/novel/{novel_id}/chapter/{chapter_id}")
async def delete_chapter(novel_id: str, chapter_id: str):
    _get_storage().delete_chapter(novel_id, chapter_id)
    return {"status": "deleted"}
