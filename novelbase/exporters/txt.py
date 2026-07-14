import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .base import BASEExporter
from ..core.options import ExportOptions
from ..models.novel import Chapter, Novel


@dataclass
class TXTExportOptions(ExportOptions):
    format: str = "txt"
    encoding: str = "utf-8"


class TXTExporter(BASEExporter):
    """TXT 导出器：初始化时传入选项，可多次调用 export 追加章节"""

    def __init__(self, options: TXTExportOptions):
        self.options = options
        self.encoding = getattr(options, "encoding", "utf-8")
        self._file_name_template = getattr(options, "file_name_template", "{title}")

        self._ordered_chapter_dict: dict[int, Chapter] = {}
        self._header_written = False
        self._file_path: Path | None = None

    def export(self, chapters: Chapter | Iterable[Chapter], meta: Novel, **kwargs):
        """导出章节（首次调用自动写入信息头）"""

        # 首次调用时从 meta 构建文件路径
        if self._file_path is None:
            self._file_path = self._build_file_path(meta)

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

        self._write_header(meta)
        # 写入章节内容
        with open(self._file_path, "a", encoding=self.encoding) as f:
            text = ""
            for chapter in chapters:
                text += self._format_chapter(chapter)
            f.write(text)

    def _build_file_path(self, novel: Novel) -> Path:
        """从 options + novel 构建输出文件路径。"""
        from datetime import datetime

        from ..utils.template_utils import SafeDict as _SafeDict

        variables = _SafeDict({
            "title": novel.title if novel else "",
            "author": novel.author if novel else "",
            "novel_id": novel.id if novel else "",
            "total_chapters": novel.serial if novel else 0,
            "date": datetime.now().strftime("%Y%m%d"),
        })
        raw_path = str(getattr(self.options, "output_path", "."))
        output_dir = Path(raw_path.format_map(variables))
        filename = self._file_name_template.format(**variables)
        return output_dir / f"{filename}.txt"

    def _write_header(self, novel: Novel):
        """生成小说信息头部并创建/覆盖文件"""
        if self._header_written:
            return
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._file_path, "w", encoding=self.encoding) as f:
            f.write(self._generate_info_text(novel))
        self._header_written = True

    def _generate_info_text(self, novel: Novel) -> str:
        if not novel:
            return ""
        return (
            f"小说名：{novel.title}\n"
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
            f"更新时间：{time.strftime('%Y-%m-%d %H:%M', time.localtime(chapter.time)) if chapter.time else '未知'}\n\n"
            f"{content}\n\n"
        )
