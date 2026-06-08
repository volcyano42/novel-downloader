import json
import random
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
from ..utils.logger import get_logger

_log = get_logger("nldlder.core.engine")


class Engine(ABC):
    """网络层基类 — 三种实现共享的接口。"""

    @abstractmethod
    def fetch_text(self, url: str, no_delay: bool = False, **kwargs) -> str:
        """GET/POST 请求返回纯文本。"""
        ...

    @abstractmethod
    def fetch_json(self, url: str,no_delay: bool = False, **kwargs) -> dict:
        """GET/POST 请求返回解析后的 JSON 对象。"""
        ...

    @abstractmethod
    def close(self) -> None:
        """释放所有资源（进程退出前调用）。"""
        ...

    def close_current(self) -> None:
        """关闭当前线程持有的资源（page / session），线程退出前调用。"""
        _log.debug("%s.close_current: no-op", type(self).__name__)

class APIEngine(Engine):

    def __init__(self, options: APIOptions) -> None:
        self.name = "API"
        self.options = options
        self._session_local = threading.local()
        self._session_lock = threading.Lock()
        self._sessions: list[requests.Session] = []

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

    def _request_post(self, url: str,post_data = None, no_delay: bool = False, **kwargs) -> requests.Response:
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
                timeout=self.options.timeout,
            )
        except requests.RequestException as e:
            raise NetworkError(f"POST failed: {e}", url=url) from e

        response.encoding = 'utf-8'
        if not no_delay:
            time.sleep(random.uniform(*self.options.delay))
        return response

    def fetch_text(self, url: str, post_data = None, no_delay: bool = False, **kwargs) -> str:
        _log.debug("API fetch_text: url=%s", url[:80])
        response = self._request_post(url,post_data = post_data,no_delay = no_delay, **kwargs)
        _log.debug("API fetch_text ok: len=%s", len(response.text))
        return response.text

    def fetch_json(self, url: str, post_data = None, no_delay: bool = False, **kwargs: Any) -> Any:
        _log.debug("API fetch_json: url=%s", url[:80])
        response = self._request_post(url,post_data = post_data,no_delay = no_delay, **kwargs)
        return response.json()

    def close(self) -> None:
        for session in self._sessions:
            try:
                session.close()
            except Exception:
                pass

    def close_current(self) -> None:
        if not hasattr(self._session_local, 'session'):
            return
        session = self._session_local.session
        _log.debug("APIEngine.close_current: closing session")
        try:
            session.close()
        except Exception:
            pass
        with self._session_lock:
            if session in self._sessions:
                self._sessions.remove(session)
        del self._session_local.session

class BrowserEngine(Engine):
    def __init__(self, options: BrowserOptions) -> None:
        self.name = "browser"
        self.options = options
        self._thread_local = threading.local()
        self._page_lock = threading.Lock()
        self._page_pool: list[Any] = []
        self._init_browser()

    def _init_browser(self) -> None:
        from DrissionPage import Chromium, ChromiumOptions

        co = ChromiumOptions()
        co.headless(self.options.headless)
        if self.options.viewport:
            co.set_argument(
                f'--window-size={self.options.viewport["width"]},'
                f'{self.options.viewport["height"]}'
            )
        if self.options.user_data_dir:
            co.set_user_data_path(str(self.options.user_data_dir))

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

    def fetch_text(self, url: str, no_delay: bool = False, **kwargs: Any) -> str:
        _log.debug("fetch_text start: url=%s", url[:80])
        page = self.get_page()

        for i in range(self.options.retry_times):
            if i > 0:
                _log.warning(
                    "fetch_text retry %s/%s: url=%s",
                    i + 1, self.options.retry_times, url[:80],
                )
            try:
                page.get(url, timeout=self.options.timeout)
                time.sleep(random.uniform(*self.options.delay))
                _log.debug("fetch_text ok: len=%s url=%s", len(page.html), url[:80])
                return page.html
            except Exception as e:
                backoff = self.options.backoff_factor * (2 ** i)
                _log.debug("fetch_text attempt %s failed: %s; backoff %.1fs",
                           i + 1, e, backoff)
                time.sleep(backoff)

        _log.error("fetch_text exhausted retries: url=%s", url[:80])
        raise NetworkError(
            f"fetch_text failed after {self.options.retry_times} retries",
            url=url,
        )

    def fetch_json(self, url: str, no_delay: bool = False, **kwargs: Any) -> Any:
        text = self.fetch_text(url=url)
        return json.loads(text)

    def close(self) -> None:
        for page in self._page_pool:
            try:
                page.close()
            except Exception:
                pass

    def close_current(self) -> None:
        if not hasattr(self._thread_local, 'page'):
            return
        page = self._thread_local.page
        _log.debug("BrowserEngine.close_current: closing page")
        try:
            page.close()
        except Exception:
            pass
        with self._page_lock:
            if page in self._page_pool:
                self._page_pool.remove(page)
        del self._thread_local.page

    @property
    def browser(self) -> Any:
        """返回底层 Chromium 浏览器实例，供高级操作使用。"""
        return self._browser

class RequestsEngine(Engine):

    def __init__(self, options: RequestsOptions) -> None:
        self.name = "requests"
        self.options = options
        self._session_local = threading.local()
        self._session_lock = threading.Lock()
        self._sessions: list[requests.Session] = []

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

    def fetch_text(self, url: str, no_delay: bool = False, **kwargs: Any) -> str:
        _log.debug("Requests fetch_text: url=%s", url[:80])
        session = self._get_session()
        try:
            response = session.get(
                url,
                timeout=self.options.timeout,
                cookies=self.options.cookies,
            )
        except requests.RequestException as e:
            raise NetworkError(f"GET failed: {e}", url=url) from e

        response.encoding = 'utf-8'
        time.sleep(random.uniform(*self.options.delay))
        _log.debug("Requests fetch_text ok: len=%s", len(response.text))
        return response.text

    def fetch_json(self, url: str, no_delay: bool = False, **kwargs: Any) -> Any:
        session = self._get_session()
        try:
            response = session.get(
                url,
                timeout=self.options.timeout,
                cookies=self.options.cookies,
            )
        except requests.RequestException as e:
            raise NetworkError(f"GET failed: {e}", url=url) from e

        response.encoding = 'utf-8'
        time.sleep(random.uniform(*self.options.delay))
        return response.json()

    def close(self) -> None:
        for session in self._sessions:
            try:
                session.close()
            except Exception:
                pass

    def close_current(self) -> None:
        if not hasattr(self._session_local, 'session'):
            return
        session = self._session_local.session
        _log.debug("RequestsEngine.close_current: closing session")
        try:
            session.close()
        except Exception:
            pass
        with self._session_lock:
            if session in self._sessions:
                self._sessions.remove(session)
        del self._session_local.session

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
