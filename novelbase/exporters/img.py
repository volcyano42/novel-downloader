from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    format: str = "img"
    file_name_template: str = "{n}"
    output_format: str = "original"


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════

def _build_output_base(novel: Novel, options: IMGExportOptions) -> Path:
    from datetime import datetime
    from ..utils.template_utils import SafeDict

    variables = SafeDict({
        "title": novel.title if novel else "",
        "author": novel.author if novel else "",
        "novel_id": novel.id if novel else "",
        "total_chapters": novel.serial if novel else 0,
        "date": datetime.now().strftime("%Y%m%d"),
    })
    resolved = str(options.output_path).format_map(variables)
    return Path(resolved).resolve()


def _write_image(base_dir: Path, raw_data: bytes, counter: int, options: IMGExportOptions) -> int:
    name = options.file_name_template.format(n=counter)
    safe_name = _sanitize_filename(name)
    fmt = options.output_format
    if fmt and fmt != "original":
        ext = f".{fmt}" if not fmt.startswith(".") else fmt
        data = _convert_format(raw_data, fmt)
    else:
        ext = _resolve_ext_from_bytes(raw_data)
        data = raw_data
    path = base_dir / f"{safe_name}{ext}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return counter + 1


def _convert_format(raw_data: bytes, target_fmt: str) -> bytes:
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


def _sanitize_filename(name: str) -> str:
    from ..utils.template_utils import sanitize_filename
    return sanitize_filename(name)


# ═══════════════════════════════════════════════════════════════════
# 主导出函数
# ═══════════════════════════════════════════════════════════════════

def export(
    chapters,
    novel: Novel,
    options: IMGExportOptions | None = None,
    **kwargs,
) -> Path:
    """一次性导出图片，返回输出目录路径。"""
    if options is None:
        options = IMGExportOptions()
    output_base = _build_output_base(novel, options)
    output_base.mkdir(parents=True, exist_ok=True)

    if isinstance(chapters, Chapter):
        chapters_list = [chapters]
    else:
        chapters_list = list(chapters)

    counter = 0

    # 封面（n=0）
    if novel and novel.cover and novel.cover.raw_data:
        counter = _write_image(output_base, novel.cover.raw_data, counter, options)

    # 章节图片
    for chapter in chapters_list:
        if not chapter.images:
            continue
        for img in chapter.images:
            counter = _write_image(output_base, img.raw_data, counter, options)

    return output_base


