"""同步任务管理 — 在后端进程内跑同步，并把进度暴露给 UI。

与 :mod:`backend.services.task_manager` 的区别：下载是「多任务并发」，同步是
「同时只允许一个」（两路同步会争抢同一批 SQLite 写锁，且语义上没意义）。

任务状态放在模块级 dict 里，进程重启即丢——同步本来就是一次性动作，
历史结果没有保留价值。
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from novelbase.core.storage import StorageOptions, create_storage
from novelbase.core.sync import SyncError, sync_from
from shared.config import get_database_url

_log = logging.getLogger("backend.sync_task")

_state: dict[str, Any] | None = None
_lock = threading.Lock()
_storage = None


def _get_storage():
    """与 CLI / backend 共用同一套存储目录（sqlite, app_data/storage/novels）。"""
    global _storage
    if _storage is None:
        _storage = create_storage(StorageOptions(backend="sqlite",
                                                 database_url=get_database_url()))
    return _storage


def _new_state(peer: str, novel_ids: list[str] | None, include_images: bool) -> dict[str, Any]:
    return {
        "running": True,
        "phase": "scanning",
        "peer": peer,
        "include_images": include_images,
        "requested_novels": list(novel_ids or []),
        "books_total": 0,
        "books_done": 0,
        "chapters_total": 0,
        "chapters_done": 0,
        "current_book": "",
        "current_chapter": "",
        "summary": "",
        "error": None,
        "started_at": time.time(),
        "finished_at": None,
        "_stop": False,
    }


def _public(state: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in state.items() if not k.startswith("_")}


def status() -> dict[str, Any] | None:
    with _lock:
        return _public(_state) if _state else None


def cancel() -> bool:
    with _lock:
        if not _state or not _state.get("running"):
            return False
        _state["_stop"] = True
        return True


def start(peer: str, novel_ids: list[str] | None = None,
          include_images: bool = False) -> dict[str, Any]:
    """启动一次同步。已有任务在跑时抛 RuntimeError。"""
    global _state
    peer = (peer or "").strip()
    if not peer:
        raise ValueError("对端地址不能为空")
    if not peer.startswith(("http://", "https://")):
        peer = f"http://{peer}"

    with _lock:
        if _state and _state.get("running"):
            raise RuntimeError("已有同步在进行中")
        _state = _new_state(peer, novel_ids, include_images)
        state = _state

    # start 是同步函数、由 async 路由调用 → 事件循环正在运行，可以拿到当前 loop
    loop = asyncio.get_running_loop()
    loop.create_task(_run(state, peer, novel_ids, include_images))
    return _public(state)


async def _run(state: dict[str, Any], peer: str,
               novel_ids: list[str] | None, include_images: bool) -> None:
    store = _get_storage()

    def on_progress(payload: dict[str, Any]) -> None:
        # 只合并进度字段，不覆盖 running/error 等控制字段
        state.update({k: v for k, v in payload.items() if not k.startswith("_")})

    try:
        result = await sync_from(
            store, peer,
            novel_ids=novel_ids,
            include_images=include_images,
            progress_cb=on_progress,
            should_stop=lambda: bool(state.get("_stop")),
        )
        state["summary"] = result.summary()
        state["order_mismatch"] = list(result.order_mismatch)
    except SyncError as e:
        state["error"] = str(e)
    except Exception as e:            # noqa: BLE001 — 兜底，避免任务永远停在 running
        _log.exception("同步异常")
        state["error"] = f"{type(e).__name__}: {e}"
    finally:
        with _lock:
            state["running"] = False
            state["finished_at"] = time.time()
            if state.get("_stop") and not state.get("error"):
                state["phase"] = "cancelled"
            elif state.get("error"):
                state["phase"] = "error"
            else:
                state["phase"] = "done"
        _log.info("同步结束：%s", state.get("summary") or state.get("error") or "已取消")
