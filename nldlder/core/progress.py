from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from ..models.novel import Chapter, Chapters


@dataclass
class DownloadProgress:
    total_chapters: Chapters = field(default_factory=Chapters)
    downloaded_chapters: Chapters = field(default_factory=Chapters)
    failed_chapters: Chapters = field(default_factory=Chapters)
    last_update: float = 0.0

    def set_total(self, chapters: Chapter | Iterable[Chapter]) -> None:
        """设置总章节列表。"""
        self.total_chapters = Chapters(chapters)

    @property
    def remaining(self) -> int:
        """剩余未完成的章节数。"""
        return len(self.total_chapters) - len(self.downloaded_chapters) - len(self.failed_chapters)

    def add_downloaded(self, chapters: Chapter | Iterable[Chapter]) -> None:
        """记录成功下载的章节。"""
        self.downloaded_chapters = self.downloaded_chapters.merge(chapters)

    def add_failed(self, chapters: Chapter | Iterable[Chapter]) -> None:
        """记录下载失败的章节。"""
        self.failed_chapters = self.failed_chapters.merge(chapters)

    def update_timestamp(self):
        self.last_update = time.time()
