"""BrowserEngine.auto_reconnect 重建逻辑测试。"""
import asyncio

import pytest

from novelbase.core.engine import BrowserEngine
from novelbase.core.exceptions import NetworkError
from novelbase.core.options import BrowserOptions


class FakePlaywright:
    """mock playwright：首轮 goto 抛浏览器失效异常，重建后成功。

    - fail_first_batch=True：下一次 goto 抛「TargetClosedError」异常一次，随后恢复成功。
    - fail_always=True：每次 goto 都抛（用于验证不重建时最终 NetworkError）。
    """

    def __init__(self, monkeypatch):
        self.calls = []
        self.launch_count = 0
        self.fail_first_batch = False
        self.fail_always = False
        self._install(monkeypatch)

    def _install(self, monkeypatch):
        fake = self

        class FakePage:
            async def goto(self, url, timeout=None):
                fake.calls.append(("goto", url))
                if fake.fail_first_batch or fake.fail_always:
                    if not fake.fail_always:
                        fake.fail_first_batch = False
                    raise RuntimeError("TargetClosedError: browser has been closed")
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
                fake.launch_count += 1
                fake.calls.append(("launch", headless))
                return FakeBrowser()

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


def _engine(auto_reconnect: bool):
    return BrowserEngine(BrowserOptions(delay=(0, 0), headless=True,
                                        retry_times=3, backoff_factor=0,
                                        auto_reconnect=auto_reconnect))


def test_reconnect_recovers_after_browser_closed(monkeypatch):
    """auto_reconnect=True：浏览器失效 → 重建 → 成功（launch 两次）。"""
    fake = FakePlaywright(monkeypatch)
    fake.fail_first_batch = True
    engine = _engine(auto_reconnect=True)
    result = asyncio.run(engine.async_fetch_text("http://x", skip_delay=True))
    assert result == "<html>ok</html>"
    assert fake.launch_count == 2, f"应重建一次，实际 launch {fake.launch_count} 次"
    assert any(c[0] == "browser_close" for c in fake.calls)  # 旧浏览器被清理
    engine.close()


def test_no_reconnect_when_disabled(monkeypatch):
    """auto_reconnect=False：不重建，最终 NetworkError。"""
    fake = FakePlaywright(monkeypatch)
    fake.fail_always = True
    engine = _engine(auto_reconnect=False)
    with pytest.raises(NetworkError):
        asyncio.run(engine.async_fetch_text("http://x", skip_delay=True))
    assert fake.launch_count == 1, "auto_reconnect=False 不应重建"
    engine.close()


def test_concurrent_reconnects_are_safe(monkeypatch):
    """两个任务并发触发重建：锁保护下最终引擎可用，不出现双重破坏。"""
    fake = FakePlaywright(monkeypatch)
    fake.fail_first_batch = True
    engine = _engine(auto_reconnect=True)

    async def _fetch():
        return await engine.async_fetch_text("http://x", skip_delay=True)

    async def _run():
        return await asyncio.gather(_fetch(), _fetch())

    results = asyncio.run(_run())
    assert all(r == "<html>ok</html>" for r in results)
    engine.close()


def test_sync_fetch_text_keeps_retry_behavior(monkeypatch):
    """同步 fetch_text（isolated session）auto_reconnect=True 时不退化：不直抛原始异常。"""
    fake = FakePlaywright(monkeypatch)
    fake.fail_always = True
    engine = _engine(auto_reconnect=True)
    with pytest.raises(NetworkError):
        engine.fetch_text("http://x", skip_delay=True)
    engine.close()
