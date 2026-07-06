from __future__ import annotations

from base64 import b64encode, b64decode
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Sequence, Iterator
from urllib.parse import urlparse, urlunparse


def normalize_url(url: str) -> str:
    """规范化 URL：去掉末尾斜杠、统一小写 scheme 和 host。

    不改变路径大小写（部分站点路径区分大小写）。
    """
    if not url:
        return url
    parsed = urlparse(url)
    # 去掉末尾 /
    path = parsed.path.rstrip("/") or "/"
    # 统一 scheme 和 host 为小写
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=path,
    )
    return urlunparse(normalized)


_IMAGE_SIGNATURES: list[tuple[bytes, str]] = [
    (b'\x89PNG\r\n\x1a\n', "png"),
    (b'\xff\xd8', "jpeg"),
    (b'\x00\x00\x00\x0c', "jpeg"),         # JPEG 变体
    (b'RIFF', "webp"),                      # 需二次校验
    (b'GIF87a', "gif"),
    (b'GIF89a', "gif"),
    (b'BM', "bmp"),
    (b'MM\x00*', "tiff"),                  # TIFF big-endian
    (b'II*\x00', "tiff"),                  # TIFF little-endian
    (b'\x00\x00\x00 ftyp', "heic"),        # HEIC / HEIF
    (b'\x00\x00\x00\x18ftyp', "heic"),
    (b'\x00\x00\x00\x1cftyp', "heic"),
    (b'\x00\x00\x00 ftyp', "heif"),
]

