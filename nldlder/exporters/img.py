import re
from pathlib import Path
from typing import Iterable, Union

from dataclasses import dataclass

from core.options import ExportOptions
from exporters.base import BaseExporter
from models.novel import Chapter, Novel

@dataclass
class IMGExportOptions(ExportOptions):
    format: str = "img"
    extension: str = ".jpg"
    group: str = "default"


class IMGExporter(BaseExporter):
    def __init__(self, options: IMGExportOptions, novel: Novel):
        self.novel = novel
        self.options = options

    @staticmethod
    def _write(data: bytes, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def export(self, chapters: Union[Chapter, Iterable[Chapter]], **kwargs):
        if isinstance(chapters, Chapter):
            chapters = [chapters]

        base_dir = Path(self.options.output_dir).resolve()
        group_name = self.options.group
        novel_name = self._sanitize_filename(self.novel.name)

        # 扩展名处理
        ext = self.options.extension
        if ext == "default":
            ext = ".jpg"
        if not ext.startswith("."):
            ext = "." + ext

        total_saved = 0

        for chapter in chapters:
            chapter_dir = base_dir / group_name / novel_name / self._sanitize_filename(chapter.title)

            img_counter = 1

            for img in chapter.images:
                if img.alt and img.alt.strip():
                    base_name = self._sanitize_filename(img.alt.strip())
                else:
                    base_name = f"img_{img_counter:03d}"
                    img_counter += 1

                # 处理同目录重名
                final_name = base_name + ext
                final_path = chapter_dir / final_name
                suffix = 1
                while final_path.exists():
                    final_name = f"{base_name}_{suffix}{ext}"
                    final_path = chapter_dir / final_name
                    suffix += 1

                # 写入文件
                self._write(img.raw_data, final_path)
                total_saved += 1

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """移除文件系统不允许的字符"""
        return re.sub(r'[\\/*?:"<>|]', '_', name)