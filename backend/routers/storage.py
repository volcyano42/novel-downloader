"""Storage 路由。"""
from base64 import b64decode, b64encode

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.schemas import BackendSwitch, NovelMeta, ChapterData, ChapterBrief
from novelbase.core.options import StorageOptions
from novelbase.core.storage import create_storage
from novelbase.models.novel import Novel, Illustration
from shared.config import get_database_url

router = APIRouter(prefix="/api/v2/storage", tags=["storage"])

_storage = None

def _get_storage():
    global _storage
    if _storage is None:
        _storage = create_storage(StorageOptions(
            backend="sqlite",
            database_url=get_database_url(),
        ))
    return _storage

def _cover_to_response(cover, thumbnail: bool = False) -> dict | None:
    """HEIC -> JPEG 后 base64；PIL 缺失时退回不发送 raw_data。

    thumbnail=True 时生成缩略图（书架列表用，减小响应体与渲染开销）。
    """
    if not cover: return None
    if thumbnail and cover.raw_data:
        cover = cover.thumbnail()
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
    serial = novel.serial
    if not isinstance(serial, int):
        serial = int(serial) if serial else 0
    return NovelMeta(
        title=novel.title, url=novel.url, id=novel.id, serial=serial,
        author=novel.author, description=novel.description,
        tags=list(novel.tags) if novel.tags else None, count=novel.count, cover=cover_data,
        extra=dict(novel.extra) if novel.extra else None,
    )

def _chapter_to_brief(ch) -> ChapterBrief:
    return ChapterBrief(id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title,
                        order=ch.order, volume=ch.volume, count=ch.count,
                        downloaded=ch.content is not None,
                        image_count=len(ch.images))

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
    for novel in store.iter_metas(include_images=True):
        result.append({
            "title": novel.title, "url": novel.url, "id": novel.id,
            "serial": novel.serial, "author": novel.author,
            "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None,
            "count": novel.count,
            "cover": _cover_to_response(novel.cover, thumbnail=True),
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
async def save_meta(novel_id: str, body: NovelMeta):
    store = _get_storage()
    cover = None
    if body.cover and body.cover.raw_data:
        cover = Illustration(
            raw_data=b64decode(body.cover.raw_data),
            alt=body.cover.alt,
            url=body.cover.url,
        )
    novel = Novel(
        title=body.title, url=body.url, id=novel_id,
        serial=body.serial, author=body.author, description=body.description,
        tags=body.tags, count=body.count, cover=cover,
    )
    store.save_meta(novel)
    return {"status": "ok", "novel_id": novel_id}

@router.delete("/novel/{novel_id}")
async def delete_novel(novel_id: str):
    store = _get_storage()
    if not store.load_meta(novel_id): raise HTTPException(404, "小说不存在")
    store.delete_novel(novel_id)
    return {"status": "deleted", "novel_id": novel_id}

@router.get("/novel/{novel_id}/chapters")
async def list_chapters(novel_id: str, order: str | None = Query(None), volume: str | None = Query(None),
                        page: int = Query(1, ge=1), size: int = Query(100, ge=1, le=20000)):
    store = _get_storage(); chapters = store.load_chapters(novel_id, include_images=True)
    result = [_chapter_to_brief(ch) for ch in chapters]
    if order:
        parts = order.split("-"); lo = int(parts[0]) if parts[0] else 1
        hi = int(parts[1]) if len(parts) > 1 and parts[1] else len(result)
        result = [r for r in result if lo <= r.order <= hi]
    if volume: result = [r for r in result if r.volume == volume]
    start = (page - 1) * size; return result[start:start + size]

@router.get("/novel/{novel_id}/chapters/stream")
async def stream_chapters(novel_id: str):
    """SSE 流式返回章节，include_images=True。前端逐行渲染，首屏即见。"""
    store = _get_storage()
    if not store.load_meta(novel_id):
        raise HTTPException(404, "小说不存在")

    def generate():
        for ch in store.iter_chapters(novel_id, include_images=True):
            brief = _chapter_to_brief(ch)
            if hasattr(brief, "model_dump_json"):
                data = brief.model_dump_json()
            else:
                data = brief.json()
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

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
