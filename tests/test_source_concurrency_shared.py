"""书源级并发额度：跨任务共享，同一书源同时最多 `concurrency` 个请求在飞。

- 同一书源、额度 1：两个任务不会同时进入请求（spy 记录 enter/exit，peak == 1）
- 不同书源、额度 2：可并行（peak >= 2）

`_source_active` 是模块级计数，测试前后必须清理，避免污染其它用例。
"""
import asyncio
from unittest.mock import MagicMock

import pytest

from backend.services import task_manager as tm


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch):
    tm._tasks.clear()
    tm._running_tasks.clear()
    tm._source_active.clear()
    # 任务级额度放宽到 2，使两个任务能同时运行（否则测不出书源共享）
    monkeypatch.setattr(tm, "_max_workers", lambda: 2)
    monkeypatch.setattr(tm, "set_novel_source", lambda *a, **k: None)
    yield
    tm._tasks.clear()
    tm._running_tasks.clear()
    tm._source_active.clear()


def _install(monkeypatch, stats: dict, speed: float = 0.05):
    """spy 版 resolve_chapter：记录在飞请求数与峰值。"""
    from novelbase.models.novel import Novel

    engine = MagicMock()
    store = MagicMock()

    async def fake_resolve_meta(url, source_name, engines, **kw):
        return Novel(title="测试", url=url, id="n1", serial=0,
                     author="", description="")

    async def fake_resolve_chapter(ch, source_name, engines, **kw):
        stats["inflight"] += 1
        stats["peak"] = max(stats["peak"], stats["inflight"])
        stats["events"].append(("enter", ch.title))
        await asyncio.sleep(speed)
        stats["inflight"] -= 1
        stats["events"].append(("exit", ch.title))
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


async def _wait_for(pred, tries: int = 800, interval: float = 0.01):
    for _ in range(tries):
        if pred():
            return True
        await asyncio.sleep(interval)
    return False


def test_same_source_never_overlaps(monkeypatch):
    """同一书源、额度 1：两个任务共享额度，任意时刻至多 1 个请求在飞。"""
    monkeypatch.setattr(tm, "source_concurrency", lambda name: 1)
    stats = {"inflight": 0, "peak": 0, "events": []}
    _install(monkeypatch, stats, speed=0.05)
    chapters = _chapters(3)

    async def _run():
        r1 = tm.create_task("n1", chapters, "one", source_name="shared-src")
        r2 = tm.create_task("n2", chapters, "two", source_name="shared-src")
        t1, t2 = tm._tasks[r1["task_id"]], tm._tasks[r2["task_id"]]
        assert await _wait_for(
            lambda: t1["status"] in ("completed", "failed", "partial")
            and t2["status"] in ("completed", "failed", "partial")), (t1, t2)
        assert t1["status"] == "completed" and t2["status"] == "completed"

    asyncio.run(_run())

    assert stats["peak"] == 1, stats
    # enter/exit 严格交替（无重叠）
    assert [k for k, _ in stats["events"]] == ["enter", "exit"] * 6, stats["events"]
    assert tm._source_active == {}


def test_different_sources_run_in_parallel(monkeypatch):
    """不同书源、各自额度 2：两个任务的请求可同时在飞（peak >= 2）。"""
    monkeypatch.setattr(tm, "source_concurrency", lambda name: 2)
    stats = {"inflight": 0, "peak": 0, "events": []}
    _install(monkeypatch, stats, speed=0.1)
    chapters = _chapters(3)

    async def _run():
        r1 = tm.create_task("n1", chapters, "one", source_name="src-A")
        r2 = tm.create_task("n2", chapters, "two", source_name="src-B")
        t1, t2 = tm._tasks[r1["task_id"]], tm._tasks[r2["task_id"]]
        assert await _wait_for(
            lambda: t1["status"] in ("completed", "failed", "partial")
            and t2["status"] in ("completed", "failed", "partial")), (t1, t2)
        assert t1["status"] == "completed" and t2["status"] == "completed"

    asyncio.run(_run())

    assert stats["peak"] >= 2, stats
    assert tm._source_active == {}
