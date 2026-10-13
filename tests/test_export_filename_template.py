"""导出文件名模板契约：默认占位符统一用 {title}。

回归背景（WebUI 导出 txt 失败，toast 显示 "导出失败：'name'"）：
前端只发 `{novel_id, chapter_id, txt: {enabled: true}}`，后端 schema 曾把
`file_name_template` 默认成 `{name}`，而 txt 导出器的模板变量表里没有 `name`
（`app_data/config/formats/txt.yaml` 声明的合法占位符是 `{title}`），
txt 导出器用 `format(**variables)` 抛 `KeyError('name')` → `str(e)` 即 `'name'`。
"""
import asyncio
from pathlib import Path

from backend.routers import export as export_router
from backend.schemas import EPUBExportOptions, ExportRequest, TXTExportOptions
from novelbase import export as do_export
from novelbase.core.options import ExportOptions
from novelbase.exporters.epub import EPUBExportOptions as CoreEpubOptions
from novelbase.exporters.epub import _build_file_path as epub_build_file_path
from novelbase.exporters.txt import TXTExportOptions as CoreTxtOptions


def test_default_file_name_templates_use_title():
    assert TXTExportOptions().file_name_template == "{title}"
    assert EPUBExportOptions().file_name_template == "{title}"
    assert ExportOptions().file_name_template == "{title}"


def test_default_output_paths_drop_name_placeholder():
    assert "{name}" not in TXTExportOptions().output_path
    assert "{name}" not in EPUBExportOptions().output_path


def test_txt_and_epub_accept_backend_default_template(tmp_path, novel):
    """后端默认模板必须落在导出器的变量表内，否则 format 抛 KeyError。"""
    txt_opt = CoreTxtOptions(
        format="txt", output_path=str(tmp_path), enabled=True,
        file_name_template=TXTExportOptions().file_name_template, encoding="utf-8",
    )
    assert Path(do_export(novel, options=txt_opt)).name == f"{novel.title}.txt"

    epub_opt = CoreEpubOptions(
        format="epub", output_path=str(tmp_path), enabled=True,
        file_name_template=EPUBExportOptions().file_name_template,
    )
    assert epub_build_file_path(novel, epub_opt).name == f"{novel.title}.epub"


def test_trigger_export_txt_with_frontend_body(monkeypatch, tmp_path, novel, chapters):
    """复现用户路径：前端请求体（不带 file_name_template）→ txt 导出完成。"""
    class _Store:
        def load_meta(self, novel_id: str):
            return novel

        def load_chapters(self, novel_id: str, include_images: bool = True):
            return chapters

    def _fake_mkdtemp(prefix: str = "") -> str:
        target = tmp_path / "export"
        target.mkdir(exist_ok=True)
        return str(target)

    monkeypatch.setattr("novelbase.core.storage.create_storage", lambda config: _Store())
    monkeypatch.setattr(export_router.tempfile, "mkdtemp", _fake_mkdtemp)

    body = ExportRequest(novel_id=novel.id, chapter_id=None, txt=TXTExportOptions(enabled=True))
    task_id = asyncio.run(export_router.trigger_export(body))["task_id"]
    try:
        task = export_router._tasks[task_id]
        assert task["status"] == "completed", task.get("error")
        assert Path(task["path"]).name == f"{novel.title}.txt"
    finally:
        export_router._tasks.pop(task_id, None)
