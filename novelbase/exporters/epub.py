import html as html_lib
import io as _io
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Literal

from ..core.options import ExportOptions
from ..models.novel import Chapter, Novel, Illustration
from ..utils.logger import get_logger

_log = get_logger("novelbase.exporters.epub")

from PIL import Image

# ═══════════════════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════════════════

_FORMAT_EXT: dict[str, str] = {
    "jpeg": ".jpg", "png": ".png", "gif": ".gif",
    "webp": ".webp", "heic": ".heic", "tiff": ".tiff",
}

_MIME_MAP: dict[str, str] = {
    '.jpg':  'image/jpeg', '.jpeg': 'image/jpeg',
    '.png':  'image/png', '.gif': 'image/gif',
    '.webp': 'image/webp', '.bmp': 'image/bmp',
    '.tiff': 'image/tiff', '.heic': 'image/heic',
    '.svg':  'image/svg+xml',
}

_COMPRESSION_MAP: dict[str, int] = {
    "stored": zipfile.ZIP_STORED, "deflate": zipfile.ZIP_DEFLATED,
}
try:
    _COMPRESSION_MAP["bzip2"] = zipfile.ZIP_BZIP2
except AttributeError:
    pass
try:
    _COMPRESSION_MAP["lzma"] = zipfile.ZIP_LZMA
except AttributeError:
    pass

DEFAULT_CSS = """\
body {
    font-family: "Microsoft YaHei", "SimSun", serif;
    line-height: 1.8;
    margin: 1em;
    color: #333;
}
h1 {
    text-align: center;
    font-size: 1.5em;
    margin: 1.5em 0 0.8em 0;
    font-weight: bold;
}
p {
    text-indent: 2em;
    margin: 0.5em 0;
}
img {
    max-width: 100%;
    height: auto;
}
.cover {
    text-align: center;
    padding: 2em 0;
}
.cover img {
    max-width: 90%;
    max-height: 90%;
}
.chapter-meta {
    font-size: 0.8em;
    color: #888;
    text-align: left;
    margin-bottom: 1.2em;
}
.illustration {
    text-align: center;
    margin: 1em 0;
}
.illustration img {
    display: block;
    margin: 0 auto;
}
.illustration-caption {
    font-size: 0.85em;
    color: #666;
    margin-top: 0.3em;
    text-indent: 0;
}
"""


@dataclass
class EPUBExportOptions(ExportOptions):
    format: str = "epub"
    css_style: str = "default"
    file_name_template: str = "{name}"
    include_toc: bool = True
    encoding: str = "utf-8"
    compression: Literal["deflate", "bzip2", "stored"] = "deflate"
    compresslevel: int = 9
    optimize_images: bool = True
    jpeg_quality: int = 85
    max_image_width: int = 0


# ═══════════════════════════════════════════════════════════════════
# 图片注册（纯函数，image_registry 是局部 dict）
# ═══════════════════════════════════════════════════════════════════

def _new_image_registry() -> dict:
    return {
        "img_list": [],
        "img_hash_seen": set(),
        "img_name_seen": set(),
        "img_counter": 0,
    }


def _register_image(reg: dict, img: Illustration) -> str:
    if img.image_format in ("heic", "heif"):
        img = img.convert("jpeg")
        if img.image_format in ("heic", "heif"):
            _log.warning("HEIC 转 JPEG 失败（pillow-heif 未安装？），封面将保留为 HEIC 格式")

    h = hash(img.raw_data)
    if h in reg["img_hash_seen"]:
        for registered_img, fname in reg["img_list"]:
            if hash(registered_img.raw_data) == h:
                return fname
        return reg["img_list"][0][1] if reg["img_list"] else "unknown.jpg"

    reg["img_counter"] += 1
    if img.alt and img.alt.strip():
        base = _sanitize_filename(img.alt.strip())[:30]
    else:
        base = f"img_{reg['img_counter']:04d}"

    fmt = img.image_format or "jpeg"
    ext = _FORMAT_EXT.get(fmt, ".jpg")
    filename = f"{base}{ext}"

    suffix = 1
    while filename in reg["img_name_seen"]:
        filename = f"{base}_{suffix}{ext}"
        suffix += 1

    reg["img_hash_seen"].add(h)
    reg["img_name_seen"].add(filename)
    reg["img_list"].append((img, filename))
    return filename


def _img_filename(reg: dict, img: Illustration) -> str | None:
    h = hash(img.raw_data)
    for registered_img, fname in reg["img_list"]:
        if hash(registered_img.raw_data) == h:
            return fname
    return None


def _mime_type(filename: str) -> str:
    _, dot, ext = filename.rpartition('.')
    return _MIME_MAP.get(f".{ext.lower()}", "image/jpeg")


