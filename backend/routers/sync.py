"""同步路由 — 触发、查询进度、取消。

同步是**拉**模式：本机主动连对端的 ``/api/v2/storage/*`` 只读取数，
落库在本进程内完成。没有配对、没有凭据（个人项目、仅局域网，见设计文档）。

响应由 ``V2ResponseMiddleware`` 统一包成 ``{ok, message, data}``。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services import sync_task

router = APIRouter(prefix="/api/v2/sync", tags=["sync"])


class StartRequest(BaseModel):
    peer: str = Field(..., description="对端地址，如 192.168.1.20:8000 或 http://192.168.1.20:8000")
    novel_ids: list[str] | None = Field(None, description="只同步这几本；空则全部")
    include_images: bool = Field(False, description="是否连封面/插图一起拉")


@router.post("/start")
async def start_sync(body: StartRequest):
    try:
        return sync_task.start(body.peer, body.novel_ids, body.include_images)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except RuntimeError as e:
        # 已有任务在跑
        raise HTTPException(409, str(e)) from e


@router.get("/status")
async def sync_status():
    """返回当前/最近一次同步的状态；从未同步过时 ``data`` 为 null。"""
    return sync_task.status()


@router.post("/cancel")
async def cancel_sync():
    if not sync_task.cancel():
        raise HTTPException(404, "没有正在进行的同步")
    return {"status": "ok"}
