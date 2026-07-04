import json
import os
import shutil
from pathlib import Path
from typing import Iterator, Sequence

from .options import StorageOptions
from ..models.novel import Novel, Chapter, Chapters
from ..utils.logger import get_logger

_log = get_logger("nldlder.core.storage")


class LocalStorage:
    """
    本地小说数据存储管理器。

    维护以下目录结构：
        base_dir/
            {novel_id}/
                meta.json          # 小说元数据
                chapters/
                    id1.json     # 每章独立文件
                    id2.json
                    ...

    每个章节文件内容格式：
        {
            "id": "章节ID",
            "url": "章节URL",
            "title": "章节标题",
            "order": 1(章节序号),
            "volume": "章节所属卷名",
            "content": "清洗后的正文文本",
            "time": 1234567890.123(更新时间),
            "count": "章节字数",
            "is_complete": True(章节是否完整),
            "images": [](章节插图)
        }
    """

    def __init__(self, config: StorageOptions | Path | str):
        if isinstance(config, StorageOptions):
            self.base_dir = Path(config.base_dir)
        else:
            self.base_dir = Path(config)

    def get_novel_dir(self, novel_id: str) -> Path:
        """返回某部小说的存储目录。"""
        return self.base_dir / novel_id

    def get_meta_path(self, novel_id: str) -> Path:
        return self.get_novel_dir(novel_id) / "meta.json"

    def get_chapters_path(self, novel_id: str) -> Path:
        return self.get_novel_dir(novel_id) / "chapters"

    def get_chapter_path(self, novel_id: str, chapter_id: str) -> Path:
        return self.get_novel_dir(novel_id) / "chapters" / f"{chapter_id}.json"

    def save_meta(self, novel: Novel) -> Path:
        """保存小说元数据（标题、作者、封面等），返回写入的文件路径。"""
        _log.debug("save_meta: id=%s", novel.id)
        path = self.get_meta_path(novel.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "title": novel.title,
            "url": novel.url,
            "id": novel.id,
            "serial": novel.serial,
            "author": novel.author,
            "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None,
            "count": novel.count,
            "cover": novel.cover.to_json() if novel.cover else None,
        }
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return path

    def load_meta(self, novel_id: str) -> Novel | None:
        """加载小说元数据，返回Novel或 None。"""
        path = self.get_meta_path(novel_id)
        if not path.exists():
            return None
        json_data = json.loads(path.read_text(encoding="utf-8"))
        novel = Novel.loads(**json_data)
        return novel

    def iter_metas(self) -> Iterator[Novel]:
        """遍历所有小说的元数据，一次 yield 一个 Novel。

        ponytail: load_chapters 全量加载 N 章 → N 个对象同时驻留。
        此方法逐个 yield，O(1) 内存。
        """
        if not self.base_dir.exists():
            return
        for entry in sorted(self.base_dir.iterdir()):
            if not entry.is_dir():
                continue
            meta_path = entry / "meta.json"
            if not meta_path.exists():
                continue
            try:
                json_data = json.loads(meta_path.read_text(encoding="utf-8"))
                yield Novel.loads(**json_data)
            except (json.JSONDecodeError, KeyError, TypeError):
                _log.warning("跳过损坏的 meta 文件: %s", meta_path)

    # ---------- 章节操作 ----------
    def save_chapter(self, novel: Novel, chapters: Sequence[Chapter] | Chapter) -> list[Path]:
        """保存章节内容（立即写入磁盘），返回写入的文件路径列表。"""
        if isinstance(chapters, Chapter):
            chapters = [chapters]

        saved = []
        for chapter in chapters:
            path = self.get_chapter_path(novel.id, chapter.id)
            path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "id": chapter.id,
                "url": chapter.url,
                "title": chapter.title,
                "order": chapter.order,
                "volume": chapter.volume,
                "content": chapter.content,
                "time": chapter.time,
                "count": chapter.count,
                "is_complete": chapter.is_complete,
                "images": [image.to_json() for image in chapter.images],
            }
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            saved.append(path)
        return saved

    def load_chapter(self,
                     novel_id: str,
                     chapter_id: str,
                     index_url: str | None = None) -> Chapter | None:
        """读取单个章节的保存数据，不存在时返回 None。"""
        if index_url is None:
            novel = self.load_meta(novel_id)
            if novel is None:
                return None
            index_url = novel.url

        path = self.get_chapter_path(novel_id=novel_id, chapter_id=chapter_id)
        if not path.exists():
            return None
        json_data = json.loads(path.read_text(encoding="utf-8"))
        json_data["index_url"] = index_url
        return Chapter.loads(**json_data)

    def load_chapters(self, novel_id: str) -> Chapters:
        """读取所有章节的保存数据，元数据或 chapters 目录不存在时返回空 Chapters。"""
        return Chapters(self.iter_chapters(novel_id))

    def iter_chapters(self, novel_id: str) -> Iterator[Chapter]:
        """逐章 yield，O(1) 内存。

        meta 只加载一次取 index_url。损坏的章节文件跳过并 warning。
        """
        path = self.get_chapters_path(novel_id=novel_id)
        if not path.exists():
            return

        novel = self.load_meta(novel_id)
        if novel is None:
            return

        index_url = novel.url
        for file in path.glob("*.json"):
            try:
                chapter = self.load_chapter(
                    novel_id=novel_id, chapter_id=file.stem,
                    index_url=index_url,
                )
                if chapter is not None:
                    yield chapter
            except (json.JSONDecodeError, KeyError, TypeError):
                _log.warning("跳过损坏的章节文件: %s", file)


    def delete_chapter(self, novel_id: str, chapter_id: str) -> None:
        """删除单个章节文件。"""
        path = self.get_chapter_path(novel_id=novel_id, chapter_id=chapter_id)
        if path.exists():
            os.remove(path)

    def delete_chapters(self, novel_id: str) -> None:
        """删除某部小说的所有章节（递归删除 chapters 目录）。"""
        path = self.get_chapters_path(novel_id=novel_id)
        if path.exists():
            shutil.rmtree(path)

    def delete_meta(self, novel_id: str) -> None:
        """删除小说元数据文件。"""
        path = self.get_meta_path(novel_id=novel_id)
        if path.exists():
            os.remove(path)

    def delete_novel_dir(self, novel_id: str) -> None:
        """删除某部小说的存储目录（含 meta + chapters + 空目录）。"""
        path = self.get_novel_dir(novel_id=novel_id)
        if path.exists():
            shutil.rmtree(path)

    def delete_novel(self, novel_id: str) -> None:
        """彻底删除某部小说的所有本地数据（元数据 + 章节 + 目录）。

        安全删除：如果 storage 目录下还有其他小说，仅删除该小说的目录。
        """
        _log.info("delete_novel: id=%s", novel_id)
        self.delete_novel_dir(novel_id)