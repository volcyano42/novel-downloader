import httpx

from novelbase import create_engine, Options


def _requests_engine():
    opts = Options().set_mode("requests").set_requests_options(
        headers={"User-Agent": "test"},
        timeout=5,
        retry_times=1,
        delay=(0, 0),
    )
    return create_engine(opts)


def test_requests_engine_uses_httpx_client():
    engine = _requests_engine()
    assert isinstance(engine._client, httpx.Client)
    engine.close()


def test_requests_engine_fetch_text(monkeypatch):
    engine = _requests_engine()

    class FakeResp:
        content = "测试内容".encode("utf-8")
        encoding = "utf-8"

    def fake_get(url):
        return FakeResp()

    monkeypatch.setattr(engine._client, "get", fake_get)
    assert engine.fetch_text("http://x") == "测试内容"
    engine.close()


def test_requests_engine_has_async_methods():
    engine = _requests_engine()
    assert asyncio.iscoroutinefunction(engine.async_fetch_text)
    assert asyncio.iscoroutinefunction(engine.async_fetch_json)
    engine.close()


def test_requests_engine_async_fetch_text(monkeypatch):
    engine = _requests_engine()

    async def fake_get(url):
        class R:
            content = "异步内容".encode("utf-8")
            encoding = "utf-8"
        return R()

    monkeypatch.setattr(engine._get_async_client(), "get", fake_get)
    result = asyncio.run(engine.async_fetch_text("http://x", skip_delay=True))
    assert result == "异步内容"
    engine.close()


def test_requests_engine_async_fetch_text_post(monkeypatch):
    """RequestsEngine async_fetch_text 支持 post_data（POST 请求）。"""
    engine = _requests_engine()
    calls = {}

    async def fake_post(url, data=None):
        calls["url"] = url
        calls["data"] = data

        class R:
            content = "POST 响应".encode("utf-8")
        return R()

    monkeypatch.setattr(engine._get_async_client(), "post", fake_post)
    result = asyncio.run(engine.async_fetch_text(
        "http://x", post_data={"k": "v"}, skip_delay=True,
    ))
    assert result == "POST 响应"
    assert calls["url"] == "http://x"
    assert calls["data"] == {"k": "v"}
    engine.close()


def test_requests_engine_fetch_text_post(monkeypatch):
    """RequestsEngine 同步 fetch_text 也支持 post_data。"""
    engine = _requests_engine()
    calls = {}

    def fake_post(url, data=None):
        calls["data"] = data

        class R:
            content = "POST 同步".encode("utf-8")
        return R()

    monkeypatch.setattr(engine._client, "post", fake_post)
    result = engine.fetch_text("http://x", post_data={"a": "b"}, skip_delay=True)
    assert result == "POST 同步"
    assert calls["data"] == {"a": "b"}
    engine.close()


def _api_engine():
    opts = Options().set_mode("api").set_api_options(
        name="test", key="k", timeout=5, retry_times=1, delay=(0, 0),
        params={"token": "abc"},
    )
    return create_engine(opts)


def test_api_engine_has_async_methods():
    engine = _api_engine()
    assert asyncio.iscoroutinefunction(engine.async_fetch_text)
    assert asyncio.iscoroutinefunction(engine.async_fetch_json)
    engine.close()


def test_api_engine_async_fetch_json_post(monkeypatch):
    engine = _api_engine()

    async def fake_post(url, data=None):
        class R:
            def json(self):
                return {"ok": True, "data": data}
        return R()

    monkeypatch.setattr(engine._get_async_client(), "post", fake_post)
    result = asyncio.run(engine.async_fetch_json("http://x", skip_delay=True, post_data={"id": "1"}))
    assert result["ok"] is True
    assert result["data"]["token"] == "abc"  # params 合并进 post_data
    engine.close()


