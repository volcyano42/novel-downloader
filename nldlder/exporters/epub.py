import html as html_lib
import io as _io
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Literal

from .base import BaseExporter
from ..core.options import ExportOptions
from ..models.novel import Chapter, Novel, Illustration
from ..utils.logger import get_logger

_log = get_logger("nldlder.exporters.epub")

# 尝试导入 Pillow（可选）
try:
    from PIL import Image
    _HAS_PILLOW = True
except ImportError:
    _HAS_PILLOW = False

# 压缩算法常量
_COMPRESSION_MAP: dict[str, int] = {
    "stored": zipfile.ZIP_STORED,
    "deflate": zipfile.ZIP_DEFLATED,
}
try:
    _COMPRESSION_MAP["bzip2"] = zipfile.ZIP_BZIP2
except AttributeError:
    pass
try:
    _COMPRESSION_MAP["lzma"] = zipfile.ZIP_LZMA
except AttributeError:
    pass


@dataclass
class EPUBExportOptions(ExportOptions):
    """EPUB 保存配置"""
    format: str = "epub"
    css_style: str = "default"
    file_name_template: str = "{name}"
    include_toc: bool = True
    extension: str = ".epub"
    encoding: str = "utf-8"

    # ── 压缩选项 ────────────────────────────────────────────────
    compression: Literal["deflate", "bzip2", "stored"] = "deflate"
    compresslevel: int = 9

    # ── 图片优化选项 ────────────────────────────────────────────
    optimize_images: bool = True
    jpeg_quality: int = 85
    max_image_width: int = 0  # 0 = 不缩放


