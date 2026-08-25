# -*- coding: utf-8 -*-
"""Export 路由 — 4 条，支持多格式导出自动打包 ZIP + 浏览器下载。"""
import tempfile
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from backend.schemas import ExportRequest, ExportTaskStatus
from novelbase import export as do_export, get_exporters
from shared.config import get_database_url

router = APIRouter(prefix="/api/v2/export", tags=["export"])

_tasks: dict[str, dict] = {}

def _enabled_formats(body: ExportRequest) -> list[str]:
    formats: list[str] = []
    if body.txt and body.txt.enabled:   formats.append("txt")
    if body.epub and body.epub.enabled: formats.append("epub")
    if body.img and body.img.enabled:   formats.append("img")
    return formats

@router.get("/format")
async def list_formats():
    return [{"id": name, "label": name.upper()} for name in get_exporters()]

@router.post("")
async def trigger_export(body: ExportRequest):
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {"status": "downloading", "progress": 0.0}
    try:
        from novelbase.core.storage import create_storage
        from novelbase.core.options import StorageOptions
        store = create_storage(StorageOptions(
            backend="sqlite",
            database_url=get_database_url(),
        ))
        novel = store.load_meta(body.novel_id)
        if not novel:
            raise HTTPException(404, "小说不存在")
        chapters = store.load_chapters(body.novel_id)
        if body.chapter_id:
            chapters = [ch for ch in chapters if ch.id in body.chapter_id]
        novel.update_chapter(chapters)

        formats = _enabled_formats(body)
        if not formats:
            raise HTTPException(400, "没有启用任何导出格式")

        # 统一导出到临时目录
        export_dir = Path(tempfile.mkdtemp(prefix="nld_export_"))

        if body.txt and body.txt.enabled:
            from novelbase.exporters.txt import TXTExportOptions
            sub = export_dir / "txt"; sub.mkdir()
            opt = TXTExportOptions(
                format="txt", output_path=str(sub), enabled=True,
                file_name_template=body.txt.file_name_template or "{name}",
                encoding=body.txt.encoding)
            do_export(novel, options=opt)
        if body.epub and body.epub.enabled:
            from novelbase.exporters.epub import EPUBExportOptions
            sub = export_dir / "epub"; sub.mkdir()
            opt = EPUBExportOptions(
                format="epub", output_path=str(sub), enabled=True,
                file_name_template=body.epub.file_name_template or "{name}",
                compression=body.epub.compression, compresslevel=body.epub.compresslevel,
                include_toc=body.epub.include_toc, optimize_images=body.epub.optimize_images,
                jpeg_quality=body.epub.jpeg_quality, max_image_width=body.epub.max_image_width)
            do_export(novel, options=opt)
        if body.img and body.img.enabled:
            from novelbase.exporters.img import IMGExportOptions
            sub = export_dir / "img"; sub.mkdir()
            opt = IMGExportOptions(
                format="img", output_path=str(sub), enabled=True,
                file_name_template=body.img.file_name_template or "{n}",
                output_format=body.img.output_format)
            do_export(novel, options=opt)

        # 收集导出文件
        exported: list[Path] = []
        for f in export_dir.rglob("*"):
            if f.is_file():
                exported.append(f)

        if not exported:
            raise RuntimeError("导出未生成任何文件")

        result_path: str
        if len(exported) == 1:
            result_path = str(exported[0])
        else:
            # 多文件 → ZIP
            zip_path = export_dir / f"{novel.title}.zip"
            with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
                for f in exported:
                    zf.write(f, f.relative_to(export_dir))
            result_path = str(zip_path)

        _tasks[task_id] = {
            "status": "completed", "progress": 1.0,
            "formats": formats, "path": result_path,
        }
    except HTTPException:
        raise
    except Exception as e:
        _tasks[task_id] = {"status": "failed", "progress": 0.0, "error": str(e)}
    return {"task_id": task_id}

@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return ExportTaskStatus(
        task_id=task_id,
        status=task["status"],
        progress=task.get("progress", 0.0),
        error=task.get("error"),
    )

@router.get("/download/{task_id}")
async def download_export(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    if task["status"] != "completed":
        raise HTTPException(400, "导出尚未完成")

    file_path = Path(task["path"])
    if not file_path.exists():
        raise HTTPException(404, "导出文件已被清理")

    media_type = "application/zip" if file_path.suffix == ".zip" else "application/octet-stream"
    return FileResponse(file_path, media_type=media_type, filename=file_path.name)