# ═══════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════

def _sanitize_filename(name: str) -> str:
    from ..utils.template_utils import sanitize_filename
    return sanitize_filename(name)


# ═══════════════════════════════════════════════════════════════════
# 渲染函数
# ═══════════════════════════════════════════════════════════════════

def _render_container_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
        '  <rootfiles>\n'
        '    <rootfile full-path="OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/>\n'
        '  </rootfiles>\n'
        '</container>'
    )


def _render_cover_xhtml(novel: Novel, cover_img_name: str) -> str:
    title = html_lib.escape(novel.title) if novel else ""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
        '<head>\n'
        '  <title>Cover</title>\n'
        '  <link rel="stylesheet" type="text/css" href="css/style.css"/>\n'
        '</head>\n'
        '<body>\n'
        '  <div class="cover">\n'
        f'    <img src="images/{cover_img_name}" alt="{title}"/>\n'
        '  </div>\n'
        '</body>\n'
        '</html>'
    )


def _render_css(options: EPUBExportOptions) -> str:
    style = getattr(options, "css_style", "default")
    if style == "default" or not style:
        raw = DEFAULT_CSS
    elif isinstance(style, str):
        raw = style
    else:
        raw = DEFAULT_CSS
    raw = re.sub(r'\s+', ' ', raw)
    raw = raw.replace('; ', ';').replace(': ', ':')
    raw = raw.replace(' {', '{').replace('{ ', '{')
    raw = raw.replace(' }', '}').replace(';}', '}')
    return raw


def _render_chapter(chapter: Chapter) -> str:
    title = html_lib.escape(chapter.title)
    update_time = ""
    if chapter.time:
        try:
            import time as _time
            update_time = _time.strftime("%Y-%m-%d %H:%M", _time.localtime(chapter.time))
        except (OSError, ValueError, OverflowError):
            update_time = str(chapter.time)
    word_count = chapter.count or 0
    body = _build_chapter_body(chapter)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
        '<head>\n'
        f'  <title>{title}</title>\n'
        '  <link rel="stylesheet" type="text/css" href="css/style.css"/>\n'
        '</head>\n'
        '<body>\n'
        f'  <h1>{title}</h1>\n'
        f'  <div class="chapter-meta">字数：{word_count} ｜ 更新时间：{update_time}</div>\n'
        f'{body}\n'
        '</body>\n'
        '</html>'
    )


# ═══════════════════════════════════════════════════════════════════
# _build_chapter_body 依赖 _register_image → 需要在渲染时传入 reg
# ═══════════════════════════════════════════════════════════════════

def _build_chapter_body(chapter: Chapter, reg: dict) -> str:
    content = chapter.content or ""
    images = list(chapter.images) if chapter.images else []
    if not images:
        return _text_to_xhtml(content)

    positioned: list[tuple[Illustration, int]] = []
    unpositioned: list[Illustration] = []
    for img in images:
        if img.insert is not None:
            positioned.append((img, img.insert))
        else:
            unpositioned.append(img)
    positioned.sort(key=lambda x: x[1])

    result = content
    placeholder_map: dict[str, Illustration] = {}
    end_placeholders: list[str] = []
    idx = 0

    for img, pos in reversed(positioned):
        ph = f"{{{{IMG_{idx:04d}}}}}"
        placeholder_map[ph] = img
        pos = max(0, min(pos, len(result)))
        result = result[:pos] + ph + result[pos:]
        idx += 1

    for img in unpositioned:
        ph = f"{{{{IMG_{idx:04d}}}}}"
        placeholder_map[ph] = img
        end_placeholders.append(ph)
        idx += 1

    xhtml = _text_to_xhtml(result)

    for ph, img in placeholder_map.items():
        fname = _register_image(reg, img)
        alt = html_lib.escape(img.alt or "")
        if ph in end_placeholders:
            continue
        tag = f'<img src="images/{fname}" alt="{alt}"/>'
        xhtml = xhtml.replace(ph, tag)

    if end_placeholders:
        end_tags: list[str] = []
        for ph in end_placeholders:
            img = placeholder_map[ph]
            fname = _img_filename(reg, img)
            if fname is None:
                fname = _register_image(reg, img)
            alt = html_lib.escape(img.alt or "")
            end_tags.append(
                f'<div class="illustration">'
                f'<img src="images/{fname}" alt="{alt}"/>'
                f'<p class="illustration-caption">{alt}</p>'
                f'</div>'
            )
        xhtml += "\n" + "\n".join(end_tags) if xhtml else "\n".join(end_tags)

    return xhtml


