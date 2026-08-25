"""task_manager 全 asyncio 化契约测试。

核心契约：
1. create_task 保持同步 def（被 async 路由调用），内部通过
   asyncio.get_running_loop() 拿到当前事件循环，再 loop.create_task 调度协程。
2. _run_download 是协程函数（async def），不再是 threading.Thread 目标。
3. 下载协程确实被调度到调用 create_task 的事件循环里执行。
4. 真实下载全流程（mock 书源）：并发限流 + resume(failed) 重启协程。
"""

import asyncio
from unittest.mock import MagicMock


def test_run_download_is_coroutine():
    """下载流程是协程函数（asyncio 原生，不再走 threading.Thread）。"""
    from backend.services import task_manager as tm
    assert asyncio.iscoroutinefunction(tm._run_download)


def test_create_task_returns_id_and_schedules_coroutine(monkeypatch):
    """create_task 同步返回 task_id，并在事件循环里调度下载协程。"""
    from backend.services import task_manager as tm
    tm._tasks.clear()

    async def _run():
        ran = asyncio.Event()

        async def _stub(task, mode, variant, platform):
            task["_stub_ran"] = True
            ran.set()

        monkeypatch.setattr(tm, "_run_download", _stub)
        tid = tm.create_task(
            "fanqie_1",
            [{"id": "c1", "url": "http://x", "title": "t", "order": 0}],
            "test", mode="requests",
        )
        assert tid  # 返回了 task_id
        assert tid["task_id"] in tm._tasks
        # 下载协程必须在当前事件循环中被调度并执行
        await asyncio.wait_for(ran.wait(), timeout=5)
        return tid

    tid = asyncio.run(_run())
    assert tm._tasks[tid["task_id"]]["_stub_ran"] is True


def _install_mocks(monkeypatch, chapters, speed: float = 0.01):
    """把书源/引擎/存储替换为异步 mock，返回并发统计容器。speed 为每章下载耗时。"""
    from backend.services import engine_manager
    from novelbase.models.novel import Novel

    engine = MagicMock()
    engine.mode = "requests"
    engine.name = "requests"

    stats = {"inflight": 0, "peak": 0}
    store = MagicMock()

    async def fake_resolve_meta(url, engine, **kw):
        return Novel(title="测试", url=url, id="fanqie_1", serial=0,
                     author="", description="", count=len(chapters))

    async def fake_resolve_chapter(ch, engine, **kw):
        stats["inflight"] += 1
        stats["peak"] = max(stats["peak"], stats["inflight"])
        await asyncio.sleep(speed)
        ch.content = "内容"
        ch.count = 10
        stats["inflight"] -= 1
        return ch

    monkeypatch.setattr("novelbase.resolve_meta", fake_resolve_meta)
    monkeypatch.setattr("novelbase.resolve_chapter", fake_resolve_chapter)
    monkeypatch.setattr("novelbase.core.downloader.resolve_meta", fake_resolve_meta)
    monkeypatch.setattr("novelbase.core.downloader.resolve_chapter", fake_resolve_chapter)
    monkeypatch.setattr("novelbase.core.storage.create_storage", lambda opts: store)
    monkeypatch.setattr(engine_manager, "get_cached_engine", lambda *a, **kw: engine)
    return stats


def _chapters(n: int) -> list[dict]:
    return [{"id": f"c{i}", "url": f"http://x/{i}", "title": f"章{i}", "order": i}
            for i in range(1, n + 1)]


def test_full_download_lifecycle(monkeypatch):
    """真实 _run_download 全流程：完成 + Semaphore 并发限流。"""
    from shared.config import load_config
    from backend.services import task_manager as tm

    chapters = _chapters(5)
    stats = _install_mocks(monkeypatch, chapters)
    max_workers = load_config().get("download", {}).get("max_workers", 3)
    tm._tasks.clear()

    async def _run():
        r = tm.create_task("fanqie_1", chapters, "测试", mode="requests")
        tid = r["task_id"]
        for _ in range(500):
            if tm._tasks[tid]["status"] in ("completed", "failed", "partial"):
                break
            await asyncio.sleep(0.01)
        t = tm._tasks[tid]
        assert t["status"] == "completed", t
        assert t["progress"] == t["total"] == 5, t
        assert stats["peak"] <= max(1, max_workers), stats["peak"]

    asyncio.run(_run())