class FakePlaywright:
    """mock playwright.async_api.async_playwright 的最小替身。

    FakePW 既是 context manager（支持 async with）又是 Playwright 实例（有 chromium）。
    """

    def __init__(self, monkeypatch):
        self.calls = []
        self._install(monkeypatch)

    def _install(self, monkeypatch):
        fake = self

        class FakePage:
            async def goto(self, url, timeout=None):
                fake.calls.append(("goto", url))
            async def content(self):
                fake.calls.append(("content",))
                return "<html>ok</html>"
            async def close(self):
                fake.calls.append(("page_close",))

        class FakeContext:
            def __init__(self):
                self.browser = FakeBrowser()
            async def new_page(self):
                fake.calls.append(("new_page",))
                return FakePage()
            async def close(self):
                fake.calls.append(("context_close",))

        class FakeBrowser:
            async def new_context(self, viewport=None):
                fake.calls.append(("new_context", viewport))
                return FakeContext()
            async def new_page(self):
                fake.calls.append(("new_page",))
                return FakePage()
            async def close(self):
                fake.calls.append(("browser_close",))

        class FakeChromium:
            async def launch(self, headless=True, args=None):
                fake.calls.append(("launch", headless))
                return FakeBrowser()
            async def launch_persistent_context(
                self, user_data_dir, headless=True, args=None, **kwargs
            ):
                fake.calls.append(("launch_persistent_context", user_data_dir))
                return FakeContext()

        class FakePW:
            def __init__(self):
                self.chromium = FakeChromium()
            async def start(self):
                return self
            async def stop(self):
                fake.calls.append(("pw_stop",))
            async def __aenter__(self):
                return self
            async def __aexit__(self, *exc):
                fake.calls.append(("pw_stop",))

        import novelbase.core.engine as eng
        monkeypatch.setattr(eng, "_async_playwright", lambda: FakePW())


def _browser_engine():
    from novelbase.core.options import BrowserOptions
    from novelbase.core.engine import BrowserEngine
    return BrowserEngine(BrowserOptions(delay=(0, 0), headless=True))


def test_browser_engine_lazy_init(monkeypatch):
    """__init__ 不启动浏览器（懒启动），_browser 初始为 None。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()
    assert engine._browser is None
    assert fake.calls == []


def test_browser_engine_async_fetch_text_is_native(monkeypatch):
    """async_fetch_text 直接 await Playwright（不再委托同步 fetch_text）。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()
    result = asyncio.run(engine.async_fetch_text("http://x", skip_delay=True))
    assert result == "<html>ok</html>"
    # 懒启动 + goto + content 都被真实调用
    assert ("launch", True) in fake.calls
    assert ("new_context", None) in fake.calls  # 无 viewport 时显式参数为 None
    assert ("new_page",) in fake.calls
    assert ("goto", "http://x") in fake.calls
    assert ("content",) in fake.calls


def test_browser_engine_sync_fetch_text_isolated_session(monkeypatch):
    """同步 fetch_text 用独立浏览器会话，不触碰懒启动的 self._browser。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()
    result = engine.fetch_text("http://sync", skip_delay=True)
    assert result == "<html>ok</html>"
    # 独立会话启停：browser 被 close，pw 被 stop
    assert ("browser_close",) in fake.calls
    assert ("pw_stop",) in fake.calls
    # 懒启动的 self._browser 仍为 None（未被触碰）
    assert engine._browser is None


def test_browser_engine_sync_fetch_text_raises_network_error_on_fail(monkeypatch):
    """同步 fetch_text 独立会话中 goto 失败后抛 NetworkError（retry/backoff 与 async 对齐）。"""
    from novelbase.core.options import BrowserOptions
    from novelbase.core.engine import BrowserEngine
    from novelbase.core.exceptions import NetworkError

    class FailingPage:
        async def goto(self, url, timeout=None):
            raise TimeoutError("goto timeout")

        async def content(self):
            return "<html>"

        async def close(self):
            pass

    class FailingBrowser:
        async def new_page(self):
            return FailingPage()

        async def close(self):
            pass

    class FailingChromium:
        async def launch(self, headless=True, args=None):
            return FailingBrowser()

    class FailingPW:
        def __init__(self):
            self.chromium = FailingChromium()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            pass

    import novelbase.core.engine as eng
    monkeypatch.setattr(eng, "_async_playwright", lambda: FailingPW())

    engine = BrowserEngine(BrowserOptions(
        delay=(0, 0), headless=True, retry_times=1, backoff_factor=0,
    ))
    try:
        engine.fetch_text("http://fail", skip_delay=True)
    except NetworkError:
        pass
    else:
        raise AssertionError("同步 fetch_text 在 goto 失败后应抛 NetworkError")


def test_browser_engine_new_page_async(monkeypatch):
    """new_page 是 async 方法，懒启动后返回 page。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()

    async def _run():
        page = await engine.new_page()
        return page
    page = asyncio.run(_run())
    assert page is not None
    assert ("new_page",) in fake.calls
    assert engine._browser is not None  # 懒启动完成


