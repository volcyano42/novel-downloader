import asyncio
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


def _browser_engine(monkeypatch):
    # 避免真实启动 Chromium：monkeypatch _init_browser
    import novelbase.core.engine as eng
    monkeypatch.setattr(eng.BrowserEngine, "_init_browser", lambda self: None)
    from novelbase.core.options import BrowserOptions
    return eng.BrowserEngine(BrowserOptions(delay=(0, 0), headless=True))


def test_browser_engine_has_async_methods(monkeypatch):
    engine = _browser_engine(monkeypatch)
    assert asyncio.iscoroutinefunction(engine.async_fetch_text)
    assert asyncio.iscoroutinefunction(engine.async_fetch_json)


def test_browser_engine_async_delegates_to_sync(monkeypatch):
    engine = _browser_engine(monkeypatch)
    calls = []

    def fake_fetch_text(url, skip_delay=False, encoding=None, **kwargs):
        calls.append(url)
        return "<html>ok</html>"

    monkeypatch.setattr(engine, "fetch_text", fake_fetch_text)
    result = asyncio.run(engine.async_fetch_text("http://x", skip_delay=True))
    assert result == "<html>ok</html>"
    assert calls == ["http://x"]


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
    # close 后 AsyncClient 应已关闭
    assert engine._async_client.is_closed


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

