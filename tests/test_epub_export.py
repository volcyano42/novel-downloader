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
