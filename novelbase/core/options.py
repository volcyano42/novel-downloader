from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence, Literal



@dataclass
class APIOptions:
    name: str | None = None
    delay: tuple[float, ...] = field(default_factory=lambda: (3.0, 5.0))
    timeout: float = 30
    retry_times: int = 3
    backoff_factor: float = 2
    key: str | None = None
    params: dict[str, str] | None = None

@dataclass
class RequestsOptions:
    headers: dict = field(default_factory=lambda: {"User-Agent": "Mozilla/5.0 ..."})
    delay: tuple[float, ...] = field(default_factory=lambda: (3.0, 5.0))
    timeout: float = 30
    retry_times: int = 3
    backoff_factor: float = 2
    cookies: dict[str, str] | None = None
    proxies: dict[str, str] | None = None

@dataclass
class BrowserOptions:
    browser_type: str = "chromium"
    delay: tuple[float, ...] = field(default_factory=lambda: (3.0, 5.0))
    timeout: float = 30
    retry_times: int = 3
    backoff_factor: float = 2
    headless: bool = False
    user_data_dir: Path | str | None = None
    viewport: dict[str, int] | None = None
    extra_args: list[str] | None = None
    auto_reconnect: bool = False   # 浏览器意外关闭时自动重建并重试

@dataclass
class StorageOptions:
    backend: str = "local"           # local | sqlite
    base_dir: Path | str = ""        # 存储根目录
    database_url: str = ""           # sqlite:///path/to/novels.db

@dataclass
class ExportOptions:
    format: str = ""
    output_path: Path | str = ""
    enabled: bool = True
    file_name_template: str = "{name}"

@dataclass
class Options:
        _mode: str = "api"
        _requests: RequestsOptions = field(default_factory=RequestsOptions)
        _browser: BrowserOptions = field(default_factory=BrowserOptions)
        _api: APIOptions = field(default_factory=APIOptions)
        _storage: StorageOptions | None = None
        _export: ExportOptions | None = None

        def set_mode(self, mode: Literal["api", "browser", "requests"]) -> "Options":
            self._mode = mode
            return self

        def set_api_options(self,
                            name: str,
                            delay: Sequence[float] = (3, 5),
                            timeout: float = 30,
                            retry_times: int = 3,
                            backoff_factor: float = 2,
                            key: str | None = None,
                            params: dict[str, str] | None = None) -> "Options":
            self._api = APIOptions(name=name, delay=tuple(delay), timeout=timeout,
                                   retry_times=retry_times,
                                   backoff_factor=backoff_factor, key=key, params=params)
            return self

        def set_requests_options(self,
                                  headers: dict | None = None,
                                  delay: Sequence[float] = (3, 5),
                                  timeout: float = 30,
                                  retry_times: int = 3,
                                  backoff_factor: float = 2,
                                  cookies: dict[str, str] | None = None,
                                  proxies: dict[str, str] | None = None) -> "Options":
            if headers is None:
                headers = {"User-Agent": "Mozilla/5.0 ..."}
            self._requests = RequestsOptions(headers=headers, delay=tuple(delay), timeout=timeout,
                                             retry_times=retry_times, backoff_factor=backoff_factor,
                                             cookies=cookies, proxies=proxies)
            return self

        def set_browser_options(self,
                                browser_type: str = "chromium",
                                delay: Sequence[float] = (3, 5),
                                timeout: float = 30,
                                retry_times: int = 3,
                                backoff_factor: float = 2,
                                headless: bool = False,
                                user_data_dir: Path | str | None = None,
                                viewport: dict[str, int] | None = None,
                                extra_args: list[str] | None = None,
                                auto_reconnect: bool = False) -> "Options":
            self._browser = BrowserOptions(browser_type=browser_type, delay=tuple(delay), timeout=timeout, retry_times=retry_times,
                                           backoff_factor=backoff_factor, headless=headless,
                                           user_data_dir=user_data_dir, viewport=viewport,
                                           extra_args=extra_args, auto_reconnect=auto_reconnect)
            return self


        def set_storage_options(self, backend: str = "local",
                                base_dir: Path | str = "",
                                database_url: str = "") -> "Options":
            self._storage = StorageOptions(backend=backend, base_dir=base_dir,
                                           database_url=database_url)
            return self

        def set_export(self, options: ExportOptions) -> "Options":
            self._export = options
            return self

        def enable_export(self, enabled: bool = True) -> "Options":
            if self._export:
                self._export.enabled = enabled
            return self

        @property
        def mode(self) -> str: return self._mode

        @property
        def api(self) -> APIOptions: return self._api

        @property
        def requests(self) -> RequestsOptions: return self._requests

        @property
        def browser(self) -> BrowserOptions: return self._browser

        @property
        def storage(self) -> StorageOptions | None: return self._storage

        @property
        def export(self) -> ExportOptions | None: return self._export
