from pathlib import Path
from typing import Iterable
from datetime import datetime
from core.options import ExportOptions
from dataclasses import dataclass
from exporters.base import BaseExporter
from models.novel import Chapter, Novel
import time


@dataclass
class TXTExportOptions(ExportOptions):
    format = "txt"
    encoding: str = "utf-8"
    extension = ".txt"
    single_file_path = None  # 默认 output_dir / group / novel.name / file_name


class TXTExporter(BaseExporter):
    """TXT 导出器：初始化时传入小说和选项，可多次调用 export 追加章节"""

    def __init__(self, options: TXTExportOptions, novel: Novel):
        encoding = getattr(options, "encoding", "utf-8")
        file_name_template = getattr(options, "file_name_template", "{title} - {author}")
        output_dir = Path(getattr(options, "output_dir"))
        group = getattr(options, "group", "default")
        extension = getattr(options, "extension", ".txt")

        self.novel = novel
        self.options = options
        self.extension = extension
        self.encoding = encoding
        self.file_name_template = file_name_template
        self.group = group

        self._ordered_chapter_dict = {}

        # 计算输出文件路径
        variables = {
            "title": novel.name if novel else "",
            "author": novel.author if novel else "",
            "group": self.group,
            "novel_id": novel.id if novel else "",
            "total_chapters": novel.serial if novel else 0,
            "date": datetime.now().strftime("%Y%m%d"),
        }

        file_name = self.file_name_template.format(**variables) + extension if extension is not "default" else ".txt"
        self.file_path = Path(output_dir) / group / (novel.name if novel else "unknown") / file_name
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

        if not self._header_written:
            self._write_header()
            self._header_written = True
        if self.options.single_file_path:
            self.file_path = Path(self.options.single_file_path)
        # 写入章节内容
        with open(self.file_path, "w", encoding=self.encoding) as f:
            for chapter in chapters:
                text = self._format_chapter(chapter)
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
