"""存储相关 Pydantic 模型。"""
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
    extra: dict | None = None


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
    downloaded: bool = False
    image_count: int = 0
