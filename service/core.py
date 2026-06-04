"""核心业务逻辑 — 下载、导出、存储查询。"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from nldlder import get_exporter_options, get_exporters
from nldlder.core.exceptions import AntiCrawlError
from nldlder.core.storage import Storage

from .config import APP_DATA
from .progress import emit, finish
from .tasks import create_task, update_task, set_status

if TYPE_CHECKING:
    from nldlder import NovelDownloader, Options
    from nldlder.models.novel import Novel


def _do_export(novel: Novel, grp: str, fmts: dict, task_id: str = ""):
    """执行导出（所有 enabled 格式）。"""
    registered = get_exporters()
    opt_map = get_exporter_options()
    for fmt, fc in fmts.items():
        if not fc.get("enabled", True):
            continue
        ecls = registered.get(fmt)
        ocls = opt_map.get(fmt)
        if ecls is None or ocls is None:
            continue
        raw = fc.get("output_path", "").replace("{group}", grp)
        extra = {}
        for k in ("encoding", "file_name_template", "extension", "css_style", "include_toc"):
            if k in fc:
                extra[k] = fc[k]
        eopt = ocls(output_path=raw, **extra)
        exporter = ecls(options=eopt, novel=novel)
        exporter.export(novel.chapters)
        if task_id:
            emit(task_id, "log", f"  导出: {fmt}")


def download_novel(url: str, task_id: str, dl: NovelDownloader,
                   group: str, format_configs: dict, storage: Storage):
    """下载单个小说：获取信息 → 章节列表 → 合并本地 → 下载新章 → 导出。"""
    _group = group

    try:
        emit(task_id, "log", "正在获取小说信息...")
        novel = dl.fetch_novel(url)
        emit(task_id, "log", f"  书名：{novel.title}  |  作者：{novel.author}  |  字数：{novel.count or '未知'}")
        storage.save_meta(novel)
        create_task(task_id, title=novel.title, total=0)
        set_status(task_id, "downloading", "获取章节列表中...")

        emit(task_id, "log", "正在获取章节列表...")
        chapters = dl.fetch_chapter_list(novel)
        total_chapters = len(chapters)
        emit(task_id, "log", f"  共 {total_chapters} 章")
        novel.update_chapter(chapters)

        local = storage.load_chapters(novel.id)
        if local:
            novel.update_chapter(local)

        incomplete = novel.chapters.get_incompleted_chapters()
        target = list(incomplete) if incomplete else []
        already_downloaded = total_chapters - len(target) if target else total_chapters

        update_task(task_id, total=total_chapters, downloaded=already_downloaded)
        emit(task_id, "progress", f"  已下载 {already_downloaded}/{total_chapters} 章",
             downloaded=already_downloaded, total=total_chapters)

        if not target:
            emit(task_id, "log", "  所有章节已下载完毕")
        else:
            emit(task_id, "log", f"  待下载: {len(target)} 章")
            set_status(task_id, "downloading", f"下载中 0/{len(target)}")
            dl._progress = type(dl._progress)("")

            def _on_batch(ch):
                storage.save_chapter(novel, ch)
                novel.update_chapter(ch)
                current = already_downloaded + len(novel.chapters) - len(target)
                update_task(task_id, downloaded=current,
                            message=f"下载中 {len(novel.chapters) - len(target)}/{total_chapters}")
                emit(task_id, "progress",
                     f"  已下载 {len(ch)} 章 ({ch[-1].title})",
                     downloaded=current, total=total_chapters)

            try:
                downloaded = dl.download_chapters(target, on_batch_complete=_on_batch)
                emit(task_id, "log", f"  下载完成: {len(downloaded)} 章")
            except AntiCrawlError:
                r = dl.progress.remaining
                emit(task_id, "error",
                     f"触发反爬，保存已下载部分（剩余 {r} 章未下载）..." if r else "触发反爬，保存已下载部分...")
                if dl.progress.downloaded_chapters:
                    storage.save_chapter(novel, dl.progress.downloaded_chapters)
                    novel.update_chapter(dl.progress.downloaded_chapters)
                set_status(task_id, "error", f"反爬中断，剩余 {r} 章" if r else "反爬中断")
                finish(task_id, "error")
                return

        emit(task_id, "log", "正在导出...")
        _do_export(novel, _group, format_configs, task_id)
        emit(task_id, "done", f"✓ {novel.title} 下载完成",
             downloaded=total_chapters, total=total_chapters)
        set_status(task_id, "done", "下载完成")
    except Exception as e:
        emit(task_id, "error", f"下载失败: {e}")
        set_status(task_id, "error", str(e))
        try:
            if dl.progress.downloaded_chapters:
                storage.save_chapter(novel, dl.progress.downloaded_chapters)
                novel.update_chapter(dl.progress.downloaded_chapters)
                emit(task_id, "log", f"已保存 {len(dl.progress.downloaded_chapters)} 章已下载内容")
        except Exception:
            pass
        finish(task_id, "error")
        return
    finish(task_id, "done")


def _infer_group_from_exports(novel_id: str, title: str) -> str:
    """从 exports 目录推断分组，未匹配则回退到 config.yaml 的 group。"""
    exports_dir = APP_DATA / "exports"
    if exports_dir.exists():
        for group_dir in sorted(exports_dir.iterdir()):
            if not group_dir.is_dir():
                continue
            for novel_dir in group_dir.iterdir():
                if novel_dir.is_dir() and novel_dir.name == title:
                    return group_dir.name
    # fallback: config.yaml 的 group
    cfg_path = APP_DATA / "config" / "config.yaml"
    if cfg_path.exists():
        import yaml
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return cfg.get("group", "default") or "default"
    return "default"


def get_stored_novels(storage: Storage) -> list[dict]:
    """返回已存储小说的元数据列表。group 从 exports 目录结构推断。"""
    result = []
    sd = APP_DATA / "storage"
    if not sd.exists():
        return result
    for d in sorted(sd.iterdir(), key=lambda x: x.name):
        if not d.is_dir():
            continue
        meta = storage.load_meta(d.name)
        if meta is None:
            continue
        chapters_dir = d / "chapters"
        downloaded = 0
        if chapters_dir.is_dir():
            downloaded = sum(1 for _ in chapters_dir.glob("*.json"))
        group = _infer_group_from_exports(meta.id, meta.title)
        result.append({
            "id": meta.id, "title": meta.title, "author": meta.author,
            "url": meta.url, "serial": meta.serial,
            "downloaded": downloaded, "tags": list(meta.tags or []),
            "group": group,
        })
    return result


def get_chapter_count(storage: Storage, novel_id: str) -> int:
    """快速获取已下载章节数（不加载全部章节内容）。"""
    chapters_dir = storage.get_chapters_path(novel_id)
    if not chapters_dir.is_dir():
        return 0
    return sum(1 for _ in chapters_dir.glob("*.json"))
