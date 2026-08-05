from __future__ import annotations
import json
import random
import sys
import threading
import time
from abc import ABC, abstractmethod
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from requests.structures import CaseInsensitiveDict
from urllib3.util.retry import Retry

from .exceptions import NetworkError
from .options import Options, BrowserOptions, APIOptions, RequestsOptions
from ..utils.logger import get_logger, mask_key

_log = get_logger("novelbase.core.engine")


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
        self._session_local = threading.local()
        self._session_lock = threading.Lock()
        self._sessions: list[requests.Session] = []

    def update_options(self, options: APIOptions) -> None:
        for attr in ("delay", "timeout", "retry_times", "backoff_factor", "key", "params"):
            if hasattr(options, attr):
                setattr(self.options, attr, getattr(options, attr))

    def _create_session(self) -> requests.Session:
        retry_strategy = Retry(
            total=self.options.retry_times,
            backoff_factor=self.options.backoff_factor,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        return session

    def _get_session(self) -> requests.Session:
        if not hasattr(self._session_local, 'session'):
            with self._session_lock:
                session = self._create_session()
                self._sessions.append(session)
                self._session_local.session = session
        return self._session_local.session

    def _requests_get(self, url: str, skip_delay: bool = False, **kwargs) -> requests.Response:
        """执行 GET 请求，统一处理延时、编码和异常。"""
        session = self._get_session()
        try:
            response = session.get(
                url=url,
                params=self.options.params or None,
                timeout=(10, self.options.timeout),
            )
        except requests.RequestException as e:
            raise NetworkError(f"GET failed: {e}", url=url) from e

        response.encoding = 'utf-8'
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        return response

    def _request_post(self, url: str, post_data: dict[str, Any] | None = None, skip_delay: bool = False, **kwargs) -> requests.Response:
        """执行 POST 请求，统一处理延时、编码和异常。"""
        if post_data is None:
            raise NetworkError(
                "APIEngine.fetch_* requires post_data kwarg",
                url=url,
            )

        # 合并 APIOptions.params（若有）到 post_data
        if self.options.params:
            merged = dict(self.options.params)
            merged.update(post_data)
            post_data = merged

        session = self._get_session()
        try:
            response = session.post(
                url=url,
                data=post_data,
                timeout=(10, self.options.timeout),
            )
        except requests.RequestException as e:
            raise NetworkError(f"POST failed: {e}", url=url) from e

        response.encoding = 'utf-8'
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        return response

    def fetch_text(self, url: str, skip_delay: bool = False, encoding: str | None = None, **kwargs) -> str:
        post_data = kwargs.pop('post_data', None)
        _log.debug("API fetch_text: url=%s", mask_key(url[:120]))
        if post_data is not None:
            response = self._request_post(url, post_data=post_data, skip_delay=skip_delay, **kwargs)
        else:
            response = self._requests_get(url, skip_delay=skip_delay, **kwargs)
        if encoding:
            response.encoding = encoding
        _log.debug("API fetch_text ok: len=%s", len(response.text))
        return response.text

    def fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict[str, Any]:
        post_data = kwargs.pop('post_data', None)
        _log.debug("API fetch_json: url=%s", mask_key(url[:120]))
        if post_data is not None:
            response = self._request_post(url, post_data=post_data, skip_delay=skip_delay, **kwargs)
        else:
            response = self._requests_get(url, skip_delay=skip_delay, **kwargs)
        return response.json()

    def close(self) -> None:
        super().close()
        for session in self._sessions:
            try:
                session.close()
            except (OSError, AttributeError):
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
        if sys.platform.startswith("linux"):
            co.set_argument("--no-sandbox")
            co.set_argument("--disable-gpu")
            co.set_argument("--disable-setuid-sandbox")
            co.set_argument("--disable-dev-shm-usage")

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
        self._session_local = threading.local()
        self._session_lock = threading.Lock()
        self._sessions: list[requests.Session] = []

    def update_options(self, options: RequestsOptions) -> None:
        for attr in ("delay", "timeout", "retry_times", "backoff_factor", "headers", "cookies", "proxies"):
            if hasattr(options, attr):
                setattr(self.options, attr, getattr(options, attr))

    # ── Session 管理 ─────────────────────────────────────────────

    def _create_session(self) -> requests.Session:
        retry_strategy = Retry(
            total=self.options.retry_times,
            backoff_factor=self.options.backoff_factor,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        if self.options.proxies:
            session.proxies = self.options.proxies
        if self.options.headers:
            session.headers = CaseInsensitiveDict(self.options.headers)
        return session

    def _get_session(self) -> requests.Session:
        if not hasattr(self._session_local, 'session'):
            with self._session_lock:
                session = self._create_session()
                self._sessions.append(session)
                self._session_local.session = session
        return self._session_local.session

    # ── 请求 ─────────────────────────────────────────────────────

    def fetch_text(self, url: str, skip_delay: bool = False, encoding: str | None = None, **kwargs) -> str:
        _log.debug("Requests fetch_text: url=%s", mask_key(url[:120]))
        session = self._get_session()
        try:
            response = session.get(
                url,
                timeout=(10, self.options.timeout),
                cookies=self.options.cookies,
            )
        except requests.RequestException as e:
            raise NetworkError(f"GET failed: {e}", url=url) from e

        response.encoding = encoding or response.apparent_encoding or 'utf-8'
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        _log.debug("Requests fetch_text ok: len=%s", len(response.text))
        return response.text

    def fetch_json(self, url: str, skip_delay: bool = False, **kwargs) -> dict[str, Any]:
        session = self._get_session()
        try:
            response = session.get(
                url,
                timeout=(10, self.options.timeout),
                cookies=self.options.cookies,
            )
        except requests.RequestException as e:
            raise NetworkError(f"GET failed: {e}", url=url) from e

        response.encoding = 'utf-8'
        if not skip_delay:
            time.sleep(random.uniform(*self.options.delay))
        return response.json()

    def close(self) -> None:
        super().close()
        for session in self._sessions:
            try:
                session.close()
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