"""任务级排队：`max_workers` 作为「同时运行的任务数」上限。

- 超额任务停在 `queued`，第一个完成后拿到额度转 `downloading`
- 排队中被删除 → `cancelled` 且协程不进入下载
- 任务槽在任务结束（无论成败）后释放

轮询式任务槽：`_running_tasks` 是模块级集合，测试前后必须清理，避免污染其它用例。
"""
import asyncio
from unittest.mock import MagicMock

import pytest

from backend.services import task_manager as tm


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch):
    """隔离模块级并发状态，并把任务上限钉死为 1、书源额度钉死为 1。"""
    tm._tasks.clear()
    tm._running_tasks.clear()
    tm._source_active.clear()
    monkeypatch.setattr(tm, "_max_workers", lambda: 1)
    monkeypatch.setattr(tm, "_max_workers_cache", None)
    monkeypatch.setattr(tm, "source_concurrency", lambda name: 1)
    monkeypatch.setattr(tm, "set_novel_source", lambda *a, **k: None)
    yield
    tm._tasks.clear()
    tm._running_tasks.clear()
    tm._source_active.clear()


def _install(monkeypatch, speed: float = 0.15, error: Exception | None = None):
    """把书源/引擎/存储替换为异步 mock；resolve_chapter 每章耗时 speed。

    `error` 非空时 resolve_chapter 每章抛该异常（用于验证异常路径的额度释放）。
    """
    from novelbase.models.novel import Novel

    engine = MagicMock()
    store = MagicMock()

    async def fake_resolve_meta(url, source_name, engines, **kw):
        return Novel(title="测试", url=url, id="n1", serial=0,
                     author="", description="")

    async def fake_resolve_chapter(ch, source_name, engines, **kw):
        await asyncio.sleep(speed)
        if error is not None:
            raise error
        ch.content = "内容"
        ch.count = 10
        return ch

    monkeypatch.setattr("novelbase.resolve_meta", fake_resolve_meta)
    monkeypatch.setattr("novelbase.resolve_chapter", fake_resolve_chapter)
    monkeypatch.setattr("novelbase.core.storage.create_storage", lambda opts: store)
    monkeypatch.setattr(tm, "get_cached_engine", lambda *a, **kw: engine)


def _chapters(n: int) -> list[dict]:
    return [{"id": f"c{i}", "url": f"http://x/{i}", "title": f"章{i}", "order": i}
            for i in range(1, n + 1)]


async def _wait_for(pred, tries: int = 600, interval: float = 0.01):
    for _ in range(tries):
        if pred():
            return True
        await asyncio.sleep(interval)
    return False


def test_second_task_queued_until_first_finishes(monkeypatch):
    """max_workers=1：第二个任务停在 queued，第一个完成后才转 downloading。"""
    _install(monkeypatch, speed=0.15)
    chapters = _chapters(2)

    async def _run():
        r1 = tm.create_task("n1", chapters, "one", source_name="92xs-requests-default")
        t1 = tm._tasks[r1["task_id"]]
        assert await _wait_for(lambda: t1["status"] == "downloading"), t1
        assert t1["task_id"] in tm._running_tasks

        r2 = tm.create_task("n2", chapters, "two", source_name="92xs-requests-default")
        t2 = tm._tasks[r2["task_id"]]
        # 超额任务：初始即 queued，且未占任务槽
        assert t2["status"] == "queued", t2
        assert t2["task_id"] not in tm._running_tasks

        # 第一个任务完成前，第二个保持 queued
        await asyncio.sleep(0.1)
        assert t2["status"] == "queued", t2
        assert t1["status"] == "downloading", t1

        # 第一个完成后 → 第二个拿到额度转 downloading
        assert await _wait_for(lambda: t1["status"] == "completed"), t1
        assert await _wait_for(lambda: t2["status"] == "downloading"), t2

        # 收尾：第二个也完成，任务槽全部释放
        assert await _wait_for(lambda: t2["status"] == "completed"), t2
        assert tm._running_tasks == set()

    asyncio.run(_run())