def _text_to_xhtml(text: str, compression: str = "deflate") -> str:
    if not text:
        return ""
    text = html_lib.escape(text, quote=False)
    blocks = re.split(r"\n\s*\n", text)
    parts: list[str] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        block = block.replace("\n", "<br/>\n")
        parts.append(f"<p>{block}</p>")
    result = "\n".join(parts)
    if compression != "stored":
        result = re.sub(r'\n{3,}', '\n\n', result)
    return result


# ═══════════════════════════════════════════════════════════════════
# 构建路径
# ═══════════════════════════════════════════════════════════════════

def _build_file_path(novel: Novel, options: EPUBExportOptions) -> Path:
    from ..utils.template_utils import SafeDict

    file_name_template = getattr(options, "file_name_template", "{title}")
    variables = SafeDict({
        "name": novel.title if novel else "",
        "title": novel.title if novel else "",
        "author": novel.author if novel else "",
        "novel_id": novel.id if novel else "",
        "total_chapters": novel.serial if novel else 0,
        "date": datetime.now().strftime("%Y%m%d"),
        "file_name_template": file_name_template,
    })
    raw_path = str(getattr(options, "output_path", "."))
    output_dir = Path(raw_path.format_map(variables))
    filename = file_name_template.format_map(variables)
    return output_dir / f"{filename}.epub"


# ═══════════════════════════════════════════════════════════════════
# OPF / NAV 渲染
# ═══════════════════════════════════════════════════════════════════

def _render_opf(
    novel: Novel,
    chapter_xhtml: list[tuple[Chapter, int, str]],
    cover_img_name: str | None,
    novel_uuid: str,
    reg: dict,
    include_toc: bool,
) -> str:
    title = html_lib.escape(novel.title) if novel else "Unknown"
    author = html_lib.escape(novel.author) if novel else "Unknown"
    desc = html_lib.escape(novel.description or "") if novel else ""

    manifest: list[str] = []
    spine: list[str] = []

    if include_toc:
        manifest.append(
            '    <item id="nav" href="nav.xhtml" '
            'media-type="application/xhtml+xml" properties="nav"/>'
        )
    manifest.append('    <item id="css" href="css/style.css" media-type="text/css"/>')

    if cover_img_name:
        mime = _mime_type(cover_img_name)
        manifest.append(
            f'    <item id="cover-image" href="images/{cover_img_name}" '
            f'media-type="{mime}" properties="cover-image"/>'
        )
        manifest.append(
            '    <item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>'
        )
        spine.append('    <itemref idref="cover"/>')

    for _, order, _ in chapter_xhtml:
        cid = f"chapter_{order:04d}"
        manifest.append(
            f'    <item id="{cid}" href="{cid}.xhtml" media-type="application/xhtml+xml"/>'
        )
        spine.append(f'    <itemref idref="{cid}"/>')

    img_seq = 0
    for img, fname in reg["img_list"]:
        if cover_img_name and fname == cover_img_name:
            continue
        img_seq += 1
        img_id = f"img_{img_seq:04d}"
        mime = _mime_type(fname)
        manifest.append(
            f'    <item id="{img_id}" href="images/{fname}" media-type="{mime}"/>'
        )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" '
        'unique-identifier="book-id" version="3.0">\n'
        '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"\n'
        '            xmlns:opf="http://www.idpf.org/2007/opf">\n'
        f'    <dc:identifier id="book-id">urn:uuid:{novel_uuid}</dc:identifier>\n'
        f'    <dc:title>{title}</dc:title>\n'
        f'    <dc:creator>{author}</dc:creator>\n'
        f'    <dc:language>zh-CN</dc:language>\n'
        f'    <dc:description>{desc}</dc:description>\n'
        f'    <dc:date>{datetime.now().strftime("%Y-%m-%d")}</dc:date>\n'
        '    <meta name="generator" content="novel-downloader"/>\n'
        '  </metadata>\n'
        '  <manifest>\n'
        + "\n".join(manifest)
        + "\n  </manifest>\n"
        '  <spine>\n'
        + "\n".join(spine)
        + '\n  </spine>\n'
        '</package>'
    )


def _render_nav(
    novel: Novel,
    chapter_xhtml: list[tuple[Chapter, int, str]],
    reg: dict,
) -> str:
    title = html_lib.escape(novel.title) if novel else "Unknown"
    items: list[str] = []
    has_cover = bool(novel and novel.cover and _img_filename(reg, novel.cover))
    if has_cover:
        items.append('      <li>\n        <a href="cover.xhtml">封面</a>\n      </li>')
    for ch, order, _ in chapter_xhtml:
        items.append(
            f'      <li>\n'
            f'        <a href="chapter_{order:04d}.xhtml">{html_lib.escape(ch.title)}</a>\n'
            f'      </li>'
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml"'
        ' xmlns:epub="http://www.idpf.org/2007/ops">\n'
        '<head>\n'
        f'  <title>{title} — 目录</title>\n'
        '</head>\n'
        '<body>\n'
        '  <nav epub:type="toc" id="toc">\n'
        '    <h1>目录</h1>\n'
        '    <ol>\n'
        + "\n".join(items)
        + "\n    </ol>\n"
        '  </nav>\n'
        '</body>\n'
        '</html>'
    )


