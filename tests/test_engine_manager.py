"""engine_manager 缓存（按 source_name + mode）与并发安全测试。"""
import threading
import time

from backend.services import engine_manager as em


def test_get_cached_engine_concurrent_single_create(monkeypatch):
    """并发调用 get_cached_engine 同一 key，只创建一个 engine（无竞态双创建）。"""
    em._engine_cache.clear()

    created = []
    count_lock = threading.Lock()

    def fake_create(source_name, mode="browser"):
        time.sleep(0.05)  # 制造竞态窗口：无锁时多线程都会通过 check 进入 create
        with count_lock:
            created.append((source_name, mode))
        return object()  # 假 engine

    monkeypatch.setattr(em, "create_engine_for_request", fake_create)

    results = []

    def worker():
        results.append(em.get_cached_engine("fanqie-browser-default", "browser"))

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
    key = em._fingerprint("92xs-requests-default", "requests")
    em._engine_cache[key] = fake

    created = []

    def fake_create(*a, **kw):
        created.append(1)
        return object()

    monkeypatch.setattr(em, "create_engine_for_request", fake_create)

    result = em.get_cached_engine("92xs-requests-default", "requests")
    assert result is fake
    assert len(created) == 0  # 缓存命中，不触发创建
    em._engine_cache.clear()


def test_get_cached_engine_by_source(monkeypatch):
    """缓存键 = (source_name, mode)：同一书源同一 mode 复用同一 engine。"""
    from backend.services import engine_manager as em
    em._engine_cache.clear()
    created = []

    def fake_create(source_name, mode="browser"):
        created.append((source_name, mode))
        return object()

    monkeypatch.setattr(em, "create_engine_for_request", fake_create)
    e1 = em.get_cached_engine("fanqie-api-rain", "api")
    e2 = em.get_cached_engine("fanqie-api-rain", "api")
    assert e1 is e2 and created == [("fanqie-api-rain", "api")]
    em._engine_cache.clear()


def test_fingerprint_source_and_mode():
    """同一书源不同 mode → 不同缓存键（unknown 书源走默认分支也能区分）。"""
    from backend.services import engine_manager as em
    assert em._fingerprint("a-x-default", "requests") != em._fingerprint("a-x-default", "browser")
