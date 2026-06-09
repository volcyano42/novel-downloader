from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence, Literal, Any

from ..utils.logger import LogOptions


@dataclass
class APIOptions:
    enabled: bool = True
    name: str | None = None
    delay: Sequence[float] = (3, 5)
    timeout: float = 30
    retry_times: int = 3
    batch_size: int = 1
    backoff_factor: float = 2
    key: str | None = None
    params: dict[str, str] | None = None

@dataclass
class RequestsOptions:
    headers: dict = field(default_factory=lambda: {"User-Agent": "Mozilla/5.0 ..."})
    delay: Sequence[float] = (3, 5)
    timeout: float = 30
    retry_times: int = 3
    backoff_factor: float = 2
    cookies: dict[str, str] | None = None
    proxies: dict[str, str] | None = None

@dataclass
class BrowserOptions:
    browser_type: str = "chromium"
    delay: Sequence[float] = (3, 5)
    timeout: float = 30
    retry_times: int = 3
    backoff_factor: float = 2
    headless: bool = False
    user_data_dir: Path | str | None = None
    viewport: dict[str, int] | None = None

@dataclass
class DownloadOptions:
    max_workers: int = 3

@dataclass
class ExportOptions:
    output_path: Path | str
    enabled: bool = True
    file_name_template: str = "{name}"
    extension: str = "default"

@dataclass
class Options:
        _mode: str = "api"
        _requests: RequestsOptions = field(default_factory=RequestsOptions)
        _browser: BrowserOptions = field(default_factory=BrowserOptions)
        _api: APIOptions = field(default_factory=APIOptions)
        _download: DownloadOptions = field(default_factory=DownloadOptions)
        _log: LogOptions = field(default_factory=LogOptions)
        _exports: dict[str, Any] = field(default_factory=dict)

        def set_mode(self, mode: Literal["api", "browser", "requests"] | str) -> "Options":
            self._mode = mode
            return self

        def set_api_options(self, **kwargs) -> "Options":
            self._api = APIOptions(**kwargs)
            return self

        def set_requests_options(self, **kwargs) -> "Options":
            self._requests = RequestsOptions(**kwargs)
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
            self._browser = BrowserOptions(browser_type=browser_type, delay=delay, timeout=timeout, retry_times=retry_times,
                                           backoff_factor=backoff_factor, headless=headless,
                                           user_data_dir=user_data_dir, viewport=viewport)
            return self

        def set_download_options(self, max_workers: int) -> "Options":
            self._download = DownloadOptions(max_workers=max_workers)
            return self

        def set_log_options(self, **kwargs) -> "Options":
            self._log = LogOptions(**kwargs)
            return self

        def set_export_options(self, options) -> "Options":
            self._exports[options.format] = options
            return self

        def enable_format(self, name: str, enabled: bool = True, **extra) -> "Options":
            self._exports[name].enabled = enabled
            export_options = self._exports[name]
            for k, v in extra.items():
                if hasattr(export_options, k):
                    setattr(export_options, k, v)
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
        def download(self) -> DownloadOptions: return self._download

        @property
        def log(self) -> LogOptions: return self._log

        @property
        def exports(self) -> dict[str, ExportOptions]:return self._exports

