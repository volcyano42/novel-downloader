"""Export 路由 — 3 条。"""
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from backend.schemas import ExportRequest, ExportTaskStatus
from nldlder import NovelDownloader, get_exporters

router = APIRouter(prefix="/api/v1/export", tags=["export"])

_tasks: dict[str, dict] = {}

@router.get("/format")
async def list_formats():
    return [{"id": name, "label": name.upper()} for name in get_exporters()]

@router.post("")
async def trigger_export(body: ExportRequest):
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {"status": "pending", "progress": 0.0}
    try:
        from nldlder import LocalStorage
        from nldlder.core.options import StorageOptions, Options, ExportOptions
        base_dir = Path(__file__).parent.parent.parent / "app_data" / "storage"
        store = LocalStorage(StorageOptions(base_dir=base_dir))
        novel = store.load_meta(body.novel_id)
        if not novel: raise HTTPException(404, "小说不存在")
        chapters = store.load_chapters(body.novel_id)
        if body.chapter_id: chapters = [ch for ch in chapters if ch.id in body.chapter_id]
        novel.update_chapter(chapters)
        opts = Options().set_mode("api")
        if body.txt and body.txt.enabled:
            opts.set_export_options(ExportOptions(format="txt", output_path=body.txt.output_path, enabled=True, file_name_template=body.txt.file_name_template))
        if body.epub and body.epub.enabled:
            opts.set_export_options(ExportOptions(format="epub", output_path=body.epub.output_path, enabled=True, file_name_template=body.epub.file_name_template))
        if body.img and body.img.enabled:
            opts.set_export_options(ExportOptions(format="img", output_path=body.img.output_path, enabled=True, file_name_template=body.img.file_name_template))
        dl = NovelDownloader.from_options(opts); dl.export(novel)
        _tasks[task_id] = {"status": "completed", "progress": 1.0}
    except Exception as e:
        _tasks[task_id] = {"status": "failed", "progress": 0.0, "error": str(e)}
    return {"task_id": task_id}

@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    task = _tasks.get(task_id)
    if not task: raise HTTPException(404, "任务不存在")
    return ExportTaskStatus(task_id=task_id, status=task["status"], progress=task.get("progress", 0.0))