class EPUBExporter(BaseExporter):
    """EPUB 导出器：生成带插图和目录的 .epub 电子书。

    用法与 TXT 导出器一致——初始化时传入小说和选项，
    可多次调用 ``export()`` 追加章节（内部每次全量重建 EPUB）。
    章节内的 ``Illustration`` 会按 ``insert`` 字段指定的字符偏移量
    嵌入正文；``insert`` 为 ``None`` 时插图追加到章末。
    """

    # ── 文件头魔数 → 扩展名 ────────────────────────────────────────
    _MAGIC_EXT: list[tuple[bytes, str]] = [
        (b'\xff\xd8\xff', '.jpg'),
        (b'\x89PNG\r\n\x1a\n', '.png'),
        (b'GIF8', '.gif'),
        (b'RIFF', '.webp'),       # 额外校验 WEBP 在 12 字节内
        (b'<?xml', '.svg'),
    ]

    # ── 扩展名 → MIME 类型 ─────────────────────────────────────────
    _MIME_MAP: dict[str, str] = {
        '.jpg':  'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png':  'image/png',
        '.gif':  'image/gif',
        '.webp': 'image/webp',
        '.svg':  'image/svg+xml',
    }

    # ── 默认 CSS ───────────────────────────────────────────────────
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

    # ═══════════════════════════════════════════════════════════════
    # 初始化
    # ═══════════════════════════════════════════════════════════════

    def __init__(self, options: EPUBExportOptions, novel: Novel):
        encoding = getattr(options, "encoding", "utf-8")
        extension = getattr(options, "extension", ".epub")
        file_name_template = getattr(options, "file_name_template", "{title}")

        self.novel = novel
        self.options = options
        self.extension = extension
        self.encoding = encoding

        # 章节累积（按 order 排序，支持多次 export 调用）
        self._ordered_chapter_dict: dict[int, Chapter] = {}

        # 图片注册表（每次 build 前重置）
        self._img_list: list[tuple[Illustration, str]] = []
        self._img_hash_seen: set[int] = set()
        self._img_name_seen: set[str] = set()
        self._img_counter: int = 0

        # output_path 此时只替换了 {group}，还需替换 {file_name_template} + 扩展名
        raw = str(getattr(options, "output_path", "."))
        raw = raw.replace("{file_name_template}", file_name_template)
        ext = extension if extension != "default" else ".epub"
        raw = raw + ext
        # 再用 novel 变量格式化
        variables = {
            "name": novel.title if novel else "",
            "title": novel.title if novel else "",
            "author": novel.author if novel else "",
            "novel_id": novel.id if novel else "",
            "total_chapters": novel.serial if novel else 0,
            "date": datetime.now().strftime("%Y%m%d"),
        }
        self.file_path = Path(raw.format(**variables))

    # ═══════════════════════════════════════════════════════════════
    # 公开 API
    # ═══════════════════════════════════════════════════════════════

    def export(self, chapters: Chapter | Iterable[Chapter], **kwargs):
        """导出章节（首次调用创建 EPUB，后续调用全量重建）。

        参数 *chapters* 可以是单个 ``Chapter`` 或可迭代对象。
        内部按 ``order`` 排序并去重，仅导出 ``content is not None`` 的章节。
        """
        if isinstance(chapters, Chapter):
            chapters = [chapters]
        else:
            chapters = list(chapters)

        for ch in chapters:
            self._ordered_chapter_dict[ch.order] = ch

        ordered = list(self._ordered_chapter_dict.values())
        ordered.sort(key=lambda c: c.order)
        ordered = [c for c in ordered if c.content is not None]

        if not ordered:
            return

        # 全量重建 EPUB
        self._build_epub(ordered)

    # ═══════════════════════════════════════════════════════════════
    # EPUB 构建
    # ═══════════════════════════════════════════════════════════════

    def _build_epub(self, chapters: list[Chapter]):
        """从头构建完整 EPUB ZIP 文件。"""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # 重置图片注册表
        self._img_list.clear()
        self._img_hash_seen.clear()
        self._img_name_seen.clear()
        self._img_counter = 0

        novel_uuid = str(uuid.uuid4())

        # 预注册封面图片（如果存在）
        cover_img_name: str | None = None
        if self.novel and self.novel.cover:
            cover_img_name = self._register_image(self.novel.cover)

        # 生成所有章节 XHTML（内部会注册内联图片）
        chapter_xhtml: list[tuple[Chapter, int, str]] = []
        for idx, ch in enumerate(chapters, start=1):
            html_body = self._render_chapter(ch)
            chapter_xhtml.append((ch, idx, html_body))

        # 选择压缩算法
        comp_algo = _COMPRESSION_MAP.get(self.options.compression, zipfile.ZIP_DEFLATED)
        comp_kw: dict = {}
        if comp_algo == zipfile.ZIP_DEFLATED:
            comp_kw["compresslevel"] = self.options.compresslevel
        _log.debug(
            "EPUB compression: algo=%s level=%s",
            self.options.compression, self.options.compresslevel,
        )

        # 写入 ZIP
        with zipfile.ZipFile(self.file_path, "w", comp_algo, **comp_kw) as zf:
            # ① mimetype — 必须首文件、不压缩
            info = zipfile.ZipInfo("mimetype")
            info.compress_type = zipfile.ZIP_STORED
            zf.writestr(info, "application/epub+zip")

            # ② META-INF
            zf.writestr("META-INF/container.xml", self._render_container_xml())

            # ③ CSS
            zf.writestr("OEBPS/css/style.css", self._render_css())

            # ④ 所有图片（包括封面）— 可选优化
            for img, fname in self._img_list:
                data = self._optimize_image(img.raw_data) if self.options.optimize_images else img.raw_data
                zf.writestr(f"OEBPS/images/{fname}", data)

            # ⑤ 章节 XHTML
            for _, order, html_str in chapter_xhtml:
                zf.writestr(f"OEBPS/chapter_{order:04d}.xhtml", html_str)

            # ⑥ 封面 XHTML
            if cover_img_name:
                zf.writestr(
                    "OEBPS/cover.xhtml",
                    self._render_cover_xhtml(cover_img_name),
                )

            # ⑦ content.opf
            zf.writestr(
                "OEBPS/content.opf",
                self._render_opf(chapter_xhtml, cover_img_name, novel_uuid),
            )

            # ⑧ nav.xhtml（EPUB3 目录）
            if self.options.include_toc:
                zf.writestr(
                    "OEBPS/nav.xhtml",
                    self._render_nav(chapter_xhtml),
                )

    # ═══════════════════════════════════════════════════════════════
    # 图片注册
    # ═══════════════════════════════════════════════════════════════

    def _register_image(self, img: Illustration) -> str:
        """注册图片并返回其在 EPUB 内的文件名（自动去重）。

        基于 ``raw_data`` 的 hash 去重：相同字节的图片只存一份。
        """
        h = hash(img.raw_data)
        if h in self._img_hash_seen:
            for registered_img, fname in self._img_list:
                if hash(registered_img.raw_data) == h:
                    return fname
            return self._img_list[0][1] if self._img_list else "unknown.jpg"

        self._img_counter += 1
        if img.alt and img.alt.strip():
            base = self._sanitize_filename(img.alt.strip())[:30]
        else:
            base = f"img_{self._img_counter:04d}"

        ext = self._guess_ext(img.raw_data)
        filename = f"{base}{ext}"

        suffix = 1
        while filename in self._img_name_seen:
            filename = f"{base}_{suffix}{ext}"
            suffix += 1

        self._img_hash_seen.add(h)
        self._img_name_seen.add(filename)
        self._img_list.append((img, filename))
        return filename

    def _img_filename(self, img: Illustration) -> str | None:
        h = hash(img.raw_data)
        for registered_img, fname in self._img_list:
            if hash(registered_img.raw_data) == h:
                return fname
        return None

    def _guess_ext(self, data: bytes) -> str:
        for magic, ext in self._MAGIC_EXT:
            if data.startswith(magic):
                if magic == b'RIFF' and b'WEBP' not in data[:12]:
                    continue
                return ext
        return '.jpg'

    @staticmethod
    def _mime_type(filename: str) -> str:
        _, dot, ext = filename.rpartition('.')
        return EPUBExporter._MIME_MAP.get(f".{ext.lower()}", "image/jpeg")

    # ═══════════════════════════════════════════════════════════════
    # 图片优化（Pillow 可选）
    # ═══════════════════════════════════════════════════════════════

    def _optimize_image(self, data: bytes) -> bytes:
        """使用 Pillow 优化图片（JPEG 重压缩、PNG 优化、缩放）。

        当 Pillow 不可用或出错时返回原始数据。
        """
        if not _HAS_PILLOW:
            return data
        try:
            img = Image.open(_io.BytesIO(data))
            fmt = img.format or "JPEG"

            # 缩放
            max_w = self.options.max_image_width or 0
            if max_w > 0 and img.width > max_w:
                ratio = max_w / img.width
                new_h = int(img.height * ratio)
                img = img.resize((max_w, new_h), Image.LANCZOS)

            out = _io.BytesIO()
            save_kw: dict = {"optimize": True}

            if fmt.upper() in ("JPEG", "JPG"):
                if img.mode in ("P", "RGBA"):
                    img = img.convert("RGB")
                save_kw["quality"] = self.options.jpeg_quality
                img.save(out, format="JPEG", **save_kw)
            elif fmt.upper() == "PNG":
                if img.mode == "P":
                    img = img.convert("RGBA")
                img.save(out, format="PNG", **save_kw)
            elif fmt.upper() == "GIF":
                img.save(out, format="GIF", **save_kw)
            elif fmt.upper() == "WEBP":
                save_kw["quality"] = self.options.jpeg_quality
                img.save(out, format="WEBP", **save_kw)
            else:
                img.save(out, format=fmt, **save_kw)

            optimized = out.getvalue()
            # 确保优化后不会更大
            return optimized if len(optimized) < len(data) else data
        except Exception as exc:
            _log.debug("Image optimization skipped: %s", exc)
            return data

    # ═══════════════════════════════════════════════════════════════
    # XML / XHTML 片段渲染
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
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

    def _render_cover_xhtml(self, cover_img_name: str) -> str:
        title = html_lib.escape(self.novel.title) if self.novel else ""
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

    def _render_css(self) -> str:
        style = getattr(self.options, "css_style", "default")
        if style == "default" or not style:
            raw = self.DEFAULT_CSS
        elif isinstance(style, str) and style != "default":
            raw = style
        else:
            raw = self.DEFAULT_CSS
        # 缩小体积：压缩空白和符号间距
        raw = re.sub(r'\s+', ' ', raw)
        raw = raw.replace('; ', ';').replace(': ', ':')
        raw = raw.replace(' {', '{').replace('{ ', '{')
        raw = raw.replace(' }', '}').replace(';}', '}')
        return raw

    def _render_chapter(self, chapter: Chapter) -> str:
        """将单个 Chapter 渲染为完整 XHTML 页面的字符串。"""
        title = html_lib.escape(chapter.title)
        update_time = ""
        if chapter.time:
            try:
                import time as _time
                update_time = _time.strftime(
                    "%Y-%m-%d %H:%M", _time.localtime(chapter.time)
                )
            except Exception:
                update_time = str(chapter.time)
        word_count = chapter.count or 0

        body = self._build_chapter_body(chapter)

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

    # ═══════════════════════════════════════════════════════════════
    # 正文 + 插图 处理
    # ═══════════════════════════════════════════════════════════════

    def _build_chapter_body(self, chapter: Chapter) -> str:
        """生成章节正文 XHTML，插图按 ``insert`` 偏移量嵌入。

        策略：
        1. 分离有明确 ``insert`` 位置和无位置的插图。
        2. 在有位置插图处插入占位符 ``{{IMG_XXXX}}``（从后往前插入，
           避免前面偏移量受后面插入影响）。
        3. 纯文本 → XHTML 段落（转义 + ``<p>`` 包裹）。
        4. 将占位符替换为 ``<img>`` 标签。
        5. 无位置插图追加到章节末尾（带说明文字的块级容器）。
        """
        content = chapter.content or ""
        images = list(chapter.images) if chapter.images else []

        if not images:
            return self._text_to_xhtml(content)

        # 分组：有 insert 位置 vs 无
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

        xhtml = self._text_to_xhtml(result)

        for ph, img in placeholder_map.items():
            fname = self._register_image(img)
            alt = html_lib.escape(img.alt or "")
            if ph in end_placeholders:
                continue
            else:
                tag = f'<img src="images/{fname}" alt="{alt}"/>'
            xhtml = xhtml.replace(ph, tag)

        if end_placeholders:
            end_tags: list[str] = []
            for ph in end_placeholders:
                img = placeholder_map[ph]
                fname = self._img_filename(img)
                if fname is None:
                    fname = self._register_image(img)
                alt = html_lib.escape(img.alt or "")
                end_tags.append(
                    f'<div class="illustration">'
                    f'<img src="images/{fname}" alt="{alt}"/>'
                    f'<p class="illustration-caption">{alt}</p>'
                    f'</div>'
                )
            if xhtml:
                xhtml += "\n" + "\n".join(end_tags)
            else:
                xhtml = "\n".join(end_tags)

        return xhtml

    def _text_to_xhtml(self, text: str) -> str:
        """将纯文本转换为 XHTML 段落。

        - 连续两个及以上换行 → 段落分隔。
        - 段落内单个换行 → ``<br/>``。
        - 特殊字符 ``& < > "`` 会被转义（占位符花括号不受影响）。
        """
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
        # 缩小体积：多行空白合并
        if self.options.compression != "stored":
            result = re.sub(r'\n{3,}', '\n\n', result)
        return result

    # ═══════════════════════════════════════════════════════════════
    # OPF / NCX
    # ═══════════════════════════════════════════════════════════════

    def _render_opf(
        self,
        chapter_xhtml: list[tuple[Chapter, int, str]],
        cover_img_name: str | None,
        novel_uuid: str,
    ) -> str:
        novel = self.novel
        title = html_lib.escape(novel.title) if novel else "Unknown"
        author = html_lib.escape(novel.author) if novel else "Unknown"
        desc = html_lib.escape(novel.description or "") if novel else ""

        manifest: list[str] = []
        spine: list[str] = []

        if self.options.include_toc:
            manifest.append(
                '    <item id="nav" href="nav.xhtml" '
                'media-type="application/xhtml+xml" properties="nav"/>'
            )

        manifest.append(
            '    <item id="css" href="css/style.css" media-type="text/css"/>'
        )

        if cover_img_name:
            mime = self._mime_type(cover_img_name)
            manifest.append(
                f'    <item id="cover-image" href="images/{cover_img_name}" '
                f'media-type="{mime}" properties="cover-image"/>'
            )
            manifest.append(
                '    <item id="cover" href="cover.xhtml" '
                'media-type="application/xhtml+xml"/>'
            )
            spine.append('    <itemref idref="cover"/>')

        for _, order, _ in chapter_xhtml:
            cid = f"chapter_{order:04d}"
            manifest.append(
                f'    <item id="{cid}" href="{cid}.xhtml" '
                'media-type="application/xhtml+xml"/>'
            )
            spine.append(f'    <itemref idref="{cid}"/>')

        cover_fname = cover_img_name
        img_seq = 0
        for img, fname in self._img_list:
            if cover_fname and fname == cover_fname:
                continue
            img_seq += 1
            img_id = f"img_{img_seq:04d}"
            mime = self._mime_type(fname)
            manifest.append(
                f'    <item id="{img_id}" href="images/{fname}" '
                f'media-type="{mime}"/>'
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
            + "\n  </spine>\n"
            '</package>'
        )

    def _render_nav(
        self,
        chapter_xhtml: list[tuple[Chapter, int, str]],
    ) -> str:
        novel = self.novel
        title = html_lib.escape(novel.title) if novel else "Unknown"

        items: list[str] = []
        has_cover = bool(
            self.novel
            and self.novel.cover
            and self._img_filename(self.novel.cover)
        )

        if has_cover:
            items.append(
                '      <li>\n'
                '        <a href="cover.xhtml">封面</a>\n'
                '      </li>'
            )

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

    # ═══════════════════════════════════════════════════════════════
    # 工具
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """移除文件系统不允许的字符。"""
        return re.sub(r'[\\/*?:"<>|]', "_", name)


# 模块结尾 — 导出类的命名必须符合 register_exporter 的约定
# EPUBExportOptions 和 EPUBExporter 会被 registry.py 自动发现