# ═══════════════════════════════════════════════════════════════════
# 图片优化
# ═══════════════════════════════════════════════════════════════════

def _optimize_image(data: bytes, options: EPUBExportOptions) -> bytes:
    if options.jpeg_quality == 0:
        return data
    try:
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except ImportError:
            pass
        img = Image.open(_io.BytesIO(data))
        fmt = img.format or "JPEG"
        max_w = options.max_image_width or 0
        if max_w > 0 and img.width > max_w:
            ratio = max_w / img.width
            new_h = int(img.height * ratio)
            img = img.resize((max_w, new_h), Image.LANCZOS)
        out = _io.BytesIO()
        save_kw: dict = {"optimize": True}
        if fmt.upper() in ("JPEG", "JPG"):
            if img.mode in ("P", "RGBA"):
                img = img.convert("RGB")
            save_kw["quality"] = options.jpeg_quality
            img.save(out, format="JPEG", **save_kw)
        elif fmt.upper() == "PNG":
            if img.mode == "P":
                img = img.convert("RGBA")
            img.save(out, format="PNG", **save_kw)
        elif fmt.upper() == "GIF":
            img.save(out, format="GIF", **save_kw)
        elif fmt.upper() == "WEBP":
            save_kw["quality"] = options.jpeg_quality
            img.save(out, format="WEBP", **save_kw)
        else:
            img.save(out, format=fmt, **save_kw)
        optimized = out.getvalue()
        return optimized if len(optimized) < len(data) else data
    except Exception as exc:
        _log.debug("Image optimization skipped: %s", exc)
        return data


# ═══════════════════════════════════════════════════════════════════
# 主导出函数
# ═══════════════════════════════════════════════════════════════════

def export(
    chapters,
    novel: Novel,
    options: EPUBExportOptions | None = None,
    **kwargs,
) -> Path:
    """一次性导出 EPUB，返回输出文件路径。"""
    if options is None:
        options = EPUBExportOptions()
    file_path = _build_file_path(novel, options)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(chapters, Chapter):
        chapters_list = [chapters]
    else:
        chapters_list = list(chapters)
    chapters_list = [c for c in chapters_list if c.content is not None]
    chapters_list.sort(key=lambda c: c.order)

    if not chapters_list:
        raise ValueError("没有可导出的章节（content 均为空）")

    novel_uuid = str(uuid.uuid4())
    reg = _new_image_registry()

    # 注册封面
    cover_img_name: str | None = None
    if novel and novel.cover:
        cover_img_name = _register_image(reg, novel.cover)

    # 渲染章节
    chapter_xhtml: list[tuple[Chapter, int, str]] = []
    for idx, ch in enumerate(chapters_list, start=1):
        html_body = _build_chapter_body(ch, reg)
        chapter_xhtml.append((ch, idx, html_body))

    # 压缩
    comp_algo = _COMPRESSION_MAP.get(options.compression, zipfile.ZIP_DEFLATED)
    comp_kw: dict = {}
    if comp_algo == zipfile.ZIP_DEFLATED:
        comp_kw["compresslevel"] = options.compresslevel
    _log.debug("EPUB compression: algo=%s level=%s", options.compression, options.compresslevel)

    # 写入 ZIP
    with zipfile.ZipFile(file_path, "w", comp_algo, **comp_kw) as zf:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, "application/epub+zip")
        zf.writestr("META-INF/container.xml", _render_container_xml())
        zf.writestr("OEBPS/css/style.css", _render_css(options))
        for img, fname in reg["img_list"]:
            data = _optimize_image(img.raw_data, options) if options.optimize_images else img.raw_data
            zf.writestr(f"OEBPS/images/{fname}", data)
        for _, order, html_str in chapter_xhtml:
            zf.writestr(f"OEBPS/chapter_{order:04d}.xhtml", html_str)
        if cover_img_name:
            zf.writestr("OEBPS/cover.xhtml", _render_cover_xhtml(novel, cover_img_name))
        zf.writestr("OEBPS/content.opf", _render_opf(
            novel, chapter_xhtml, cover_img_name, novel_uuid, reg, options.include_toc))
        if options.include_toc:
            zf.writestr("OEBPS/nav.xhtml", _render_nav(novel, chapter_xhtml, reg))

    return file_path


