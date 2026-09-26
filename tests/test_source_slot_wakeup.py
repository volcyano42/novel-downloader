"""回归：书源额度「释放即唤醒」——单源额度 1 时吞吐 ≈ N×单章耗时，不被检查点钐。

背景：定时/退避轮询在「单请求耗时 < 检查间隔」时会空转 —— 一批协程在同一时基上
同步退避，醒来时刻收敛为稀疏检查点（如 ~0.5s 一个），额度在两次检查之间空转，把
有效吞吐钐到 ~1/间隔 章/s（默认 concurrency=1 时约 2 章/s）。改为「释放即唤醒」后，
等待者应在额度释放后毫秒级接手，吞吐回到 ≈ 1/单请求耗时。

`_source_active` / 唤醒队列是模块级状态，测试前后清理，避免污染其它用例。
"""
import asyncio
import time
from unittest.mock import MagicMock

import pytest

from backend.services import task_manager as tm


@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch):
    tm._tasks.clear()
    tm._running_tasks.clear()
    tm._source_active.clear()
    monkeypatch.setattr(tm, "_max_workers", lambda: 4)
    monkeypatch.setattr(tm, "_max_workers_cache", None)
    monkeypatch.setattr(tm, "source_concurrency", lambda name: 1)
    monkeypatch.setattr(tm, "set_novel_source", lambda *a, **k: None)
    yield
    tm._tasks.clear()
    tm._running_tasks.clear()
    tm._source_active.clear()


def _install(monkeypatch, stats: dict, speed: float):
    """fake resolve_chapter：每章耗时 speed，记录在飞请求数与峰值。"""
    engine = MagicMock()
    store = MagicMock()

    async def fake_resolve_chapter(ch, source_name, engines, **kw):
        stats["inflight"] += 1
        stats["peak"] = max(stats["peak"], stats["inflight"])
        await asyncio.sleep(speed)
        stats["inflight"] -= 1
        ch.content = "内容"
        ch.count = 10
        return ch

    monkeypatch.setattr("novelbase.resolve_chapter", fake_resolve_chapter)
    monkeypatch.setattr("novelbase.core.storage.create_storage", lambda opts: store)
    monkeypatch.setattr(tm, "get_cached_engine", lambda *a, **kw: engine)


def _chapters(n: int) -> list[dict]:
    return [{"id": f"c{i}", "url": f"http://x/{i}", "title": f"章{i}", "order": i}
            for i in range(1, n + 1)]


def test_release_wakes_waiter_throughput(monkeypatch):
    """额度=1、10 章、每章 0.05s：总耗时应 ≈0.5s（理想），而非被检查点钐成 ~N×0.5s。

    这是「释放即唤醒」的核心证据：有竞争时释放后毫秒级接手，无检查点空转。
    """
    n, speed = 10, 0.05
    stats = {"inflight": 0, "peak": 0}
    _install(monkeypatch, stats, speed)
    chapters = _chapters(n)

    async def _run():
        t0 = time.monotonic()
        r = tm.create_task("n1", chapters, "one", source_name="fast-src")
        t = tm._tasks[r["task_id"]]
        for _ in range(4000):
            if t["status"] in ("completed", "failed", "partial"):
                break
            await asyncio.sleep(0.005)
        return time.monotonic() - t0, t

    elapsed, t = asyncio.run(_run())

    assert t["status"] == "completed", t
    # 额度未被破坏：峰值仍为 1
    assert stats["peak"] == 1, stats
    assert tm._source_active == {}, tm._source_active
    # 无空转：理想 N×speed=0.5s；给足调度余量到 <1.0s。
    # 被 ~0.5s 检查点钐会退化成 ~N×0.5s=5s，远超阈值。
    assert elapsed < 1.0, (
        f"吞吐被检查点钐：elapsed={elapsed:.3f}s（期望 ≈{n*speed:.1f}s，上限 1.0s）")


def test_cancel_perceived_while_waiting_slot(monkeypatch):
    """额度=1、在飞章节未结束时取消：等待额度的协程应在 ≤0.5s 内被感知并退出。

    等待额度改事件驱动后，感知取消不再依赖短轮询，而靠 `_SOURCE_WAIT_TIMEOUT`（0.2s）
    超时或 release 唤醒；本测试确认取消延迟仍远小于 0.5s（不因改法回退）。
    """
    n, speed = 3, 0.15
    stats = {"inflight": 0, "peak": 0}
    _install(monkeypatch, stats, speed)
    chapters = _chapters(n)

    async def _run():
        r = tm.create_task("n1", chapters, "one", source_name="c-src")
        for _ in range(400):
            if stats["inflight"] >= 1:
                break
            await asyncio.sleep(0.005)
        await asyncio.sleep(0.02)              # 让第 2、3 章登记等待额度
        t0 = time.monotonic()
        assert tm.delete_task(r["task_id"]) is True
        for _ in range(400):
            if tm._source_active == {} and r["task_id"] not in tm._running_tasks:
                break
            await asyncio.sleep(0.005)
        return time.monotonic() - t0

    elapsed = asyncio.run(_run())
    assert tm._source_active == {}, tm._source_active
    assert elapsed < 0.5, f"取消感知过慢：{elapsed:.3f}s（应 ≤0.5s）"
