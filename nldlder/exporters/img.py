import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .base import BaseExporter
from ..core.options import ExportOptions
from ..models.novel import Chapter, Novel


@dataclass
class IMGExportOptions(ExportOptions):
    """图片导出配置。

    output_path 表示图片输出目录的准确路径（非单个文件路径）。
    file_name_template 为 ``str.format()`` 模板，
    可用变量 ``{n}`` 表示图片序号（0 = 封面，1,2,3…）。
    例如 ``"{n:03d}"`` → ``000.jpg``, ``001.jpg``。
    """
    format: str = "img"
    file_name_template: str = "{n}"
    extension: str = ".jpg"


class IMGExporter(BaseExporter):
    """图片导出器。

    所有图片（含封面）输出到同一目录，文件名由 ``file_name_template`` 决定。
    封面为第 0 张，后续章节图片按 order 顺序排列。
    支持多次调用 ``export()``，图片序号持续递增（不重置）。
    """

    def __init__(self, options: IMGExportOptions, novel: Novel):
        self.novel = novel
        self.options = options
        # 全局序号计数器：0 = 封面，1+ = 章节图片
        self._img_counter = 0

    # ── 公开 API ─────────────────────────────────────────────────

    def export(self, chapters: Chapter | Iterable[Chapter], **kwargs):
        """导出图片。

        首次调用自动写入封面图片（n=0），
        后续每次写入传入章节的所有内嵌图片。

        Args:
            chapters: 一个或多个章节对象。
        """
        if isinstance(chapters, Chapter):
            chapters = [chapters]
        chapters = list(chapters)

        ext = self._resolve_extension()
        base_dir = Path(self.options.output_path).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)

        # 首次调用时写入封面（n=0）
        if self._img_counter == 0 and self.novel and self.novel.cover:
            self._write_image(base_dir, self.novel.cover.raw_data, ext)

        # 写入章节图片
        for chapter in chapters:
            if not chapter.images:
                continue
            for img in chapter.images:
                self._write_image(base_dir, img.raw_data, ext)

    # ── 内部 ─────────────────────────────────────────────────────

    def _write_image(self, base_dir: Path, raw_data: bytes, ext: str):
        """按模板生成文件名并写入磁盘。"""
        name = self.options.file_name_template.format(n=self._img_counter)
        safe_name = self._sanitize_filename(name)
        path = base_dir / f"{safe_name}{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw_data)
        self._img_counter += 1

    def _resolve_extension(self) -> str:
        ext = self.options.extension
        if ext == "default" or not ext:
            return ".jpg"
        if not ext.startswith("."):
            ext = "." + ext
        return ext

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """移除文件系统不允许的字符。"""
        return re.sub(r'[\\/*?:"<>|]', "_", name)
