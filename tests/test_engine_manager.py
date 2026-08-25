"""engine_manager 缓存并发安全测试。"""
import threading
import time

from backend.services import engine_manager as em


def test_get_cached_engine_concurrent_single_create(monkeypatch):
    """并发调用 get_cached_engine 同一 key，只创建一个 engine（无竞态双创建）。"""
    em._engine_cache.clear()

    created = []
    count_lock = threading.Lock()

    def fake_create(platform, mode="browser", variant=None):
        time.sleep(0.05)  # 制造竞态窗口：无锁时多线程都会通过 check 进入 create
        with count_lock:
            created.append((platform, mode))
        return object()  # 假 engine

    monkeypatch.setattr(em, "create_engine_for_request", fake_create)

    results = []

    def worker():
        results.append(em.get_cached_engine("fanqie", "requests"))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(created) == 1, f"应只创建一次，实际 {len(created)} 次"
    assert all(r is results[0] for r in results), "所有线程应拿到同一 engine 实例"
    em._engine_cache.clear()


def test_get_cached_engine_returns_cached(monkeypatch):
    """缓存命中后不再创建，直接返回已有实例。"""
    em._engine_cache.clear()

    fake = object()
    # 预置缓存
    key = em._fingerprint("fanqie", "requests")
    em._engine_cache[key] = fake

    created = []

    def fake_create(*a, **kw):
        created.append(1)
        return object()

    monkeypatch.setattr(em, "create_engine_for_request", fake_create)

    result = em.get_cached_engine("fanqie", "requests")
    assert result is fake
    assert len(created) == 0  # 缓存命中，不触发创建
    em._engine_cache.clear()


def test_build_options_passes_auto_reconnect():
    from backend.services.engine_manager import _build_options
    from backend.schemas.engine import BrowserOptionsData
    b = BrowserOptionsData(auto_reconnect=True)
    opts = _build_options("browser", browser=b)
    assert opts.browser.auto_reconnect is True
