import json
import os
from pathlib import Path
from typing import Sequence

from models.novel import Novel, Chapter, Chapters
from core.progress import DownloadProgress


class Storage:
    """
    小说数据存储管理器。

    维护以下目录结构：
        base_dir/
            {novel_id}/
                meta.json          # 小说元数据
                progress.json      # 下载进度
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

    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir)

    def get_novel_dir(self, novel_id: str) -> Path:
        """返回某部小说的存储目录。"""
        return self.base_dir / novel_id

    def get_meta_path(self, novel_id: str) -> Path:
        return self.get_novel_dir(novel_id) / "meta.json"

    def get_progress_path(self, novel_id: str) -> Path:
        return self.get_novel_dir(novel_id) / "progress.json"

    def get_chapters_path(self, novel_id: str) -> Path:
        return self.get_novel_dir(novel_id) / "chapters"

    def get_chapter_path(self, novel_id: str, chapter_id: str) -> Path:
        return self.get_novel_dir(novel_id) / "chapters" / f"{chapter_id}.json"

    def save_meta(self, novel: Novel):
        """保存小说元数据（标题、作者、封面等）。"""
        path = self.get_meta_path(novel.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": novel.name,
            "url": novel.url,
            "id": novel.id,
            "serial": novel.serial,
            "author": novel.author,
            "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None,
            "count": novel.count,
            "rating": novel.rating,
            "cover": novel.cover.to_json() if novel.cover else None,
        }
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def load_meta(self, novel_id: str) -> Novel | None:
        """加载小说元数据，返回Novel或 None。"""
        path = self.get_meta_path(novel_id)
        if not path.exists():
            return None
        json_data = json.loads(path.read_text(encoding="utf-8"))
        novel = Novel.loads(**json_data)
        return novel

    # ---------- 章节操作 ----------
    def save_chapter(self, novel: Novel, chapters: Sequence[Chapter]):
        """
        保存章节的内容（立即写入磁盘）。

        Args:
            novel: 小说对象（仅用于提取 novel_id 和标题等元信息，未强制存储）
            chapters: 章节对象
        """
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

    def load_chapter(self, novel_id: str, chapter_id: str, index_url: str = None) -> Chapter | None:
        """
        读取单个章节的保存数据。
        """
        if index_url is None:
            novel = self.load_meta(novel_id)
            if novel is None:
                raise FileNotFoundError(f"Cannot find meta.json: {novel_id}")
            else:
                index_url = novel.url
        path = self.get_chapter_path(novel_id=novel_id, chapter_id=chapter_id)
        if not path.exists():
            return None
        json_data = json.loads(path.read_text(encoding="utf-8"))
        json_data["index_url"] = index_url
        chapter = Chapter.loads(**json_data)
        return chapter

    def load_chapters(self, novel_id: str) -> Chapters:
        """
        读取所有章节的保存数据
        """
        chapters = []
        path = self.get_chapters_path(novel_id = novel_id)
        if not path.exists():
            return Chapters()
        novel = self.load_meta(novel_id)
        if novel is None:
            raise FileNotFoundError(f"Cannot find meta.json: {novel_id}")
        else:
            index_url = novel.url
        for file in path.glob("*.json"):
            try:
                chapter = self.load_chapter(novel_id = novel_id, chapter_id = file.stem, index_url = index_url)
                chapters.append(chapter)
            finally:
                pass

        return Chapters(chapters)


    def list_chapter_orders(self, novel_id: str) -> list[int] | None:
        """
        获取已保存的所有章节序号并排序。
        """
        chapters_dir = self.get_novel_dir(novel_id) / "chapters"
        if not chapters_dir.exists():
            return []
        chapters = self.load_chapters(novel_id = novel_id)
        if chapters is None:
            return None
        orders = [chapter.order for chapter in chapters]
        return sorted(orders)

    def delete_chapter(self, novel_id: str, chapter_id: str) -> None:
        """delete chapter"""
        path = self.get_chapter_path(novel_id=novel_id, chapter_id=chapter_id)
        os.remove(path)

    def load_progress(self, novel_id: str) -> DownloadProgress | None:
        """加载下载进度，若无则返回 None。"""
        return DownloadProgress.load(self.get_progress_path(novel_id))

    def save_progress(self, progress: DownloadProgress, novel_id: str):
        """保存下载进度"""
        progress.save(self.get_progress_path(novel_id))