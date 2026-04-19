import json
import random
import time
from abc import ABC, abstractmethod
from queue import Queue
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from core.options import Options, BrowserOptions, APIOptions, RequestsOptions


class Engine(ABC):
    """下载器基类"""

    @abstractmethod
    def fetch_text(self, url, **kwargs):
        """访问网站"""
        pass

    @abstractmethod
    def fetch_json(self, url, **kwargs):
        """API"""

    @abstractmethod
    def close(self):
        pass

class APIEngine(Engine):

    def __init__(
            self,
            options: APIOptions,
    ):
        self.name = "API"
        self.options = options
        self._set_new_session()

    def _set_new_session(self):
        retry_strategy = Retry(
            total=self.options.retry_times,
            backoff_factor=self.options.backoff_factor,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)

    def fetch_text(self, url, **kwargs):
        response = self.session.post(url=url, data=kwargs["post_data"], timeout=self.options.timeout)
        time.sleep(random.uniform(*self.options.delay))
        response.encoding = 'utf-8'
        return response.text

    def fetch_json(self, url, **kwargs):
        response = self.session.post(url=url, data=kwargs["post_data"], timeout=self.options.timeout)
        time.sleep(random.uniform(*self.options.delay))
        response.encoding = 'utf-8'
        return response.json()

    def close(self):
        self.session.close()

class BrowserEngine(Engine):

    def __init__(
            self,
            options: BrowserOptions,
    ):
        self.name = "browser"
        self.options = options
        self._queue = Queue()
        self._context = self._init_browser()

    def _init_browser(self):
        from playwright.sync_api import sync_playwright
        from playwright.sync_api import ViewportSize
        self._playwright = sync_playwright().start()
        if self.options.viewport:
            view_port_size = ViewportSize(
                width=self.options.viewport.get("width", 1280),
                height=self.options.viewport.get("height",720)
            )
        else:
            view_port_size = None
        if self.options.user_data_dir:
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.options.user_data_dir,
                headless=self.options.headless,
                viewport=view_port_size
            )
        else:
            self._context = self._playwright.chromium.launch(
                headless=self.options.headless,
            ).new_context(storage_state=self.options.storage_state_path,viewport=view_port_size)
            if self.options.page_count:
                for i in range(self.options.page_count):
                    self._queue.put(self._context.new_page())
        return self._context


    def fetch_text(self, url, **kwargs):
        """访问网站"""
        for i in range(self.options.retry_times):
            try:
                page = self._queue.get() if self.options.page_count else self._context.new_page()
                page.goto(url)
                time.sleep(random.uniform(*self.options.delay))
                content = page.content()
                if self.options.page_count:
                    self._queue.put(page)
                else:
                    page.close()
                return content
            except TimeoutError:
                time.sleep(((self.options.backoff_factor * 2) ** i))
        else:
            raise TimeoutError()

    def fetch_json(self, url, **kwargs):
        text = self.fetch_text(url=url)
        return json.loads(text)

    def mount_context(self, context):
        self._context = context

    def close(self):
        self._context.close()
        self._playwright.stop()

    @property
    def context(self):
        return self._context

class RequestsEngine(Engine):

    def __init__(
            self,
            options: RequestsOptions,
    ):
        self.name = "requests"
        self.options = options
        self._set_new_session()

    def _set_new_session(self):
        retry_strategy = Retry(
            total=3,
            backoff_factor=self.options.backoff_factor,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        if self.options.proxies:
            self.session.proxies = self.options.proxies
        if self.options.headers:
            self.session.headers = self.options.headers

    def fetch_text(self, url, **kwargs):
        response = self.session.get(url, timeout=self.options.timeout,cookies=self.options.cookies)
        response.encoding = 'utf-8'
        time.sleep(random.uniform(*self.options.delay))
        return response.text

    def fetch_json(self, url, **kwargs):
        response = self.session.get(url, timeout=self.options.timeout,cookies=self.options.cookies)
        response.encoding = 'utf-8'
        time.sleep(random.uniform(*self.options.delay))
        return response.json()

    def close(self):
        self.session.close()

def create_engine(options: Options) -> APIEngine | RequestsEngine | BrowserEngine:
    if options.mode == "api":
        return APIEngine(options.api)
    elif options.mode == "requests":
        return RequestsEngine(options.requests)
    elif options.mode == "browser":
        return BrowserEngine(options.browser)
    else:
        raise ValueError(f"mode {options.mode} is not supported")