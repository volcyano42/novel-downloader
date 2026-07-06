"""Pydantic 模型 — 与 api-routes.md 请求/响应体一一对应。"""
from pydantic import BaseModel

class BackendSwitch(BaseModel):
    backend: str

class CoverData(BaseModel):
    raw_data: str | None = None
    alt: str | None = None
    url: str | None = None
    format: str | None = None

class NovelMeta(BaseModel):
    title: str
    url: str
    id: str
    serial: int
    author: str
    description: str
    tags: list[str] | None = None
    count: int | None = None
    cover: CoverData | None = None

class ImageData(BaseModel):
    raw_data: str | None = None
    alt: str | None = None
    insert: int | None = None
    url: str | None = None

class ChapterData(BaseModel):
    id: str
    url: str
    novel_id: str
    title: str
    order: int
    volume: str | None = None
    content: str | None = None
    time: float | None = None
    count: int | None = None
        images: list[ImageData] = []

class ChapterBrief(BaseModel):
    id: str
    url: str
    novel_id: str
    title: str
    order: int
    volume: str | None = None
    count: int | None = None

class SearchResultData(BaseModel):
    title: str
    author: str
    url: str
    description: str | None = None

class FetchMetaRequest(BaseModel):
    url: str
    engine_id: str

class DownloadChapterRequest(BaseModel):
    id: str
    url: str
    novel_id: str
    title: str
    order: int
    volume: str | None = None
    volume: str | None = None

class TXTExportOptions(BaseModel):
    enabled: bool = True
    output_path: str = "app_data/exports/{name}"
    file_name_template: str = "{name}"
    encoding: str = "utf-8"

class EPUBExportOptions(BaseModel):
    enabled: bool = True
    output_path: str = "app_data/exports/{name}"
    file_name_template: str = "{name}"
    encoding: str = "utf-8"
    css_style: str = "default"
    include_toc: bool = True
    compression: str = "deflate"
    compresslevel: int = 9
    optimize_images: bool = True
    jpeg_quality: int = 85
    max_image_width: int = 0

class IMGExportOptions(BaseModel):
    enabled: bool = True
    output_path: str = "app_data/exports/{name}"
    file_name_template: str = "{n}"
    output_format: str = "original"

class ExportRequest(BaseModel):
    novel_id: str
    chapter_id: list[str] | None = None
    txt: TXTExportOptions | None = None
    epub: EPUBExportOptions | None = None
    img: IMGExportOptions | None = None

class ExportTaskStatus(BaseModel):
    task_id: str
    status: str
    progress: float = 0.0

class APIOptionsData(BaseModel):
    name: str
    enabled: bool = True
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

class CreateEngineRequest(BaseModel):
    mode: str = "api"
    api: APIOptionsData | None = None
    requests: RequestsOptionsData | None = None
    browser: BrowserOptionsData | None = None
