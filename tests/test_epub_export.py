"""EPUB 导出内容结构：章节 XHTML 必须是完整文档，且带章节标题。

2026-10-26 补：此前 `export()` 只写 `_build_chapter_body()` 的裸片段，
带 `<h1>{title}</h1>` 的 `_render_chapter()` 是死代码（签名还错着：调
`_build_chapter_body(chapter)` 少传 `reg`）→ 导出的 EPUB 每章没有标题，
`css/style.css` 被打进 zip 却没有任何 xhtml 引用它。测试只覆盖了导出器
注册（`test_exporter.py`），内容生成没人测，所以一直没被发现。
"""

import zipfile

from novelbase.exporters.epub import EPUBExportOptions, export
from novelbase.models.novel import Chapter, Novel


def _build(tmp_path):
    chapters = [
        Chapter(id="c1", url="http://x/1", novel_id="n1",
                title="第一章 开端", order=1, content="第一段正文。\n\n第二段正文。"),
        Chapter(id="c2", url="http://x/2", novel_id="n1",
                title="第二章 变故", order=2, content="第二章正文。"),
    ]
    novel = Novel(title="测试书", url="http://x/book", serial=1,
                  author="作者", description="简介", chapters=chapters)
    opts = EPUBExportOptions(output_path=str(tmp_path), enabled=True)
    path = export(chapters, novel, opts)
    return path


def _read(path, name: str) -> str:
    with zipfile.ZipFile(path) as zf:
        return zf.read(name).decode("utf-8")


def test_chapter_xhtml_is_a_complete_document(tmp_path):
    xhtml = _read(_build(tmp_path), "OEBPS/chapter_0001.xhtml")
    assert xhtml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "<!DOCTYPE html>" in xhtml
    assert '<html xmlns="http://www.w3.org/1999/xhtml">' in xhtml
    assert "</html>" in xhtml


def test_chapter_xhtml_has_chapter_title(tmp_path):
    """每章内容必须有标题 —— 这是本次修复的核心断言。"""
    path = _build(tmp_path)
    assert "<h1>第一章 开端</h1>" in _read(path, "OEBPS/chapter_0001.xhtml")
    assert "<h1>第二章 变故</h1>" in _read(path, "OEBPS/chapter_0002.xhtml")


def test_chapter_xhtml_has_body_content(tmp_path):
    xhtml = _read(_build(tmp_path), "OEBPS/chapter_0001.xhtml")
    assert "第一段正文" in xhtml and "第二段正文" in xhtml


def test_chapter_xhtml_links_stylesheet(tmp_path):
    """CSS 被写进 zip，必须有 xhtml 引用它，否则样式完全不生效。"""
    xhtml = _read(_build(tmp_path), "OEBPS/chapter_0001.xhtml")
    assert '<link rel="stylesheet" type="text/css" href="css/style.css"/>' in xhtml


def test_chapter_head_title_matches_chapter_title(tmp_path):
    xhtml = _read(_build(tmp_path), "OEBPS/chapter_0001.xhtml")
    assert "<title>第一章 开端</title>" in xhtml


def test_no_legacy_render_chapter_dead_code():
    """`_render_chapter` 曾是不可调用的死代码（少传 reg）。结构修复后它应有正确签名。"""
    import inspect

    from novelbase.exporters import epub as mod

    if hasattr(mod, "_render_chapter"):
        sig = inspect.signature(mod._render_chapter)
        # 要么删掉，要么签名可调用（body 由调用方渲染后传入）
        assert "body" in sig.parameters, (
            f"_render_chapter 仍不可独立调用：{sig}；应改为接收已渲染的 body"
        )


# ═══════════════════════════════════════════════════════════════════
# 插图：src 必须是纯 ASCII，且不能裸嵌在 <p> 里
# ═══════════════════════════════════════════════════════════════════
# 2026-10-26 报告：导入番茄小说后插图小得跟一个汉字差不多 —— 那不是缩略图，
# 是**破图**。图片文件名取自 `img.alt`（中文 + 全角标点），而 XHTML 的 src 是
# URI，必须 percent-encode 非 ASCII；严格解析器加载失败，只剩破图占位符。

def _png_bytes(w: int = 800, h: int = 600) -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 100, 50)).save(buf, format="PNG")
    return buf.getvalue()


def _build_with_image(tmp_path, alt="大概是这么个位置，学到后面就知道这个图怎么看了"):
    from novelbase.models.novel import Illustration

    img = Illustration(raw_data=_png_bytes(), alt=alt, insert=6)
    chapters = [
        Chapter(id="c1", url="http://x/1", novel_id="n1", title="带图章节", order=1,
                content="前面一段话。\n\n中间这一段里插了图，后面还有字。", images=[img]),
    ]
    novel = Novel(title="插图测试", url="http://x/book", serial=1,
                  author="作者", description="简介", chapters=chapters)
    opts = EPUBExportOptions(output_path=str(tmp_path), enabled=True)
    return export(chapters, novel, opts)


def test_image_src_is_pure_ascii(tmp_path):
    """文件名不得含中文/全角标点：src 是 URI，严格阅读器不认未编码的非 ASCII。"""
    path = _build_with_image(tmp_path)
    with zipfile.ZipFile(path) as zf:
        names = [n for n in zf.namelist() if n.startswith("OEBPS/images/")]
        xhtml = zf.read("OEBPS/chapter_0001.xhtml").decode("utf-8")
    assert names, "没有写出任何图片"
    for n in names:
        assert n.isascii(), f"zip 内图片文件名含非 ASCII: {n!r}"
    import re
    srcs = re.findall(r'<img[^>]+src="([^"]+)"', xhtml)
    assert srcs, "xhtml 里没有 img"
    for src in srcs:
        assert src.isascii(), f"img src 含非 ASCII（会让阅读器加载失败）：{src!r}"


def test_image_not_nested_inside_paragraph(tmp_path):
    """<img> 不能裸嵌在 <p> 内 —— 否则与正文混排、受 text-indent 影响。"""
    path = _build_with_image(tmp_path)
    with zipfile.ZipFile(path) as zf:
        xhtml = zf.read("OEBPS/chapter_0001.xhtml").decode("utf-8")
    import re
    nested = re.search(r"<p>(?:(?!</p>).)*<img", xhtml, re.S)
    assert not nested, f"img 仍嵌在段落内：{nested.group(0)[-120:] if nested else ''}"
    assert 'class="illustration"' in xhtml, "img 缺少块级包裹容器"


def test_image_has_inline_block_style(tmp_path):
    """关键尺寸/块级样式内联，避免阅读器忽略外部 CSS 时图片退化成行内小图。"""
    path = _build_with_image(tmp_path)
    with zipfile.ZipFile(path) as zf:
        xhtml = zf.read("OEBPS/chapter_0001.xhtml").decode("utf-8")
    import re
    tag = re.search(r"<img[^>]*>", xhtml)
    assert tag, "没有 img 标签"
    style = tag.group(0)
    assert "max-width" in style and "display" in style, f"img 缺少内联样式：{style}"
