from __future__ import annotations

import asyncio
import json
import random
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from .exceptions import NetworkError
from .options import Options, BrowserOptions, APIOptions, RequestsOptions
from ..utils.encoding import detect_encoding
from ..utils.logger import get_logger, mask_key

_log = get_logger("novelbase.core.engine")


def _async_playwright():
    from playwright.async_api import async_playwright
    return async_playwright()


def _resolve_proxy(proxies: dict | None) -> httpx.Proxy | None:
    """httpx>=0.26 的 proxy 参数只接受单个代理；多协议字典按 https/http 优先取一个。"""
    if not proxies:
        return None
    for scheme in ("https", "http"):
        url = proxies.get(scheme)
        if url:
            return httpx.Proxy(url)
    return httpx.Proxy(next(iter(proxies.values())))


class Engine(ABC):
    """网络层基类 — 三种实现共享的接口。"""

    _instances: dict[str, Engine] = {}
    _registry_keys: list[str] = []

    def __init__(self) -> None:
        mode = getattr(self, "name", type(self).__name__)
        idx = sum(1 for k in Engine._registry_keys if k.startswith(f"{mode}_")) + 1
        key = f"{mode}_{idx}"
        Engine._instances[key] = self
        Engine._registry_keys.append(key)
        self._registry_key = key

    @abstractmethod
    def fetch_text(self, url: str, skip_delay: bool = False, encoding: str | None = None, **kwargs) -> str:
        """GET/POST 请求返回纯文本。encoding 为空时自动检测。"""
        ...

    @abstractmethod
    def fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict:
        """GET/POST 请求返回解析后的 JSON 对象。"""
        ...

    @abstractmethod
    async def async_fetch_text(self, url: str, skip_delay: bool = False, encoding: str | None = None, **kwargs) -> str:
        """异步版 fetch_text（GET/POST 返回纯文本）。"""
        ...

    @abstractmethod
    async def async_fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict:
        """异步版 fetch_json（GET/POST 返回解析后的 JSON）。"""
        ...

    @abstractmethod
    async def async_fetch_images(self, urls: list[str], max_workers: int = 5) -> list[bytes]:
        """批量下载图片字节，返回与 urls 等长的 bytes 列表（失败项为 b""）。"""
        ...

    def close(self) -> None:
        """释放所有资源（进程退出前调用）。"""
        Engine._instances.pop(self._registry_key, None)
        try:
            Engine._registry_keys.remove(self._registry_key)
        except ValueError:
            pass

    async def aclose(self) -> None:
        """异步关闭（供 async 上下文 await，确保资源完全释放后再退出）。

        默认走同步 close；持有异步资源的引擎（如 BrowserEngine）覆盖此方法，
        避免「运行中事件循环里 fire-and-forget 关闭，loop 随即退出导致资源残留」。
        """
        self.close()

    @abstractmethod
    def update_options(self, options) -> None:
        """更新引擎选项（运行时热更新）。"""
        ...

