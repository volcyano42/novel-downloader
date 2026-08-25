"""Engine 路由 — 6 条，委托 engine_manager。"""
from fastapi import APIRouter, HTTPException

from backend.schemas import CreateEngineRequest, UpdateEngineRequest
from backend.services import engine_manager

router = APIRouter(prefix="/api/v2/engine", tags=["engine"])


@router.get("")
async def list_engines():
    return engine_manager.list_explicit_engines()


@router.post("/create")
async def create(body: CreateEngineRequest):
    return engine_manager.create_explicit_engine(
        body.mode, body.platform, body.api, body.requests, body.browser)


@router.get("/type/list")
async def list_engine_types():
    return {"types": ["api", "browser", "requests"]}


@router.get("/{engine_id}")
async def get_engine(engine_id: str):
    result = engine_manager.get_explicit_engine(engine_id)
    if not result:
        raise HTTPException(404, "引擎不存在")
    return result


@router.put("/{engine_id}")
async def update_engine(engine_id: str, body: UpdateEngineRequest):
    result = engine_manager.update_explicit_engine(
        engine_id, body.mode, body.api, body.requests, body.browser)
    if result is None:
        info = engine_manager.get_explicit_engine(engine_id)
        if info is None:
            raise HTTPException(404, "引擎不存在")
        raise HTTPException(400, f"无效的 mode 或缺少对应选项: {body.mode}")
    return result


@router.delete("/{engine_id}")
async def delete_engine(engine_id: str):
    if not await engine_manager.delete_explicit_engine(engine_id):
        raise HTTPException(404, "引擎不存在")
    return {"status": "deleted", "engine_id": engine_id}
