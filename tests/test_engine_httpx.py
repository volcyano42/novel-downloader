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
