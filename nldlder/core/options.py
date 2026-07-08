from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence, Literal

from ..utils.logger import LogOptions


@dataclass
class APIOptions:
    enabled: bool = True
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

@dataclass
class StorageOptions:
    backend: str = "local"           # local | sqlite | postgresql
    base_dir: Path | str = ""        # local 模式：JSON 文件根目录
    database_url: str = ""           # 数据库连接字符串
                                     #   sqlite:///path/to/novels.db
                                     #   postgresql://user:pass@host:5432/dbname

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
        _log: LogOptions = field(default_factory=LogOptions)
        _exports: dict[str, ExportOptions] = field(default_factory=dict)

        def set_mode(self, mode: Literal["api", "browser", "requests"]) -> "Options":
            self._mode = mode
            return self

        def set_api_options(self,
                            name: str,
                            enabled: bool = True,
                            delay: Sequence[float] = (3, 5),
                            timeout: float = 30,
                            retry_times: int = 3,
                            backoff_factor: float = 2,
                            key: str | None = None,
                            params: dict[str, str] | None = None) -> "Options":
            self._api = APIOptions(enabled=enabled, name=name, delay=tuple(delay), timeout=timeout,
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
                                viewport: dict[str, int] | None = None) -> "Options":
            self._browser = BrowserOptions(browser_type=browser_type, delay=tuple(delay), timeout=timeout, retry_times=retry_times,
                                           backoff_factor=backoff_factor, headless=headless,
                                           user_data_dir=user_data_dir, viewport=viewport)
            return self


        def set_storage_options(self, backend: str = "local",
                                base_dir: Path | str = "",
                                database_url: str = "") -> "Options":
            self._storage = StorageOptions(backend=backend, base_dir=base_dir,
                                           database_url=database_url)
            return self

        def set_log_options(self,
                            enabled: bool = True,
                            output_dir: str | None = None,
                            level: str = "DEBUG") -> "Options":
            self._log = LogOptions(enabled=enabled, output_dir=output_dir, level=level)
            return self

        def set_export_options(self, options: ExportOptions) -> "Options":
            self._exports[options.format] = options
            return self

        def enable_format(self, name: str, enabled: bool = True) -> "Options":
            self._exports[name].enabled = enabled
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
        def log(self) -> LogOptions: return self._log

        @property
        def exports(self) -> dict[str, ExportOptions]:return self._exports

