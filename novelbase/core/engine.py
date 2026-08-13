from __future__ import annotations
import asyncio
import json
import random
import threading
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from .exceptions import NetworkError
from .options import Options, BrowserOptions, APIOptions, RequestsOptions
from ..utils.encoding import detect_encoding
from ..utils.logger import get_logger, mask_key

_log = get_logger("novelbase.core.engine")


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

    def close(self) -> None:
        """释放所有资源（进程退出前调用）。"""
        Engine._instances.pop(self._registry_key, None)
        try:
            Engine._registry_keys.remove(self._registry_key)
        except ValueError:
            pass

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

    def close(self) -> None:
        super().close()
        try:
            self._client.close()
        except Exception:
            pass
        if self._async_client is not None:
            try:
                import asyncio as _aio
                try:
                    _aio.get_running_loop()
                except RuntimeError:
                    _aio.run(self._async_client.aclose())
            except Exception:
                pass

class BrowserEngine(Engine):
    def __init__(self, options: BrowserOptions) -> None:
        super().__init__()
        self.name = "browser"
        self.options = options
        self._thread_local = threading.local()
        self._page_lock = threading.Lock()
        self._page_pool: list = []
        self._browser = None
        self._init_browser()

    def update_options(self, options: BrowserOptions) -> None:
        """热更新 delay/timeout/retry 等参数，不重建浏览器。

        browser_type / headless / user_data_dir / viewport 变更才重建浏览器。
        """
        needs_rebuild = False
        for hard_attr in ("browser_type", "headless", "extra_args"):
            new_val = getattr(options, hard_attr, None)
            if new_val is not None and new_val != getattr(self.options, hard_attr, None):
                setattr(self.options, hard_attr, new_val)
                needs_rebuild = True
        # user_data_dir 比较时忽略 None vs "" 差异
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
            self._init_browser()

    def _init_browser(self) -> None:
        from DrissionPage import Chromium, ChromiumOptions

        # 确保内部状态已初始化（update_options 也会经过这里）
        if not hasattr(self, '_thread_local'):
            self._thread_local = threading.local()
        if not hasattr(self, '_page_lock'):
            self._page_lock = threading.Lock()
        if not hasattr(self, '_page_pool'):
            self._page_pool = []

        # quit 旧浏览器防止进程泄漏
        if hasattr(self, '_browser'):
            try:
                self._browser.quit()
            except Exception:
                pass

        co = ChromiumOptions()
        co.headless(self.options.headless)
        if self.options.viewport:
            co.set_argument(
                f'--window-size={self.options.viewport["width"]},'
                f'{self.options.viewport["height"]}'
            )
        if self.options.user_data_dir:
            co.set_user_data_path(str(self.options.user_data_dir))
        if self.options.extra_args:
            for arg in self.options.extra_args:
                co.set_argument(arg)

        self._browser = Chromium(co)

        _log.info(
            "BrowserEngine init: headless=%s",
            self.options.headless,
        )
        _log.debug("BrowserEngine started (pages created lazily per thread)")

    def get_page(self):
        """获取当前线程独占的 ChromiumPage。

        每个线程第一次调用时创建新 page 并加入池中；
        后续调用复用该 page，天然线程隔离。
        """
        if not hasattr(self._thread_local, 'page'):
            with self._page_lock:
                self._thread_local.page = self._browser.new_tab()
                self._page_pool.append(self._thread_local.page)
        return self._thread_local.page

    def new_page(self):
        return self._browser.new_tab()

    def fetch_text(self, url: str, skip_delay: bool = False, encoding: str | None = None, **kwargs) -> str:
        _log.debug("fetch_text start: url=%s", mask_key(url[:120]))
        page = self.get_page()

        for i in range(self.options.retry_times):
            if i > 0:
                _log.warning(
                    "fetch_text retry %s/%s: url=%s",
                    i + 1, self.options.retry_times, mask_key(url[:120]),
                )
            try:
                page.get(url, timeout=self.options.timeout)
                if not skip_delay:
                    time.sleep(random.uniform(*self.options.delay))
                _log.debug("fetch_text ok: len=%s url=%s", len(page.html), mask_key(url[:120]))
                return page.html
            except Exception as e:
                backoff = self.options.backoff_factor * (2 ** i)
                _log.debug("fetch_text attempt %s failed: %s; backoff %.1fs",
                           i + 1, e, backoff)
                time.sleep(backoff)

        _log.error("fetch_text exhausted retries: url=%s", mask_key(url[:120]))
        raise NetworkError(
            f"fetch_text failed after {self.options.retry_times} retries",
            url=url,
        )

    def fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict[str, Any]:
        text = self.fetch_text(url=url, skip_delay=skip_delay, **kwargs)
        return json.loads(text)

    def close(self) -> None:
        super().close()
        for page in self._page_pool:
            try:
                page.close()
            except (OSError, AttributeError):
                pass
        if self._browser:
            try:
                self._browser.quit()
            except (OSError, AttributeError):
                pass

    @property
    def browser(self) -> Any:
        """返回底层 Chromium 浏览器实例，供高级操作使用。"""
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
        _log.debug("Requests fetch_text: url=%s", mask_key(url[:120]))
        try:
            response = self._client.get(url)
        except httpx.HTTPError as e:
            raise NetworkError(f"GET failed: {e}", url=url) from e

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
        client = self._get_async_client()
        response = await client.get(url)
        enc = encoding or detect_encoding(response.content)
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return response.content.decode(enc, errors="replace")

    async def async_fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict[str, Any]:
        client = self._get_async_client()
        response = await client.get(url)
        if not skip_delay:
            await asyncio.sleep(random.uniform(*self.options.delay))
        return response.json()

    def close(self) -> None:
        super().close()
        try:
            self._client.close()
        except Exception:
            pass
        if self._async_client is not None:
            try:
                # AsyncClient.close() 是异步方法，需在事件循环里关；这里尽力关闭
                import asyncio as _aio
                try:
                    _aio.get_running_loop()
                except RuntimeError:
                    _aio.run(self._async_client.aclose())
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