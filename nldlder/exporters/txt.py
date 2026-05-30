import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .base import BaseExporter
from ..core.options import ExportOptions
from ..models.novel import Chapter, Novel


@dataclass
class TXTExportOptions(ExportOptions):
    format = "txt"
    encoding: str = "utf-8"
    extension = ".txt"


class TXTExporter(BaseExporter):
    """TXT 导出器：初始化时传入小说和选项，可多次调用 export 追加章节"""

    def __init__(self, options: TXTExportOptions, novel: Novel):
        encoding = getattr(options, "encoding", "utf-8")
        output_path = Path(getattr(options, "output_path"))
        extension = getattr(options, "extension", ".txt")

        self.novel = novel
        self.options = options
        self.extension = extension
        self.encoding = encoding

        self._ordered_chapter_dict = {}

        # output_path 是精确的文件路径模板，直接格式化后使用
        variables = {
            "name": novel.name if novel else "",
            "author": novel.author if novel else "",
            "novel_id": novel.id if novel else "",
            "total_chapters": novel.serial if novel else 0,
            "date": datetime.now().strftime("%Y%m%d"),
        }
        self.file_path = Path(str(output_path).format(**variables))
        self._header_written = False

    def export(self, chapters: Chapter | Iterable[Chapter], **kwargs):
        """导出章节（首次调用自动写入信息头）"""

        # 标准化章节列表
        if isinstance(chapters, Chapter):
            chapters = [chapters]
        else:
            chapters = list(chapters)
        for chapter in chapters:
            self._ordered_chapter_dict[chapter.order] = chapter
        chapters = list(self._ordered_chapter_dict.values())
        chapters.sort(key=lambda x: x.order)
        chapters = [x for x in chapters if x.content is not None]

        self._write_header()
        # 写入章节内容
        with open(self.file_path, "a", encoding=self.encoding) as f:
            text = ""
            for chapter in chapters:
                text += self._format_chapter(chapter)
            f.write(text)

    def _write_header(self):
        """生成小说信息头部并创建/覆盖文件"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.file_path, "w", encoding=self.encoding) as f:
            f.write(self._generate_info_text())

    def _generate_info_text(self) -> str:
        if not self.novel:
            return ""
        novel = self.novel
        return (
            f"小说名：{novel.name}\n"
            f"作者：{novel.author}\n"
            f"简介：{novel.description}\n"
            f"标签：{' '.join(novel.tags) if novel.tags else ''}\n"
            f"章节数：{novel.serial}\n"
            f"字数：{novel.count}\n"
            f"链接：{novel.url}\n\n"
        )

    @staticmethod
    def _format_chapter(chapter: Chapter) -> str:
        if isinstance(chapter.content, str):
            content = '\t' + chapter.content.replace("\n", "\n\t")
        else:
            content = str(chapter.content) if chapter.content else ""
        return (
            f"{chapter.title}\n\n"
            f"更新字数：{chapter.count}\n"
            f"更新时间：{time.strftime('%Y-%m-%d %H:%M', time.localtime(chapter.time))}\n\n"
            f"{content}\n\n"
        )