def test_queued_task_delete_cancels_without_downloading(monkeypatch):
    """排队中删除 → cancelled 且不进入下载（章节保持 pending）。"""
    _install(monkeypatch, speed=0.15)
    chapters = _chapters(2)

    async def _run():
        r1 = tm.create_task("n1", chapters, "one", source_name="92xs-requests-default")
        t1 = tm._tasks[r1["task_id"]]
        assert await _wait_for(lambda: t1["status"] == "downloading"), t1

        r2 = tm.create_task("n2", chapters, "two", source_name="92xs-requests-default")
        t2 = tm._tasks[r2["task_id"]]
        assert t2["status"] == "queued"
        assert tm.delete_task(r2["task_id"]) is True
        assert t2["status"] == "cancelled"

        # 等第一个任务完成（释放槽位）+ 足够时间让第二个协程观察到取消
        assert await _wait_for(lambda: t1["status"] == "completed"), t1
        await asyncio.sleep(0.3)

        assert t2["status"] == "cancelled", t2
        assert all(c["status"] == "pending" for c in t2["chapters"]), t2["chapters"]
        assert t2["task_id"] not in tm._running_tasks
        assert tm._source_active == {}, tm._source_active

    asyncio.run(_run())


def test_pause_queued_task_not_reserving_slot(monkeypatch):
    """排队中暂停：不占任务槽（不堵队列），保持 queued；resume 后才转 downloading。"""
    _install(monkeypatch, speed=0.15)
    chapters = _chapters(2)

    async def _run():
        r1 = tm.create_task("n1", chapters, "one", source_name="92xs-requests-default")
        t1 = tm._tasks[r1["task_id"]]
        assert await _wait_for(lambda: t1["status"] == "downloading"), t1

        r2 = tm.create_task("n2", chapters, "two", source_name="92xs-requests-default")
        t2 = tm._tasks[r2["task_id"]]
        assert t2["status"] == "queued"
        assert tm.pause_task(r2["task_id"]) is True
        assert t2["_pause"].is_set()
        assert t2["status"] == "queued"
        # 暂停的排队任务不得占任务槽（否则 max_workers=1 时堵死队列）
        assert t2["task_id"] not in tm._running_tasks

        # 即使第一个任务完成释放了唯一的槽，暂停中的第二个仍不抢（保持 queued）
        assert await _wait_for(lambda: t1["status"] == "completed"), t1
        await asyncio.sleep(0.3)
        assert t2["status"] == "queued", t2
        assert t2["task_id"] not in tm._running_tasks

        # resume 后才去抢额度并转 downloading
        assert tm.resume_task(r2["task_id"]) is True
        assert await _wait_for(lambda: t2["status"] == "downloading"), t2
        assert await _wait_for(lambda: t2["status"] == "completed"), t2
        assert tm._running_tasks == set()

    asyncio.run(_run())


def test_slots_released_on_chapter_exception(monkeypatch):
    """异常路径：书源函数抛错后，任务槽与书源额度都回到零（额度不泄漏）。"""
    _install(monkeypatch, speed=0.01, error=RuntimeError("boom"))
    chapters = _chapters(3)

    async def _run():
        r = tm.create_task("n1", chapters, "one", source_name="92xs-requests-default")
        t = tm._tasks[r["task_id"]]
        assert await _wait_for(
            lambda: t["status"] in ("completed", "failed", "partial")), t
        assert t["status"] == "partial", t      # 每章失败 → errors 非空
        # 协程收尾：两类槽位都必须释放
        assert await _wait_for(lambda: t["task_id"] not in tm._running_tasks
                               and tm._source_active == {}), (t, tm._source_active)

    asyncio.run(_run())
    assert tm._running_tasks == set()
    assert tm._source_active == {}


def test_slots_released_on_cancel_during_download(monkeypatch):
    """取消路径（下载中）：取消后任务槽与书源额度都回到零。"""
    _install(monkeypatch, speed=0.2)
    chapters = _chapters(3)

    async def _run():
        r = tm.create_task("n1", chapters, "one", source_name="92xs-requests-default")
        t = tm._tasks[r["task_id"]]
        assert await _wait_for(lambda: t["status"] == "downloading"), t
        await asyncio.sleep(0.05)               # 让至少一章进入 resolve_chapter
        assert tm.delete_task(r["task_id"]) is True
        assert t["status"] == "cancelled"
        # 在飞章节跑完 + 协程观察取消后退出 → 两类槽位清零
        assert await _wait_for(lambda: t["task_id"] not in tm._running_tasks
                               and tm._source_active == {}), (t, tm._source_active)

    asyncio.run(_run())
    assert tm._running_tasks == set()
    assert tm._source_active == {}
