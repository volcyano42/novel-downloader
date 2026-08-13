"""下载任务管理器 — 后台线程池、暂停/恢复、进度跟踪、真正取消。"""
import logging
import threading
import time
import uuid

from novelbase.core.exceptions import ChapterNotFoundError
from shared.config import load_config, get_database_url
from backend.services.engine_manager import get_cached_engine

_log = logging.getLogger("backend.task_manager")

_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()


def _run_download(task: dict, mode: str, variant: str | None, platform: str):
    """后台线程：创建 engine → 并发下载章节 → close engine，支持暂停/取消。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from novelbase import resolve_meta, resolve_chapter
    from novelbase.models.novel import Chapter, Chapters, Novel
    from novelbase.core.storage import create_storage
    from novelbase.core.options import StorageOptions

    engine = get_cached_engine(platform, mode, variant=variant)
    try:
        store = create_storage(StorageOptions(
            backend="sqlite",
            database_url=get_database_url(),
        ))

        novel_url = task.get("novel_url", "")
        if novel_url:
            try:
                meta = resolve_meta(novel_url, engine)
                store.save_meta(meta)
            except Exception:
                _log.warning("fetch_meta failed for %s", novel_url, exc_info=True)

        novel = Novel(title=task["title"], url=novel_url, id=task["novel_id"],
                      serial=0, author="", description="")

        cfg = load_config()
        max_workers = cfg.get("download", {}).get("max_workers", 3)

        _eta_samples: list[float] = []
        _eta_lock = threading.Lock()

        def _update_eta(elapsed: float):
            with _eta_lock:
                _eta_samples.append(elapsed)
                if len(_eta_samples) > 10:
                    _eta_samples.pop(0)
                avg = sum(_eta_samples) / len(_eta_samples)
                remaining = task["total"] - task["progress"]
                eta_seconds = avg * remaining / max(1, max_workers)
                with _tasks_lock:
                    task["eta"] = eta_seconds

        def _download_one(ch_data: dict):
            # ── 取消检查（开始前）──
            if task["_cancel"].is_set():
                return

            # ── 暂停逻辑 ──
            if task["_pause"].is_set():
                with _tasks_lock:
                    task["status"] = "paused"
                task["_pause"].wait()
                if task["_cancel"].is_set():
                    return
                with _tasks_lock:
                    task["status"] = "downloading"

            # 标记章节为下载中
            with _tasks_lock:
                ch_data["status"] = "downloading"

            ch = Chapter(id=ch_data["id"], url=ch_data["url"], novel_id=task["novel_id"],
                         title=ch_data["title"], order=ch_data["order"],
                         volume=ch_data.get("volume"))
            max_retries = 3
            t0 = time.time()
            downloaded = None
            for attempt in range(max_retries + 1):
                if attempt > 0:
                    time.sleep(2 * attempt)
                try:
                    downloaded = resolve_chapter(ch, engine)
                except ChapterNotFoundError:
                    if attempt < max_retries:
                        continue
                    with _tasks_lock:
                        task["errors"].append(f"{ch.title}: 内容为空(已重试{max_retries}次)")
                        ch_data["status"] = "failed"
                        ch_data["error"] = f"内容为空(已重试{max_retries}次)"
                    break
                except Exception as e:
                    with _tasks_lock:
                        task["errors"].append(f"{ch.title}: {e}")
                        ch_data["status"] = "failed"
                        ch_data["error"] = str(e)
                    break
                else:
                    # ── 取消检查（下载完成后、落库前）──
                    if task["_cancel"].is_set():
                        return
                    if downloaded is not None:
                        store.save_chapter(novel, Chapters(chapters=[downloaded]))
                        with _tasks_lock:
                            task["current_title"] = downloaded.title
                            ch_data["status"] = "downloaded"
                    else:
                        with _tasks_lock:
                            task["errors"].append(f"章节不可获取: {ch.title}")
                            ch_data["status"] = "failed"
                            ch_data["error"] = "章节不可获取"
                    break

            _update_eta(time.time() - t0)
            with _tasks_lock:
                task["progress"] += 1

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_download_one, ch) for ch in task["chapters"]]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    _log.warning("future.result() failed in download task", exc_info=True)

        # 收尾：被取消时不覆盖状态
        if task["_cancel"].is_set():
            return

        if task["errors"]:
            task["status"] = "partial"
            task["error"] = f"部分章节下载失败 ({len(task['errors'])}/{task['total']})"
        else:
            task["status"] = "completed"
    except Exception as e:
        if task["_cancel"].is_set():
            return
        task["status"] = "failed"
        task["error"] = str(e)


def create_task(novel_id: str, chapters: list[dict], title: str,
                mode: str = "browser", variant: str | None = None,
                novel_url: str = "", platform: str = "fanqie") -> dict:
    task_id = str(uuid.uuid4())[:8]
    # 给每章加初始状态
    ch_data = [
        {"id": c["id"], "url": c.get("url", ""), "title": c.get("title", ""),
         "order": c.get("order", 0), "status": "pending"}
        for c in chapters
    ]
    task = {
        "task_id": task_id, "novel_id": novel_id, "title": title,
        "total": len(chapters), "progress": 0, "status": "downloading",
        "error": None, "errors": [], "current_title": "",
        "chapters": ch_data, "novel_url": novel_url,
        "_pause": threading.Event(),
        "_cancel": threading.Event(),
        "_mode": mode, "_variant": variant, "_platform": platform,
    }
    with _tasks_lock:
        _tasks[task_id] = task

    t = threading.Thread(target=_run_download, args=(task, mode, variant, platform),
                         daemon=True)
    t.start()
    return {"task_id": task_id, "total": len(chapters)}


def list_tasks() -> list[dict]:
    """返回任务列表，含章节级状态（仅给最近章节供前端渲染面板）。"""
    with _tasks_lock:
        result = []
        to_remove = []
        for t in _tasks.values():
            if t["status"] == "cancelled":
                # cancelled 任务只保留 10 秒，让前端确认
                cancelled_at = t.get("_cancelled_at", 0)
                if time.time() - cancelled_at > 10:
                    to_remove.append(t["task_id"])
                    continue
            # 精简章节：传全部但每章只保留 title/order/status/error
            chapters = [
                {"title": c.get("title", ""), "order": c.get("order", 0),
                 "status": c.get("status", "pending"), "error": c.get("error")}
                for c in t.get("chapters", [])
            ]
            result.append({
                "task_id": t["task_id"], "novel_id": t["novel_id"], "title": t["title"],
                "total": t["total"], "progress": t["progress"], "status": t["status"],
                "error": t.get("error"), "errors": t.get("errors", []),
                "current_title": t.get("current_title", ""),
                "eta": t.get("eta"),
                "chapters": chapters,
            })
        for tid in to_remove:
            _tasks.pop(tid, None)
        return result


def get_task(task_id: str) -> dict | None:
    return _tasks.get(task_id)


def pause_task(task_id: str) -> bool:
    task = _tasks.get(task_id)
    if task and task.get("_pause") and task["status"] in ("downloading",):
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
        task["_cancel"].clear()
        task["status"] = "downloading"
        task["error"] = None
        task["errors"] = []
        task["progress"] = 0
        for c in task["chapters"]:
            c["status"] = "pending"
        t = threading.Thread(
            target=_run_download,
            args=(task, task.get("_mode", "browser"), task.get("_variant"),
                  task.get("_platform", "fanqie")),
            daemon=True,
        )
        t.start()
        return True
    return False


def delete_task(task_id: str) -> bool:
    """真正取消下载：设 _cancel 标志 + status=cancelled，后台线程检测到后停止。"""
    with _tasks_lock:
        task = _tasks.get(task_id)
        if not task:
            return False
        task["_cancel"].set()
        task["status"] = "cancelled"
        task["_cancelled_at"] = time.time()
        # 唤醒可能被暂停的 worker
        if task.get("_pause") and task["_pause"].is_set():
            task["_pause"].clear()
        return True
