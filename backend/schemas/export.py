"""导出相关 Pydantic 模型。"""
from pydantic import BaseModel


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
    formats: list[str] | None = None
    path: str | None = None
    error: str | None = None