@dataclass
class Illustration:
    raw_data: bytes
    alt: str | None = None
    insert: int | None = None
    url: str | None = None
    owner_id: str | None = None   # novel_id 或 chapter_id，用于数据库索引

    def __hash__(self):
        return hash(self.raw_data)

    @property
    def image_format(self) -> str | None:
        """魔数推导图片格式"""
        for magic, fmt in _IMAGE_SIGNATURES:
            if self.raw_data.startswith(magic):
                if magic == b'RIFF' and b'WEBP' not in self.raw_data[:12]:
                    continue
                return fmt
        return None

    def convert(self, target_format: str, quality: int | None = None) -> Illustration:
        """转换为目标图片格式，返回新的 Illustration 对象。

        Args:
            target_format: \"jpeg\" / \"png\" / \"gif\" / \"webp\" / \"bmp\" / \"tiff\" / \"heic\"
            quality: 输出质量，1-100。None 时使用格式默认值。
                     为 0 时不转换。

        Returns:
            转换后的新 Illustration。raw_data 为空或 Pillow 无法识别时返回自身。
        """
        if quality == 0 or not self.raw_data:
            return self

        try:
            from io import BytesIO
            from PIL import Image

            from pillow_heif import register_heif_opener
            register_heif_opener()

            src = Image.open(BytesIO(self.raw_data))
            buf = BytesIO()
            save_kwargs: dict[str, Any] = {}

            if target_format == "jpeg":
                if src.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", src.size, (255, 255, 255))
                    mask = src.split()[-1] if src.mode == "RGBA" else None
                    bg.paste(src, mask=mask)
                    src = bg
                if quality is not None:
                    save_kwargs["quality"] = max(1, min(100, quality))
            elif target_format == "webp" and quality is not None:
                save_kwargs["quality"] = max(1, min(100, quality))

            src.save(buf, format=target_format.upper(), **save_kwargs)
            return Illustration(raw_data=buf.getvalue(), alt=self.alt,
                                insert=self.insert, url=self.url)
        except Exception as e:
            import logging
            logging.getLogger("nldlder.models.novel").warning(
                "Illustration.convert(%s) 失败: %s", target_format, e)
            return self

    def to_json(self) -> dict[str, Any]:
        return {
            "raw_data": b64encode(self.raw_data).decode(),
            "alt": self.alt,
            "insert": self.insert,
            "url": self.url,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_data": self.raw_data,
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

    def __init__(self, chapters: Chapter | Iterable[Chapter] | None = None) -> None:
        if chapters is None:
            raw: tuple[Chapter, ...] = ()
        elif isinstance(chapters, Iterable):
            raw = tuple(chapters)
        else:
            raw = (chapters,)
        self._chapters: tuple[Chapter, ...] = tuple(sorted(raw, key=lambda chapter: chapter.order))

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

    @property
    def chapters(self) -> tuple[Chapter, ...]:
        """返回内部章节元组（兼容旧代码）。"""
        return self._chapters

    def __iter__(self) -> Iterator[Chapter]:
        return iter(self._chapters)

    def __eq__(self, other):
        return self._chapters == getattr(other, "chapters", other)

    def __hash__(self):
        return hash(self._chapters)

    def get_chapter_by_id(self, chapter_id: str) -> Chapter | None:
        """根据章节 ID 获取章节"""
        for ch in self._chapters:
            if ch.id == chapter_id:
                return ch
        return None

    def get_chapter_by_url(self, url: str) -> Chapter | None:
        """根据章节 URL 获取章节"""
        for ch in self._chapters:
            if ch.url == url:
                return ch
        return None

    def get_chapter_by_order(self, order: int) -> Chapter | None:
        for ch in self._chapters:
            if ch.order == order:
                return ch
        return None

    def merge(self, other: Chapter | Iterable[Chapter]) -> Chapters:
        """合并章节，按 id 去重（other 覆盖已存在的同名章节）。

        返回新的 Chapters 对象，不修改自身。

        Args:
            other: 要合并的章节（单个或可迭代对象）。

        Returns:
            合并后的新 Chapters 实例。
        """
        if isinstance(other, Chapter):
            other = (other,)

        merged = {
            c.id: c
            for c in self._chapters
        }
        for c in other:
            merged[c.id] = c

        return Chapters(list(merged.values()))

    def get_chapters_by_volume_name(self, name: str) -> Chapters:
        """按卷名筛选章节，返回新 Chapters 对象。"""
        return Chapters(
            ch for ch in self._chapters
            if ch.volume == name
        )
    @property
    def completed_chapters(self) -> Chapters | None:
        """获取完整的章节"""
        target_chapters = [chapter for chapter in self._chapters if chapter.is_complete]
        if not target_chapters:
            return None
        else:
            return Chapters(target_chapters)

    @property
    def incompleted_chapters(self) -> Chapters | None:
        """获取不完整的章节"""
        target_chapters = [chapter for chapter in self._chapters if not chapter.is_complete]
        if not target_chapters:
            return None
        else:
            return Chapters(target_chapters)

    @property
    def volumes(self) -> dict[None | str, Chapters]:
        """按卷分组。

        返回 {卷名: Chapters} 字典。
        """
        volumes: dict[str | None, list[Chapter]] = {}

        for ch in self._chapters:
            volume_name = ch.volume

            if volume_name not in volumes.keys():
                volumes[volume_name] = [ch]
            else:
                volumes[volume_name].append(ch)

        volumes: dict[None | str, Chapters] = {k:Chapters(v) for k,v in volumes.items()}
        return volumes

    @property
    def total(self) -> int:
        return len(self)

@dataclass
class Chapter:
    id: str
    url: str
    novel_id: str
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
              novel_id: str,
              title: str,
              order: int,
              volume: str | None = None,
              content: str | None = None,
              time: float| None = None,
              count: int | None = None,
              is_complete: bool = False,
              images: Sequence[dict] = tuple(),
              **kwargs
              ) -> Chapter:

        images = [Illustration.loads(**image) for image in images]
        chapter =  Chapter(id=id, url=url, novel_id=novel_id, title=title, order=order,
                           volume=volume, content=content, time=time, count=count, is_complete=is_complete,
                           images=tuple(images))
        for k, v in kwargs.items():
            setattr(chapter, k, v)
        return chapter

    def __eq__(self, other: object):
        if not isinstance(other, Chapter):
            return NotImplemented
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

@dataclass
class Novel:
    title: str
    url: str
    id: str
    serial: int
    author: str
    description: str
    tags: Sequence[str] | None = None
    count: int | None = None
    cover: Illustration | None = None
    chapters: Chapters = field(default_factory=Chapters)

    @staticmethod
    def loads(title: str, url: str, id: str, serial: int, author: str, description: str,
              tags: Sequence[str] | None = None, count: int | None = None, cover: dict | None = None,
              chapters: Sequence[dict] = tuple(), **kwargs
              ) -> Novel:
        cover = Illustration.loads(**cover) if cover else None
        chapters = Chapters([Chapter.loads(**chapter) for chapter in chapters])
        novel = Novel(title=title, url=url,id=id, serial=serial, author=author, description=description,
                     tags=tags,count=count, cover=cover, chapters=chapters)
        for k, v in kwargs.items():
            setattr(novel, k, v)
        return novel


    def update_chapter(self, chapter: Chapter | Iterable[Chapter]) -> None:
        self.chapters = self.chapters.merge(chapter)

@dataclass
class SearchResult:
    title: str
    author: str
    url: str | None = None
    description: str | None = None