class APIEngine(Engine):

    def __init__(self, options: APIOptions) -> None:
        super().__init__()
        self.name = "API"
        self.options = options
        self._client = httpx.Client(
            timeout=options.timeout,
            follow_redirects=True,
            transport=httpx.HTTPTransport(retries=options.retry_times),
        )
        self._async_client = None

    def update_options(self, options: APIOptions) -> None:
        for attr in ("delay", "timeout", "retry_times", "backoff_factor", "key", "params"):
            if hasattr(options, attr):
                setattr(self.options, attr, getattr(options, attr))

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=self.options.timeout,
                follow_redirects=True,
                transport=httpx.AsyncHTTPTransport(retries=self.options.retry_times),
            )
        return self._async_client

    def _merge_post_data(self, post_data: dict[str, Any]) -> dict[str, Any]:
        if self.options.params:
            merged = dict(self.options.params)
            merged.update(post_data)
            return merged
        return post_data

    def fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
        post_data = kwargs.pop('post_data', None)
        _log.debug("API fetch_text: url=%s", mask_key(url[:120]))
        try:
            if post_data is not None:
                response = self._client.post(url, data=self._merge_post_data(post_data))
            else:
                response = self._client.get(url, params=self.options.params or None)
        except httpx.HTTPError as e:
            raise NetworkError(f"API request failed: {e}", url=url) from e
        enc = encoding or detect_encoding(response.content)
        text = response.content.decode(enc, errors="replace")
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        _log.debug("API fetch_text ok: len=%s", len(text))
        return text

    def fetch_json(self, url, skip_delay=False, **kwargs) -> dict[str, Any]:
        post_data = kwargs.pop('post_data', None)
        _log.debug("API fetch_json: url=%s", mask_key(url[:120]))
        try:
            if post_data is not None:
                response = self._client.post(url, data=self._merge_post_data(post_data))
            else:
                response = self._client.get(url, params=self.options.params or None)
        except httpx.HTTPError as e:
            raise NetworkError(f"API request failed: {e}", url=url) from e
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        return response.json()

    async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
        post_data = kwargs.pop('post_data', None)
        client = self._get_async_client()
        _log.debug("API async_fetch_text: url=%s", mask_key(url[:120]))
        try:
            if post_data is not None:
                response = await client.post(url, data=self._merge_post_data(post_data))
            else:
                response = await client.get(url, params=self.options.params or None)
        except httpx.HTTPError as e:
            raise NetworkError(f"API request failed: {e}", url=url) from e
        enc = encoding or detect_encoding(response.content)
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return response.content.decode(enc, errors="replace")

    async def async_fetch_json(self, url, skip_delay=False, **kwargs) -> dict[str, Any]:
        post_data = kwargs.pop('post_data', None)
        client = self._get_async_client()
        _log.debug("API async_fetch_json: url=%s", mask_key(url[:120]))
        try:
            if post_data is not None:
                response = await client.post(url, data=self._merge_post_data(post_data))
            else:
                response = await client.get(url, params=self.options.params or None)
        except httpx.HTTPError as e:
            raise NetworkError(f"API request failed: {e}", url=url) from e
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return response.json()

    async def async_fetch_images(self, urls: list[str], max_workers: int = 5) -> list[bytes]:
        sem = asyncio.Semaphore(max_workers)

        async def _one(url: str) -> bytes:
            async with sem:
                try:
                    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                        return (await client.get(url)).content
                except httpx.HTTPError:
                    return b""

        return await asyncio.gather(*(_one(u) for u in urls))

    def close(self) -> None:
        super().close()
        try:
            self._client.close()
        except Exception:
            pass
        if self._async_client is not None:
            client = self._async_client
            self._async_client = None  # 先置空，保证 close 幂等
            try:
                import asyncio as _aio
                try:
                    loop = _aio.get_running_loop()
                except RuntimeError:
                    _aio.run(client.aclose())          # 无运行中 loop：同步关闭
                else:
                    loop.create_task(client.aclose())  # 有运行中 loop：后台关闭
            except Exception:
                pass


