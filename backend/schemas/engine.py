"""引擎相关 Pydantic 模型。"""
from pydantic import BaseModel


class APIOptionsData(BaseModel):
    name: str
    delay: tuple[float, float] = (3.0, 5.0)
    timeout: float = 30
    retry_times: int = 3
    backoff_factor: float = 2
    key: str | None = None
    params: dict[str, str] | None = None


class RequestsOptionsData(BaseModel):
    headers: dict[str, str] = {"User-Agent": "Mozilla/5.0 ..."}
    delay: tuple[float, float] = (3.0, 5.0)
    timeout: float = 30
    retry_times: int = 3
    backoff_factor: float = 2
    cookies: dict[str, str] | None = None
    proxies: dict[str, str] | None = None


class BrowserOptionsData(BaseModel):
    browser_type: str = "chromium"
    delay: tuple[float, float] = (3.0, 5.0)
    timeout: float = 30
    retry_times: int = 3
    backoff_factor: float = 2
    headless: bool = False
    user_data_dir: str | None = None
    viewport: dict[str, int] | None = None
    extra_args: list[str] | None = None
    auto_reconnect: bool = False


class CreateEngineRequest(BaseModel):
    mode: str = "api"
    platform: str = ""
    api: APIOptionsData | None = None
    requests: RequestsOptionsData | None = None
    browser: BrowserOptionsData | None = None


class UpdateEngineRequest(BaseModel):
    mode: str
    api: APIOptionsData | None = None
    requests: RequestsOptionsData | None = None
    browser: BrowserOptionsData | None = None