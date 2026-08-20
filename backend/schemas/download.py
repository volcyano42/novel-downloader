"""下载相关 Pydantic 模型。"""
from pydantic import BaseModel


class SearchResultData(BaseModel):
    title: str
    author: str
    url: str
    description: str | None = None
    platform: str = ""
    cover_url: str | None = None
    extra: dict | None = None


class FetchMetaRequest(BaseModel):
    url: str


class DownloadChapterRequest(BaseModel):
    id: str
    url: str
    novel_id: str
    title: str
    order: int
    volume: str | None = None
