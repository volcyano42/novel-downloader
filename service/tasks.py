"""任务注册表 — 追踪活跃下载任务状态，线程安全。"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Literal

TaskStatus = Literal["pending", "downloading", "paused", "done", "error", "cancelled"]


@dataclass
class Task:
    task_id: str
    title: str = ""
    status: TaskStatus = "pending"
    downloaded: int = 0
    total: int = 0
    message: str = ""
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "status": self.status,
            "downloaded": self.downloaded,
            "total": self.total,
            "message": self.message,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


_tasks: dict[str, Task] = {}
_lock = threading.Lock()


def create_task(task_id: str, title: str = "", total: int = 0) -> Task:
    """注册一个新任务。"""
    with _lock:
        task = Task(task_id=task_id, title=title, total=total, status="pending")
        _tasks[task_id] = task
        return task


def update_task(task_id: str, **kwargs):
    """更新任务字段。"""
    with _lock:
        task = _tasks.get(task_id)
        if task is None:
            return
        for k, v in kwargs.items():
            if hasattr(task, k):
                setattr(task, k, v)


def set_status(task_id: str, status: TaskStatus, message: str = ""):
    """设置任务状态。"""
    with _lock:
        task = _tasks.get(task_id)
        if task is None:
            return
        task.status = status
        if message:
            task.message = message
        if status in ("done", "error", "cancelled"):
            task.finished_at = time.time()


def get_task(task_id: str) -> Task | None:
    with _lock:
        return _tasks.get(task_id)


def get_active_tasks() -> list[dict]:
    """返回所有活跃任务（未完成/未取消）。"""
    with _lock:
        return [
            t.to_dict()
            for t in _tasks.values()
            if t.status not in ("done", "error", "cancelled")
        ]


def get_all_tasks() -> list[dict]:
    """返回所有任务（含已完成）。"""
    with _lock:
        return [t.to_dict() for t in _tasks.values()]


def remove_task(task_id: str):
    """移除任务记录。"""
    with _lock:
        _tasks.pop(task_id, None)


def cleanup_stale(ttl_seconds: float = 300):
    """清理已完成超过 ttl 秒的任务。"""
    now = time.time()
    with _lock:
        stale = [
            tid
            for tid, t in _tasks.items()
            if t.status in ("done", "error", "cancelled")
            and t.finished_at is not None
            and (now - t.finished_at) > ttl_seconds
        ]
        for tid in stale:
            del _tasks[tid]
