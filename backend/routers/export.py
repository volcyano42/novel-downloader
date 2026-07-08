"""Export 路由 — 3 条，支持多格式导出自动打包 ZIP。"""
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from backend.schemas import ExportRequest, ExportTaskStatus
from nldlder import NovelDownloader, get_exporters

router = APIRouter(prefix="/api/v1/export", tags=["export"])

_tasks: dict[str, dict] = {}

def _enabled_formats(body: ExportRequest) -> list[str]:
    """返回启用的导出格式列表。"""
    formats: list[str] = []
    if body.txt and body.txt.enabled:
        formats.append("txt")
    if body.epub and body.epub.enabled:
        formats.append("epub")
    if body.img and body.img.enabled:
        formats.append("img")
    return formats

def _collect_exported_files(base_dir: Path, novel_id: str) -> list[Path]:
    """收集导出目录下属于该小说的最新文件。"""
    files: list[Path] = []
    if not base_dir.exists():
        return files
    for p in base_dir.rglob("*"):
        if p.is_file():
            files.append(p)
    return files

@router.get("/format")
async def list_formats():
    return [{"id": name, "label": name.upper()} for name in get_exporters()]

@router.post("")
async def trigger_export(body: ExportRequest):
    task_id = str(uuid.uuid4())[:8]
    _tasks[task_id] = {"status": "downloading", "progress": 0.0}
    try:
        from nldlder.core.storage import create_storage
        from nldlder.core.options import StorageOptions, Options, ExportOptions
        store = create_storage(StorageOptions(
            backend="sqlite",
            database_url="sqlite:///app_data/storage/novels.db",
        ))
        novel = store.load_meta(body.novel_id)
        if not novel:
            raise HTTPException(404, "小说不存在")
        chapters = store.load_chapters(body.novel_id)
        if body.chapter_id:
            chapters = [ch for ch in chapters if ch.id in body.chapter_id]
        novel.update_chapter(chapters)

        # 构建导出选项
        opts = Options().set_mode("api")
        formats = _enabled_formats(body)
        if not formats:
            raise HTTPException(400, "没有启用任何导出格式")

        # 收集输出根目录（统一到一个根下方便打包）
        export_roots: list[Path] = []
        if body.txt and body.txt.enabled:
            root = Path(body.txt.output_path or f"app_data/exports/{novel.title}/txt")
            opts.set_export_options(ExportOptions(format="txt", output_path=str(root), enabled=True,
                file_name_template=body.txt.file_name_template or "{name}"))
            export_roots.append(root.parent if root.name == "txt" else root)
        if body.epub and body.epub.enabled:
            root = Path(body.epub.output_path or f"app_data/exports/{novel.title}/epub")
            opts.set_export_options(ExportOptions(format="epub", output_path=str(root), enabled=True,
                file_name_template=body.epub.file_name_template or "{name}"))
            export_roots.append(root.parent if root.name == "epub" else root)
        if body.img and body.img.enabled:
            root = Path(body.img.output_path or f"app_data/exports/{novel.title}/img")
            opts.set_export_options(ExportOptions(format="img", output_path=str(root), enabled=True,
                file_name_template=body.img.file_name_template or "{n}"))
            export_roots.append(root.parent if root.name == "img" else root)

        # 执行导出
        dl = NovelDownloader.from_options(opts)
        dl.export(novel)

        # 多格式 → 打包 ZIP
        result_path: str | None = None
        if len(formats) >= 2:
            # 找到共同父目录
            parents = set(str(r.resolve()) for r in export_roots)
            if len(parents) == 1:
                common = export_roots[0].resolve()
                archive_name = common / f"{novel.title}.zip"
                # 收集所有导出文件
                files = list(common.rglob("*"))
                if files:
                    # 创建 zip，保留相对路径
                    import zipfile
                    with zipfile.ZipFile(str(archive_name), "w", zipfile.ZIP_DEFLATED) as zf:
                        for f in files:
                            if f.is_file() and f.suffix != ".zip":
                                zf.write(f, f.relative_to(common))
                    # 删除原始文件，保留 zip
                    for f in files:
                        if f.is_file() and f.suffix != ".zip":
                            f.unlink()
                    # 清理空文件夹
                    for d in sorted(common.rglob("*"), reverse=True):
                        if d.is_dir() and d != common and not any(d.iterdir()):
                            d.rmdir()
                    result_path = str(archive_name)
        if not result_path and export_roots:
            result_path = str(export_roots[0])

        _tasks[task_id] = {
            "status": "completed", "progress": 1.0,
            "formats": formats, "path": result_path,
        }
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
    )
