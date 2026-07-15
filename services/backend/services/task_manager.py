"""下载任务管理器 — 后台线程池、暂停/恢复、进度跟踪。"""
import logging
import threading
import uuid

from services.backend.services.config_service import load_config
from services.backend.services.engine_manager import get_cached_engine

_log = logging.getLogger("services.backend.task_manager")


_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()


def _run_download(task: dict, mode: str, provider: str | None, platform: str):
    """后台线程：创建 engine → 并发下载章节 → close engine，支持暂停/恢复。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from novelbase import fetch_meta, resolve_chapter
    from novelbase.models.novel import Chapter, Chapters, Novel
    from novelbase.core.storage import create_storage
    from novelbase.core.options import StorageOptions

    engine = get_cached_engine(platform, mode, provider=provider)
    try:
        store = create_storage(StorageOptions(
            backend="sqlite",
            database_url="sqlite:///app_data/storage/novels.db",
        ))

        novel_url = task.get("novel_url", "")
        if novel_url:
            try:
                meta = fetch_meta(novel_url, engine)
                store.save_meta(meta)
            except Exception:
                _log.warning("fetch_meta failed for %s", novel_url, exc_info=True)
                pass
        novel = Novel(title=task["title"], url=novel_url, id=task["novel_id"],
                      serial=0, author="", description="")

        cfg = load_config()
        max_workers = cfg.get("download", {}).get("max_workers", 3)

        def _download_one(ch_data: dict):
            if task["_pause"].is_set():
                with _tasks_lock:
                    if task["status"] == "downloading":
                        task["status"] = "paused"
                task["_pause"].wait()
                with _tasks_lock:
                    if task["status"] == "paused":
                        task["status"] = "downloading"

            ch = Chapter(id=ch_data["id"], url=ch_data["url"], novel_id=task["novel_id"],
                         title=ch_data["title"], order=ch_data["order"],
                         volume=ch_data.get("volume"))
            try:
                downloaded = resolve_chapter(ch, engine)
                if downloaded is not None:
                    store.save_chapter(novel, Chapters(chapters=[downloaded]))
                    with _tasks_lock:
                        task["current_title"] = downloaded.title
                else:
                    with _tasks_lock:
                        task["errors"].append(f"章节不可获取: {ch.title}")
            except Exception as e:
                with _tasks_lock:
                    task["errors"].append(f"{ch.title}: {e}")
            finally:
                with _tasks_lock:
                    task["progress"] += 1

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_download_one, ch) for ch in task["chapters"]]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    _log.warning("future.result() failed in download task", exc_info=True)

        task["status"] = "completed"
        if task["errors"]:
            task["error"] = "; ".join(task["errors"][:3])
    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)



def create_task(novel_id: str, chapters: list[dict], title: str,
                mode: str = "browser", provider: str | None = None,
                novel_url: str = "", platform: str = "fanqie") -> dict:
    task_id = str(uuid.uuid4())[:8]
    task = {
        "task_id": task_id, "novel_id": novel_id, "title": title,
        "total": len(chapters), "progress": 0, "status": "downloading",
        "error": None, "errors": [], "current_title": "",
        "chapters": chapters, "novel_url": novel_url,
        "_pause": threading.Event(),
        "_mode": mode, "_provider": provider, "_platform": platform,
    }
    with _tasks_lock:
        _tasks[task_id] = task

    t = threading.Thread(target=_run_download, args=(task, mode, provider, platform),
                         daemon=True)
    t.start()
    return {"task_id": task_id, "total": len(chapters)}


def list_tasks() -> list[dict]:
    with _tasks_lock:
        return [
            {"task_id": t["task_id"], "novel_id": t["novel_id"], "title": t["title"],
             "total": t["total"], "progress": t["progress"], "status": t["status"],
             "error": t.get("error"), "errors": t.get("errors", []),
             "current_title": t.get("current_title", "")}
            for t in _tasks.values()
        ]


def get_task(task_id: str) -> dict | None:
    return _tasks.get(task_id)


def pause_task(task_id: str) -> bool:
    task = _tasks.get(task_id)
    if task and task.get("_pause"):
        task["_pause"].set()
        return True
    return False


def resume_task(task_id: str) -> bool:
    task = _tasks.get(task_id)
    if not task or not task.get("_pause"):
        return False
    if task["status"] == "paused":
        task["_pause"].clear()
        task["status"] = "downloading"
        return True
    if task["status"] == "failed":
        task["_pause"].clear()
        task["status"] = "downloading"
        task["error"] = None
        task["errors"] = []
        task["progress"] = 0
        t = threading.Thread(
            target=_run_download,
            args=(task, task.get("_mode", "browser"), task.get("_provider"), task.get("_platform", "fanqie")),
            daemon=True,
        )
        t.start()
        return True
    return False


def delete_task(task_id: str) -> bool:
    with _tasks_lock:
        task = _tasks.pop(task_id, None)
        if task and task.get("_pause"):
            task["_pause"].set()
        return task is not None
