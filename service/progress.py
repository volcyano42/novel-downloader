"""SSE 进度推送管理。"""
from __future__ import annotations

import asyncio
import json
import threading

_progress_queues: dict[str, asyncio.Queue] = {}
_progress_lock = threading.Lock()


def emit(task_id: str, typ: str, text: str,
         downloaded: int | None = None, total: int | None = None,
         title: str | None = None):
    """向 task_id 对应的 SSE 队列发送一条消息。

    typ 可以是 'log', 'progress', 'done', 'error', 'end'。
    结构化字段 downloaded/total 用于进度条渲染。
    """
    with _progress_lock:
        q = _progress_queues.get(task_id)
    if q:
        payload = {"type": typ, "text": text}
        if downloaded is not None:
            payload["downloaded"] = downloaded
        if total is not None:
            payload["total"] = total
        if title is not None:
            payload["title"] = title
        try:
            q.put_nowait(json.dumps(payload))
        except asyncio.QueueFull:
            pass


def finish(task_id: str, status: str):
    """标记 task_id 对应的任务结束。"""
    with _progress_lock:
        q = _progress_queues.get(task_id)
    if q:
        try:
            q.put_nowait(json.dumps({"type": "end", "status": status, "text": ""}))
        except asyncio.QueueFull:
            pass


async def sse_progress(task_id: str):
    """SSE 事件流生成器。"""
    from fastapi.responses import StreamingResponse

    q = asyncio.Queue(maxsize=100)
    with _progress_lock:
        _progress_queues[task_id] = q

    async def gen():
        try:
            while True:
                msg = await q.get()
                yield f"data: {msg}\n\n"
                if '"type": "end"' in msg:
                    break
        except asyncio.CancelledError:
            pass
        finally:
            with _progress_lock:
                _progress_queues.pop(task_id, None)

    return StreamingResponse(gen(), media_type="text/event-stream")