class BrowserEngine(Engine):
    def __init__(self, options: BrowserOptions) -> None:
        super().__init__()
        self.name = "browser"
        self.options = options
        self._playwright = None
        self._browser = None
        self._context = None
        self._launch_lock = None
        self._idle_pages: list = []   # 空闲 page 池（复用，避免每次 new_page/close 重新握手）
        # 懒启动：__init__ 不启动浏览器/锁，首次 async 调用时 _ensure_browser 启动

    def update_options(self, options: BrowserOptions) -> None:
        """热更新 delay/timeout/retry 等参数，不重建浏览器。

        browser_type / headless / user_data_dir / viewport / extra_args 变更才重建浏览器。
        """
        needs_rebuild = False
        for hard_attr in ("browser_type", "headless", "extra_args"):
            new_val = getattr(options, hard_attr, None)
            if new_val is not None and new_val != getattr(self.options, hard_attr, None):
                setattr(self.options, hard_attr, new_val)
                needs_rebuild = True
        new_ud = getattr(options, "user_data_dir", None)
        old_ud = getattr(self.options, "user_data_dir", None)
        if str(new_ud or "") != str(old_ud or ""):
            self.options.user_data_dir = options.user_data_dir
            needs_rebuild = True
        new_vp = getattr(options, "viewport", None)
        if new_vp is not None and new_vp != getattr(self.options, "viewport", None):
            self.options.viewport = new_vp
            needs_rebuild = True

        for attr in ("delay", "timeout", "retry_times", "backoff_factor"):
            if hasattr(options, attr):
                setattr(self.options, attr, getattr(options, attr))

        if needs_rebuild:
            self._schedule_rebuild()

    def _schedule_rebuild(self) -> None:
        """标记浏览器需重建：下一次 async 调用前关闭旧 browser 并重建。"""
        # 已有运行中 loop 才真正关闭；无 loop（尚未启动）时置 None 即可
        if self._browser is not None or self._context is not None:
            self._close_running()

    def _close_running(self) -> None:
        browser, context, pw = self._browser, self._context, self._playwright
        self._browser = self._context = self._playwright = None
        self._idle_pages.clear()   # 池里 page 随 context 关闭，清空引用
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._shutdown(browser, context, pw))
        else:
            loop.create_task(self._shutdown(browser, context, pw))

    @staticmethod
    async def _shutdown(browser, context, pw):
        for obj in (browser, context):
            if obj is not None:
                try:
                    await obj.close()
                except Exception:
                    pass
        if pw is not None:
            try:
                await pw.stop()
            except Exception:
                pass

    async def _ensure_browser(self):
        if self._browser is not None or self._context is not None:
            return
        if self._launch_lock is None:
            self._launch_lock = asyncio.Lock()
        async with self._launch_lock:
            await self._ensure_browser_locked()

    async def _ensure_browser_locked(self):
        """锁内启动（调用方须已持有 _launch_lock）；double-check 后启动。"""
        if self._browser is not None or self._context is not None:
            return
        pw = _async_playwright()
        self._playwright = await pw.start()
        browser_type = getattr(self._playwright, self.options.browser_type, None)
        if browser_type is None:
            raise ValueError(f"不支持的 browser_type: {self.options.browser_type}")
        if self.options.user_data_dir:
            # 持久化上下文：launch_persistent_context 返回 context（自带 browser）
            self._context = await browser_type.launch_persistent_context(
                str(self.options.user_data_dir),
                headless=self.options.headless,
                args=self.options.extra_args or [],
                viewport=self.options.viewport,
            )
            self._browser = self._context.browser
        else:
            self._browser = await browser_type.launch(
                headless=self.options.headless,
                args=self.options.extra_args or [],
            )
            if self.options.viewport:
                self._context = await self._browser.new_context(viewport=self.options.viewport)
            else:
                self._context = await self._browser.new_context()
        _log.info("BrowserEngine started: headless=%s", self.options.headless)

    async def new_page(self):
        """懒启动后返回一个新的 Playwright page（供书源交互）。"""
        await self._ensure_browser()
        return await self._context.new_page()

    async def _acquire_page(self):
        """从池借一个空闲 page；池空则懒创建（无上限，与同步时代懒加载一致）。

        复用 page 省去每次 new_page/close 的 CDP 往返；并发数由上层下载器的
        Semaphore 限流，engine 层不做冗余限制。
        """
        if self._idle_pages:
            return self._idle_pages.pop()
        return await self._context.new_page()

    async def _release_page(self, page) -> None:
        """归还 page 到池（不 close，供后续复用）。"""
        self._idle_pages.append(page)

    @staticmethod
    def _is_reconnectable_error(e: Exception) -> bool:
        """判定异常是否为「浏览器失效」类（仅此类触发自动重建）。"""
        msg = str(e).lower()
        name = type(e).__name__
        if name in ("TargetClosedError", "PlaywrightConnectionError", "BrowserClosedError"):
            return True
        return "browser" in msg and "closed" in msg

    async def _reset_browser(self) -> None:
        """容错清理残留浏览器/上下文/playwright，并清空 page 池。"""
        # Playwright 对象无 close()，只有 stop()（否则残留 driver 进程）
        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        for obj in (self._browser, self._context):
            if obj is None:
                continue
            try:
                await obj.close()
            except Exception:
                pass
        self._browser = None
        self._context = None
        self._idle_pages.clear()

    async def _reconnect_browser(self) -> None:
        """重建浏览器实例（锁内 reset + ensure，避免并发任务互相破坏）。"""
        if self._launch_lock is None:
            self._launch_lock = asyncio.Lock()
        async with self._launch_lock:
            await self._reset_browser()
            await self._ensure_browser_locked()

    async def _fetch_with_page(self, page, url, skip_delay=False, *, abort_on_browser_close: bool = False) -> str:
        """在给定 page 上带 retry/backoff 抓取文本（async 与同步独立会话共用）。"""
        for i in range(self.options.retry_times):
            if i > 0:
                _log.warning(
                    "fetch_text retry %s/%s: url=%s",
                    i + 1, self.options.retry_times, mask_key(url[:120]),
                )
            try:
                await page.goto(url, timeout=self.options.timeout * 1000)
                if not skip_delay:
                    await asyncio.sleep(random.uniform(*self.options.delay))
                html = await page.content()
                _log.debug("fetch_text ok: len=%s url=%s", len(html), mask_key(url[:120]))
                return html
            except Exception as e:
                if abort_on_browser_close and self.options.auto_reconnect and self._is_reconnectable_error(e):
                    raise  # 浏览器失效 → 交给 async_fetch_text 层重建（仅持久浏览器路径）
                backoff = self.options.backoff_factor * (2 ** i)
                _log.debug("fetch_text attempt %s failed: %s; backoff %.1fs",
                           i + 1, e, backoff)
                await asyncio.sleep(backoff)
        _log.error("fetch_text exhausted retries: url=%s", mask_key(url[:120]))
        raise NetworkError(
            f"fetch_text failed after {self.options.retry_times} retries",
            url=url,
        )

    async def _do_fetch_text(self, url, skip_delay=False, **kwargs):
        page = await self._acquire_page()
        try:
            result = await self._fetch_with_page(page, url, skip_delay=skip_delay, abort_on_browser_close=True)
        except Exception:
            # 抓取失败：page 可能已损坏（多次 goto 失败/浏览器异常），close 不归还
            try:
                await page.close()
            except Exception:
                pass
            raise
        await self._release_page(page)
        return result

    async def async_fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
        """真异步：直接 await Playwright（不 to_thread）；浏览器失效时按 auto_reconnect 重建。"""
        _log.debug("async_fetch_text start: url=%s", mask_key(url[:120]))
        await self._ensure_browser()
        for attempt in range(self.options.retry_times):
            try:
                return await self._do_fetch_text(url, skip_delay=skip_delay, **kwargs)
            except Exception as e:
                if not (self.options.auto_reconnect and self._is_reconnectable_error(e)):
                    raise
                _log.warning("浏览器失效(%s)，重建浏览器后重试 %s/%s: url=%s",
                             e, attempt + 1, self.options.retry_times, mask_key(url[:120]))
                await self._reconnect_browser()
        _log.error("fetch_text exhausted reconnects: url=%s", mask_key(url[:120]))
        raise NetworkError(
            f"fetch_text failed after {self.options.retry_times} reconnects",
            url=url,
        )

    async def async_fetch_json(self, url, skip_delay=False, **kwargs) -> dict[str, Any]:
        text = await self.async_fetch_text(url=url, skip_delay=skip_delay, **kwargs)
        return json.loads(text)

    def fetch_text(self, url, skip_delay=False, encoding=None, **kwargs) -> str:
        """同步入口：独立浏览器会话（自启自停），不触碰懒启动的 browser。

        注意：不能在已运行的事件循环内调用（会抛 RuntimeError），
        异步上下文请用 async_fetch_text。
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "fetch_text 不能在异步上下文中同步调用，请改用 async_fetch_text"
            )
        return asyncio.run(self._fetch_in_isolated_session(url, skip_delay=skip_delay, **kwargs))

    async def _fetch_in_isolated_session(self, url, skip_delay=False, **kwargs) -> str:
        async with _async_playwright() as pw:
            browser_type = getattr(pw, self.options.browser_type, None)
            if browser_type is None:
                raise ValueError(f"不支持的 browser_type: {self.options.browser_type}")
            browser = await browser_type.launch(
                headless=self.options.headless,
                args=self.options.extra_args or [],
            )
            try:
                page = await browser.new_page()
                try:
                    return await self._fetch_with_page(page, url, skip_delay=skip_delay)
                finally:
                    await page.close()
            finally:
                await browser.close()

    def fetch_json(self, url, skip_delay=False, **kwargs) -> dict[str, Any]:
        text = self.fetch_text(url=url, skip_delay=skip_delay, **kwargs)
        return json.loads(text)

    async def async_fetch_images(self, urls, max_workers=5) -> list[bytes]:
        """图片下载用 httpx（不开 tab）。与 Requests/API 版结构一致。"""
        sem = asyncio.Semaphore(max_workers)

        async def _one(url: str) -> bytes:
            async with sem:
                try:
                    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                        return (await client.get(url)).content
                except httpx.HTTPError:
                    return b""

        return await asyncio.gather(*(_one(u) for u in urls))

    def close(self) -> None:
        super().close()
        if self._browser is not None or self._context is not None or self._playwright is not None:
            self._close_running()

    async def aclose(self) -> None:
        """异步关闭：await 完成浏览器/驱动释放（供 shutdown 等 async 上下文）。

        同步 close() 在运行中事件循环里只能 fire-and-forget（loop 随即退出会残留
        浏览器子进程）；aclose() 由调用方 await，确保彻底释放后再退出。
        """
        super().close()
        browser, context, pw = self._browser, self._context, self._playwright
        self._browser = self._context = self._playwright = None
        self._idle_pages.clear()   # context 关闭会连带关池里 page，这里清空引用
        await self._shutdown(browser, context, pw)

    @property
    def browser(self) -> Any:
        """返回底层 Playwright browser 实例（懒启动后才有，否则 None）。"""
        return self._browser

class RequestsEngine(Engine):

    def __init__(self, options: RequestsOptions) -> None:
        super().__init__()
        self.name = "requests"
        self.options = options
        self._client = httpx.Client(
            headers=options.headers,
            cookies=options.cookies,
            proxy=_resolve_proxy(options.proxies),
            follow_redirects=True,
            timeout=options.timeout,
            transport=httpx.HTTPTransport(retries=options.retry_times),
        )
        self._async_client = None

    def update_options(self, options: RequestsOptions) -> None:
        for attr in ("delay", "timeout", "retry_times", "backoff_factor", "headers", "cookies", "proxies"):
            if hasattr(options, attr):
                setattr(self.options, attr, getattr(options, attr))

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                headers=self.options.headers,
                cookies=self.options.cookies,
                proxy=_resolve_proxy(self.options.proxies),
                follow_redirects=True,
                timeout=self.options.timeout,
                transport=httpx.AsyncHTTPTransport(retries=self.options.retry_times),
            )
        return self._async_client

    def fetch_text(self, url: str, skip_delay: bool = False, encoding: str | None = None, **kwargs) -> str:
        post_data = kwargs.pop('post_data', None)
        _log.debug("Requests fetch_text: url=%s", mask_key(url[:120]))
        try:
            if post_data is not None:
                response = self._client.post(url, data=post_data)
            else:
                response = self._client.get(url)
        except httpx.HTTPError as e:
            raise NetworkError(f"Requests request failed: {e}", url=url) from e

        enc = encoding or detect_encoding(response.content)
        text = response.content.decode(enc, errors="replace")
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        _log.debug("Requests fetch_text ok: len=%s", len(text))
        return text

    def fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict[str, Any]:
        try:
            response = self._client.get(url)
        except httpx.HTTPError as e:
            raise NetworkError(f"GET failed: {e}", url=url) from e
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        return response.json()

    async def async_fetch_text(self, url: str, skip_delay: bool = False, encoding: str | None = None, **kwargs) -> str:
        post_data = kwargs.pop('post_data', None)
        client = self._get_async_client()
        try:
            if post_data is not None:
                response = await client.post(url, data=post_data)
            else:
                response = await client.get(url)
        except httpx.HTTPError as e:
            raise NetworkError(f"Requests request failed: {e}", url=url) from e
        enc = encoding or detect_encoding(response.content)
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return response.content.decode(enc, errors="replace")

    async def async_fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict[str, Any]:
        client = self._get_async_client()
        try:
            response = await client.get(url)
        except httpx.HTTPError as e:
            raise NetworkError(f"Requests request failed: {e}", url=url) from e
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return response.json()

    async def async_fetch_images(self, urls: list[str], max_workers: int = 5) -> list[bytes]:
        sem = asyncio.Semaphore(max_workers)

        async def _one(url: str) -> bytes:
            async with sem:
                try:
                    async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
                        return (await client.get(url)).content
                except httpx.HTTPError:
                    return b""

        return await asyncio.gather(*(_one(u) for u in urls))

    def close(self) -> None:
        super().close()
        try:
            self._client.close()
        except Exception:
            pass
        if self._async_client is not None:
            client = self._async_client
            self._async_client = None  # 先置空，保证 close 幂等
            try:
                # AsyncClient.close() 是异步方法；有运行中 loop 就后台关闭，
                # 否则同步 asyncio.run 关闭。
                import asyncio as _aio
                try:
                    loop = _aio.get_running_loop()
                except RuntimeError:
                    _aio.run(client.aclose())
                else:
                    loop.create_task(client.aclose())
            except Exception:
                pass

def create_engine(options: Options) -> Any:
    """根据 Options.mode 创建对应引擎实例。

    Args:
        options: 全局配置对象。
    Returns:
        APIEngine / RequestsEngine / BrowserEngine 之一。
    Raises:
        ValueError: mode 不在 ["api", "requests", "browser"] 中。
    """
    mode_map = {
        "api": (APIEngine, options.api),
        "requests": (RequestsEngine, options.requests),
        "browser": (BrowserEngine, options.browser),
    }
    cls, opts = mode_map.get(options.mode, (None, None))
    if cls is None:
        raise ValueError(
            f"mode {options.mode!r} is not supported; "
            f"choose from {list(mode_map)}"
        )
    return cls(opts)