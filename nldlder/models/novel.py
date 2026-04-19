from __future__ import annotations
import threading
from collections.abc import Iterable
from dataclasses import dataclass, field
from base64 import b64encode, b64decode
from typing import Any, Sequence, Iterator

threading_lock = threading.Lock()


@dataclass
class Illustration:
    raw_data: bytes
    alt: str | None = None
    insert: int | None = None
    url: str | None = None

    def __hash__(self):
        return hash(self.raw_data)

    def to_json(self) -> dict[str, Any]:
        return {
            "raw_data": b64encode(self.raw_data).decode(),
            "alt": self.alt,
            "insert": self.insert,
            "url": self.url,
        }

    @staticmethod
    def loads(raw_data: bytes | str,
              alt: str | None = None,
              insert: int | None = None,
              url: str | None = None,
              **kwargs
              ) -> Illustration:
        if isinstance(raw_data, str):
            raw_data = b64decode(raw_data)
        illustration = Illustration(raw_data=raw_data, alt=alt, insert=insert, url=url)
        for k, v in kwargs.items():
            setattr(illustration, k, v)
        return illustration

class Chapters(Sequence):

    def __init__(self, chapters: Chapter | Sequence[Chapter] = None) -> None:
        if chapters is None:
            self._chapters = tuple()
        else:
            self._chapters = tuple(chapters) if isinstance(chapters, Sequence) else (chapters, )
        self._chapters: tuple[Chapter, ...] = tuple(sorted(self._chapters, key=lambda chapter: chapter.order))
        self._by_id = {ch.order: ch for ch in self._chapters}
        self._by_url = {ch.url: ch for ch in self._chapters}
        self._by_order = {ch.order: ch for ch in self._chapters}

    def __getitem__(self, index: int) -> Chapter:
        return self._chapters[index]

    def __len__(self) -> int:
        return len(self._chapters)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Chapter):
            return item in self._chapters
        return False

    def __repr__(self) -> str:
        return f"Chapters({len(self)} items)"

    def __iter__(self) -> Iterator[Chapter]:
        return iter(self._chapters)

    def __eq__(self, other):
        return self._chapters == getattr(other, "chapters", other)

    def __hash__(self):
        return hash(self._chapters)

    def get_chapter_by_id(self, order: int) -> Chapter | None:
        """根据章节序号（从1开始）获取章节"""
        return self._by_id.get(order)

    def get_chapter_by_url(self, url: str) -> Chapter | None:
        """根据章节 URL 获取章节"""
        return self._by_url.get(url)

    def get_chapter_by_order(self, order: int) -> Chapter | None:
        return self._by_order.get(order)

    def get_incompleted_chapters(self) -> Chapters | None:
        """获取不完整的章节"""
        target_chapters = [chapter for chapter in self._chapters if not chapter.is_complete]
        if not target_chapters:
            return None
        else:
            return Chapters(target_chapters)

    # 可选的便利方法
    @property
    def total(self) -> int:
        return len(self)

    @property
    def chapters(self) -> tuple[Chapter, ...]:
        return self._chapters

@dataclass
class Chapter:
    id: str
    url: str
    index_url: str
    title: str
    order: int
    volume: str | None = None
    content: str | None = None
    time: float | None = None
    count: int | None = None
    is_complete: bool = False
    images: Sequence[Illustration] = field(default_factory=tuple)

    @staticmethod
    def loads(id: str,
              url: str,
              index_url: str,
              title: str,
              order: int,
              volume: str = None,
              content: str = None,
              time: float = None,
              count: int = None,
              is_complete: bool = False,
              images: Sequence[dict] = tuple(),
              **kwargs
              ) -> Chapter:

        images = [Illustration.loads(**image) for image in images]
        chapter =  Chapter(id=id, url=url, index_url=index_url, title=title, order=order,
                           volume=volume, content=content, time=time, count=count, is_complete=is_complete,
                           images=tuple(images))
        for k, v in kwargs.items():
            setattr(chapter, k, v)
        return chapter

    def __eq__(self, other):
        if not isinstance(other, Chapter):
            return NotImplemented
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

@dataclass
class Novel:
    name: str
    url: str
    id: str
    serial: int
    author: str
    description: str
    tags: Sequence[str] | None = None
    count: int | None = None
    rating: float | None = None
    cover: Illustration | None = None
    chapters: Chapters = field(default_factory=Chapters)

    @staticmethod
    def loads(name: str, url: str, id: str, serial: int, author: str, description: str,
              tags: Sequence[str], count: int, rating: float, cover: dict | None = None,
              chapters: Sequence[dict] = tuple(), **kwargs
              ) -> Novel:
        cover = Illustration.loads(**cover) if cover else None
        chapters = Chapters([Chapter.loads(**chapter) for chapter in chapters])
        novel = Novel(name=name, url=url,id=id, serial=serial, author=author, description=description,
                     tags=tags,count=count, rating=rating, cover=cover, chapters=chapters)
        for k, v in kwargs.items():
            setattr(novel, k, v)
        return novel


    def update_chapter(self, chapter: Chapter | Iterable[Chapter]) -> None:
        if isinstance(chapter, Chapter):
            incoming = (chapter,)
        else:
            incoming = tuple(chapter)

        with threading_lock:
            merged = {}
            for c in self.chapters:
                merged[c.id] = c
            for c in incoming:
                merged[c.id] = c
            self.chapters = Chapters(list(merged.values()))

@dataclass
class SearchResult:
    name: str
    author: str
    url: str | None = None
    description: str | None = None