def test_browser_engine_user_data_dir_uses_persistent_context(monkeypatch):
    """user_data_dir 非空时走 launch_persistent_context，不调 launch/new_context。"""
    from novelbase.core.options import BrowserOptions
    from novelbase.core.engine import BrowserEngine
    fake = FakePlaywright(monkeypatch)
    engine = BrowserEngine(BrowserOptions(
        delay=(0, 0), headless=True, user_data_dir="C:/tmp/ud",
    ))
    result = asyncio.run(engine.async_fetch_text("http://x", skip_delay=True))
    assert result == "<html>ok</html>"
    assert ("launch_persistent_context", "C:/tmp/ud") in fake.calls
    assert not any(c[0] == "launch" for c in fake.calls)
    assert not any(c[0] == "new_context" for c in fake.calls)


def test_browser_engine_concurrent_lazy_init_launches_once(monkeypatch):
    """并发首次 async_fetch_text 只启动一次浏览器（_launch_lock double-check）。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()

    async def _run():
        return await asyncio.gather(
            engine.async_fetch_text("http://a", skip_delay=True),
            engine.async_fetch_text("http://b", skip_delay=True),
        )
    results = asyncio.run(_run())
    assert results == ["<html>ok</html>", "<html>ok</html>"]
    assert fake.calls.count(("launch", True)) == 1


def test_browser_engine_reuses_page_from_pool(monkeypatch):
    """连续两次 async_fetch_text 复用同一个 page（new_page 只调用一次，不 close）。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()

    async def _run():
        await engine.async_fetch_text("http://a", skip_delay=True)
        await engine.async_fetch_text("http://b", skip_delay=True)
    asyncio.run(_run())

    assert fake.calls.count(("new_page",)) == 1      # 第二次复用第一次的 page
    assert fake.calls.count(("page_close",)) == 0    # 复用不 close
    assert len(engine._idle_pages) == 1              # 池里有一个空闲 page


def test_browser_engine_lazy_creates_pages_when_pool_empty(monkeypatch):
    """池空则懒创建 page（无上限，与同步时代懒加载一致）；归还后复用。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()

    async def _run():
        await engine._ensure_browser()
        p1 = await engine._acquire_page()   # 池空 → 懒创建 page1
        p2 = await engine._acquire_page()   # 池空 → 懒创建 page2（无上限）
        assert p1 is not None and p2 is not None
        assert fake.calls.count(("new_page",)) == 2

        await engine._release_page(p1)
        await engine._release_page(p2)
        p3 = await engine._acquire_page()   # 池非空 → 复用，不新创建
        assert fake.calls.count(("new_page",)) == 2
    asyncio.run(_run())


def test_browser_engine_failed_fetch_closes_page_not_return(monkeypatch):
    """抓取失败：page 被 close 且不归还池（避免坏 page 污染后续复用）。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()

    async def fake_fail(page, url, skip_delay=False, **kwargs):
        # **kwargs 兼容 _do_fetch_text 传入的 abort_on_browser_close（测试替身不关心）
        raise RuntimeError("goto failed")

    monkeypatch.setattr(engine, "_fetch_with_page", fake_fail)

    async def _run():
        try:
            await engine.async_fetch_text("http://x", skip_delay=True)
        except RuntimeError:
            pass
    asyncio.run(_run())

    assert ("page_close",) in fake.calls   # 失败 page 被 close
    assert engine._idle_pages == []        # 不归还池


def test_browser_engine_aclose_awaits_shutdown(monkeypatch):
    """aclose() await 完成浏览器/驱动释放，且状态置 None（幂等）。"""
    fake = FakePlaywright(monkeypatch)
    engine = _browser_engine()

    async def _run():
        await engine.async_fetch_text("http://x", skip_delay=True)
        await engine.aclose()
        # 状态已置 None，可重复 aclose 不抛异常
        await engine.aclose()
    asyncio.run(_run())

    assert engine._browser is None
    assert engine._context is None
    assert engine._playwright is None
    # 懒启动 + 关闭：browser/context/pw 都被 await 关闭
    assert ("browser_close",) in fake.calls
    assert ("context_close",) in fake.calls
    assert ("pw_stop",) in fake.calls


def test_engine_base_has_abstract_async_methods():
    from novelbase.core.engine import Engine
    assert "async_fetch_text" in Engine.__abstractmethods__
    assert "async_fetch_json" in Engine.__abstractmethods__


