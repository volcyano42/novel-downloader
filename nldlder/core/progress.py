from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json
import time
import threading
from typing import Sequence
from models.novel import Chapter

@dataclass
class DownloadProgress:
    novel_url: str
    downloaded_chapters_id: set[str] = field(default_factory=set)
    last_update: float = 0.0

    @classmethod
    def load(cls, path: Path) -> DownloadProgress | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["downloaded_chapters_id"] = set(data.get("downloaded_chapters_id", []))
            return cls(**data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def add_downloaded_chapter_id(self, chapters: Sequence[Chapter]) -> None:
        with threading.Lock():
            for chapter in chapters:
                self.downloaded_chapters_id.add(chapter.id)

    def update_timestamp(self):
        self.last_update = time.time()

    def save(self, path: Path):
        data = asdict(self)
        data["downloaded_chapters_id"] = list(self.downloaded_chapters_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
