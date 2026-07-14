import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Any

from .base import BASEExporter
from ..core.options import ExportOptions
from ..models.novel import Chapter, Novel

_MAGIC_EXT: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"\xff\xd8", ".jpg"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
    (b"RIFF", ".webp"),
    (b"BM", ".bmp"),
    (b"\x00\x00\x00 ftyp", ".heic"),
    (b"\x00\x00\x00\x18ftyp", ".heic"),
    (b"\x00\x00\x00\x1cftyp", ".heic"),
    (b"MM\x00*", ".tiff"),
    (b"II*\x00", ".tiff"),
]


def _resolve_ext_from_bytes(data: bytes) -> str:
    for magic, ext in _MAGIC_EXT:
        if data.startswith(magic):
            if magic == b"RIFF" and b"WEBP" not in data[:12]:
                continue
            return ext
    return ".jpg"


@dataclass
class IMGExportOptions(ExportOptions):
    """图片导出配置。

    output_path 表示图片输出目录的准确路径（非单个文件路径）。
    file_name_template 为 ``str.format()`` 模板，
    可用变量 ``{n}`` 表示图片序号（0 = 封面，1,2,3…）。
    例如 ``"{n:03d}"`` → ``000.jpg``, ``001.jpg``。

    output_format: 输出图片格式。
        "original" — 保持原格式（默认）
        "jpeg" — 统一转为 JPEG（RGBA 自动填充白色背景）
        "png"  — 统一转为 PNG
        "webp" — 统一转为 WebP
    """
    format: str = "img"
    file_name_template: str = "{n}"
    output_format: str = "original"  # original / jpeg / png / webp / tiff


class IMGExporter(BASEExporter):
    """图片导出器。

    所有图片（含封面）输出到同一目录，文件名由 ``file_name_template`` 决定。
    封面为第 0 张，后续章节图片按 order 顺序排列。
    支持多次调用 ``export()``，图片序号持续递增（不重置）。
    """

    def __init__(self, options: IMGExportOptions):
        self.options = options
        # 全局序号计数器：0 = 封面，1+ = 章节图片
        self._img_counter = 0
        # output_path 在首次 export() 时格式化（需要 novel 元数据）
        self._output_base: Path | None = None

    # ── 公开 API ─────────────────────────────────────────────────

    def export(self, chapters: Chapter | Iterable[Chapter], meta: Novel, **kwargs):
        """导出图片。

        首次调用自动写入封面图片（n=0），
        后续每次写入传入章节的所有内嵌图片。

        Args:
            chapters: 一个或多个章节对象。
            novel: 小说对象（用于封面和路径变量）。
        """
        if isinstance(chapters, Chapter):
            chapters = [chapters]
        chapters = list(chapters)

        # 首次调用时格式化输出路径
        if self._output_base is None:
            self._output_base = self._build_output_base(meta)

        self._output_base.mkdir(parents=True, exist_ok=True)

        # 首次调用时写入封面（n=0）
        if self._img_counter == 0 and meta and meta.cover:
            self._write_image(self._output_base, meta.cover.raw_data)

        # 写入章节图片
        for chapter in chapters:
            if not chapter.images:
                continue
            for img in chapter.images:
                self._write_image(self._output_base, img.raw_data)

    # ── 内部 ─────────────────────────────────────────────────────

    def _build_output_base(self, novel: Novel) -> Path:
        """用 novel 变量格式化 output_path。"""
        from datetime import datetime

        class _SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        variables = _SafeDict({
            "title": novel.title if novel else "",
            "author": novel.author if novel else "",
            "novel_id": novel.id if novel else "",
            "total_chapters": novel.serial if novel else 0,
            "date": datetime.now().strftime("%Y%m%d"),
        })
        resolved = str(self.options.output_path).format_map(variables)
        return Path(resolved).resolve()

    # ── 内部 ─────────────────────────────────────────────────────

    def _write_image(self, base_dir: Path, raw_data: bytes):
        """按模板生成文件名并写入磁盘（可选格式转换）。"""
        name = self.options.file_name_template.format(n=self._img_counter)
        safe_name = self._sanitize_filename(name)

        fmt = self.options.output_format
        if fmt and fmt != "original":
            ext = f".{fmt}" if not fmt.startswith(".") else fmt
            data = self._convert_format(raw_data, fmt)
        else:
            ext = _resolve_ext_from_bytes(raw_data)
            data = raw_data

        path = base_dir / f"{safe_name}{ext}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self._img_counter += 1

    @staticmethod
    def _convert_format(raw_data: bytes, target_fmt: str) -> bytes:
        """将图片 bytes 转为目标格式（jpeg / png / webp / tiff / heic）。"""
        try:
            from io import BytesIO
            from PIL import Image

            from pillow_heif import register_heif_opener
            register_heif_opener()

            src = Image.open(BytesIO(raw_data))
            buf = BytesIO()

            save_kwargs: dict[str, Any] = {}
            if target_fmt == "jpeg":
                if src.mode in ("RGBA", "LA", "P"):
                    bg = Image.new("RGB", src.size, (255, 255, 255))
                    bg.paste(src, mask=src.split()[-1] if src.mode == "RGBA" else None)
                    src = bg
                save_kwargs["quality"] = 95
            elif target_fmt == "webp":
                save_kwargs["quality"] = 90

            src.save(buf, format=target_fmt.upper(), **save_kwargs)
            return buf.getvalue()
        except ImportError:
            import logging
            logging.getLogger("novelbase.exporters.img").warning(
                "Pillow 未安装，跳过格式转换，保持原格式")
            return raw_data



    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """移除文件系统不允许的字符。"""
        return re.sub(r'[\\/*?:"<>|]', "_", name)