def test_requests_engine_close_cleans_async_client():
    engine = _requests_engine()
    # 触发懒加载
    client = engine._get_async_client()
    assert client is not None
    assert engine._async_client is not None
    engine.close()
    # close 后 _async_client 置 None（幂等），且 client 已关闭（无泄漏）
    assert engine._async_client is None
    assert client.is_closed


def test_requests_engine_close_idempotent():
    """close 可重复调用：第二次 close 不抛异常，_async_client 保持 None。"""
    engine = _requests_engine()
    engine._get_async_client()
    engine.close()
    engine.close()  # 幂等，不抛异常
    assert engine._async_client is None


def test_requests_engine_close_inside_running_loop():
    """running loop 内调用 close：走 loop.create_task 分支，不抛异常。"""
    import asyncio

    async def _run():
        engine = _requests_engine()
        engine._get_async_client()
        engine.close()  # 此时有 running loop
        assert engine._async_client is None
        # 给后台 aclose 任务一点时间执行
        await asyncio.sleep(0.01)

    asyncio.run(_run())


def test_requests_engine_close_without_async_client():
    engine = _requests_engine()
    # 未触发 async client，close 不应报错
    assert engine._async_client is None
    engine.close()
    assert engine._async_client is None


import asyncio
import inspect

def test_engine_has_async_fetch_images_abstract():
    """Engine 基类声明 async_fetch_images 抽象方法。"""
    from novelbase.core.engine import Engine
    assert hasattr(Engine, "async_fetch_images")
    method = Engine.async_fetch_images
    assert inspect.iscoroutinefunction(method)
    # 抽象方法：直接实例化基类会失败（已由其他抽象方法保证）
    assert getattr(Engine.async_fetch_images, "__isabstractmethod__", False)


def _make_engine(mode: str):
    from novelbase.core.engine import create_engine
    from novelbase.core.options import Options
    opts = Options().set_mode(mode)
    if mode == "requests":
        opts.set_requests_options(headers={}, cookies={}, proxies={}, delay=[0, 0])
    elif mode == "api":
        opts.set_api_options(name="test", key="", delay=[0, 0])
    return create_engine(opts)


def test_requests_engine_async_fetch_images_success_and_failure(monkeypatch):
    """批量下载：成功项返回 bytes，失败项返回 b""。"""
    import httpx

    class FakeResponse:
        def __init__(self, content): self.content = content
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    class FakeAsyncClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url):
            if "fail" in url:
                raise httpx.HTTPError("boom")
            return FakeResponse(url.encode())

    monkeypatch.setattr("novelbase.core.engine.httpx.AsyncClient", FakeAsyncClient)
    engine = _make_engine("requests")
    result = asyncio.run(engine.async_fetch_images(["http://ok1", "http://fail", "http://ok2"]))
    assert result == [b"http://ok1", b"", b"http://ok2"]


def test_api_engine_async_fetch_images_success_and_failure(monkeypatch):
    """APIEngine 批量下载：成功项返回 bytes，失败项返回 b""。"""
    import httpx

    class FakeResponse:
        def __init__(self, content): self.content = content
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    class FakeAsyncClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url):
            if "fail" in url:
                raise httpx.HTTPError("boom")
            return FakeResponse(url.encode())

    monkeypatch.setattr("novelbase.core.engine.httpx.AsyncClient", FakeAsyncClient)
    engine = _make_engine("api")
    from novelbase.core.engine import APIEngine
    assert isinstance(engine, APIEngine)
    result = asyncio.run(engine.async_fetch_images(["http://ok1", "http://fail", "http://ok2"]))
    assert result == [b"http://ok1", b"", b"http://ok2"]


def test_browser_engine_async_fetch_images_uses_httpx_not_tab(monkeypatch):
    """BrowserEngine 图片下载用 httpx，不 new_tab / get_page。"""

    class FakeResponse:
        def __init__(self, content): self.content = content
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

    class FakeAsyncClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def get(self, url):
            return FakeResponse(url.encode())

    monkeypatch.setattr("novelbase.core.engine.httpx.AsyncClient", FakeAsyncClient)

    from novelbase.core.engine import BrowserEngine
    engine = BrowserEngine.__new__(BrowserEngine)  # 不触发 __init__（避免启动 Chromium）
    result = asyncio.run(engine.async_fetch_images(["http://a"]))
    assert result == [b"http://a"]