def test_resume_failed_task_restarts_coroutine(monkeypatch):
    """resume_task 的 failed 分支：loop.create_task 重启下载协程，进度归零。"""
    from backend.services import task_manager as tm

    chapters = _chapters(3)
    _install_mocks(monkeypatch, chapters)
    tm._tasks.clear()

    async def _run():
        task = {
            "task_id": "t_resume", "novel_id": "fanqie_1", "title": "测试",
            "total": 3, "progress": 1, "status": "failed", "error": "x",
            "errors": ["x"], "current_title": "", "chapters": [
                {"id": c["id"], "url": c["url"], "title": c["title"], "order": c["order"],
                 "status": "failed"} for c in chapters],
            "novel_url": "", "_pause": asyncio.Event(), "_cancel": asyncio.Event(),
            "_mode": "requests", "_variant": None, "_platform": "fanqie",
        }
        tm._tasks["t_resume"] = task
        assert tm.resume_task("t_resume") is True
        assert task["status"] == "downloading" and task["progress"] == 0
        for _ in range(500):
            if task["status"] in ("completed", "failed", "partial"):
                break
            await asyncio.sleep(0.01)
        assert task["status"] == "completed", task
        assert task["progress"] == 3, task

    asyncio.run(_run())


def test_pause_freezes_progress_until_resume(monkeypatch):
    """暂停后进度冻结（wait() 反用修复）：点暂停任务停住，resume 后继续到完成。"""
    from backend.services import task_manager as tm

    chapters = _chapters(5)
    # speed=0.05：5 章约 0.1s 下完，sleep(0.02) 时稳定处于下载中，
    # 避免默认 speed=0.01 与 sleep(0.02) 临界竞态导致 pause 落在完成后
    _install_mocks(monkeypatch, chapters, speed=0.05)
    tm._tasks.clear()

    async def _run():
        r = tm.create_task("fanqie_1", chapters, "测试", mode="requests")
        tid = r["task_id"]
        t = tm._tasks[tid]
        await asyncio.sleep(0.02)  # 让部分章节开始
        assert tm.pause_task(tid) is True
        await asyncio.sleep(0.15)  # 等待暂停生效（优雅暂停：当前章跑完）
        frozen = t["progress"]
        assert t["status"] == "paused", t
        # 暂停期间进度不再增长
        await asyncio.sleep(0.2)
        assert t["progress"] == frozen, f"暂停期间 progress 从 {frozen} 增长到 {t['progress']}"
        assert t["status"] == "paused"
        # resume 后继续到完成
        assert tm.resume_task(tid) is True
        for _ in range(500):
            if t["status"] in ("completed", "failed", "partial"):
                break
            await asyncio.sleep(0.01)
        assert t["status"] == "completed", t
        assert t["progress"] == 5, t

    asyncio.run(_run())


def test_pause_at_tail_does_not_skip(monkeypatch):
    """尾部暂停不跳过（收尾检查点）：章节全下载完但暂停中，任务停在 paused 而非 completed。"""
    from backend.services import task_manager as tm

    chapters = _chapters(3)
    _install_mocks(monkeypatch, chapters, speed=0.05)  # 每章 0.05s，时序可控
    tm._tasks.clear()

    async def _run():
        r = tm.create_task("fanqie_1", chapters, "测试", mode="requests")
        tid = r["task_id"]
        t = tm._tasks[tid]
        await asyncio.sleep(0.02)  # 3 章都已开始下载（还没完成）
        assert tm.pause_task(tid) is True  # 此时 status == downloading
        # 等 3 章都下载完（优雅暂停：当前章跑完）
        await asyncio.sleep(0.12)
        # 关键：章节虽全下载完，但暂停中 → 停在 paused 而非 completed
        assert t["status"] == "paused", t
        assert t["progress"] == 3, t  # 3 章都下载完了
        # resume 后才 completed
        assert tm.resume_task(tid) is True
        for _ in range(500):
            if t["status"] in ("completed", "failed", "partial"):
                break
            await asyncio.sleep(0.01)
        assert t["status"] == "completed", t

    asyncio.run(_run())
