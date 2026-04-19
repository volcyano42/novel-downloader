from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence, Literal
from box import Box

@dataclass
class APIOptions:
    enabled: bool = True
    delay: Sequence[float] = (3, 5)
    timeout: float = 30
    retry_times: int = 3
    batch_size: int = 3
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
    page_count: int | None = None
    user_data_dir: Path | str | None = None
    storage_state_path: Path | str | None = None
    viewport: dict[str, int] | None = field(default_factory=lambda: {"width": 1280, "height": 720})

@dataclass
class DownloadOptions:
    max_workers: int = 5

@dataclass
class ExportOptions:
    output_dir: Path | str
    enabled: bool = True
    group: str = "default"
    file_name_template: str = "{name}"
    extension: str = "default"

@dataclass
class Options:
        _mode: str = "api"
        _requests: RequestsOptions = RequestsOptions()
        _browser: BrowserOptions = BrowserOptions()
        _api: APIOptions = APIOptions()
        _download: DownloadOptions = DownloadOptions()
        _storage: Path | str | None = None
        _exports: Box = field(default_factory=Box)

        # 链式设置方法
        def set_mode(self, mode: Literal["api", "browser", "requests"]) -> "Options":
            self._mode = mode
            return self

        def set_api_options(self, **kwargs) -> "Options":
            self._api = APIOptions(**kwargs)
            return self

        def set_requests_options(self, **kwargs) -> "Options":
            self._requests = RequestsOptions(**kwargs)
            return self

        def set_browser_options(self, **kwargs) -> "Options":
            self._browser = BrowserOptions(**kwargs)
            return self

        def set_download_options(self, **kwargs) -> "Options":
            self._download = DownloadOptions(**kwargs)
            return self

        def set_export_options(self, name: str, options) -> "Options":
            self._exports[name] = options
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
        def exports(self) -> dict[str, ExportOptions]:return self._exports

        @property
        def storage(self) -> Path | str | None: return self._storage
