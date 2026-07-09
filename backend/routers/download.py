"""Download 路由 — 8 条，对接 search + NovelDownloader + 后台下载任务管理。"""
import hashlib
import json
import os
import threading
import uuid
from base64 import b64encode
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from backend.schemas import FetchMetaRequest, DownloadChapterRequest, SearchResultData, ChapterBrief
from backend.routers.config import load_config
from nldlder import NovelDownloader, Options, create_engine, get_fetchers, search

router = APIRouter(prefix="/api/v1/download", tags=["download"])

_engines: dict[str, tuple[object, str]] = {}

# ── 下载任务管理器 ──────────────────────────────────────────

_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()

def _run_download(task: dict, engine_id: str, mode: str | None, provider: str | None = None):
    """后台线程：逐章下载，支持暂停/恢复。"""
    from nldlder.models.novel import Chapter, Chapters, Novel
    from nldlder.core.storage import create_storage
    from nldlder.core.options import StorageOptions
    from nldlder.core.downloader import get_fetcher_for_id

    # API 模式自动发现 provider（如果前端没指定）
    platform = None
    if mode == "api" and not provider:
        from nldlder.core.downloader import get_fetcher_for_id as _gffi, get_fetchers as _gf
        fetcher_cls = _gffi(task["novel_id"])
        if fetcher_cls:
            # 反向查 get_fetchers() 字典，用 fetcher class 匹配正确的平台名
            for name, cls in _gf().items():
                if cls is fetcher_cls:
                    platform = name
                    break
            site = _load_site_cfg(platform) if platform else {}
            api_section = site.get("api", {}) if isinstance(site.get("api"), dict) else {}
            for name, prov in api_section.items():
                if isinstance(prov, dict) and prov.get("enabled", True):
                    provider = name
                    break

    try:
        engine = _get_engine(engine_id, mode, provider=provider, platform=platform)
        dl = NovelDownloader(engine)
        store = create_storage(StorageOptions(
            backend="sqlite",
            database_url="sqlite:///app_data/storage/novels.db",
        ))

        # 先保存小说元数据
        novel_url = task.get("novel_url", "")
        if novel_url:
            try:
                meta = dl.fetch_meta(novel_url)
                store.save_meta(meta)
            except Exception:
                pass
        novel = Novel(title=task["title"], url=novel_url, id=task["novel_id"], serial=0, author="", description="")

        for ch_data in task["chapters"]:
            if task["_pause"].is_set():
                task["status"] = "paused"
                task["_pause"].wait()
                task["status"] = "downloading"

            ch = Chapter(id=ch_data["id"], url=ch_data["url"], novel_id=task["novel_id"],
                         title=ch_data["title"], order=ch_data["order"], volume=ch_data.get("volume"))
            task["current_title"] = ch.title
            try:
                downloaded = dl.resolve_chapter(ch)
                if downloaded is not None:
                    store.save_chapter(novel, Chapters(chapters=[downloaded]))
                else:
                    msg = f"章节不可获取: {ch.title}"
                    with _tasks_lock:
                        task["errors"].append(msg)
                        task["detail"] = msg
            except Exception as e:
                msg = f"{ch.title}: {e}"
                with _tasks_lock:
                    task["errors"].append(msg)
                    task["detail"] = msg
            task["progress"] += 1
        task["status"] = "completed"
        if task["errors"]:
            task["error"] = "; ".join(task["errors"][:3])
    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)

def _mode_fingerprint(mode_cfg: dict) -> str:
    """对模式配置做哈希，用于检测选项变更。"""
    return hashlib.md5(json.dumps(mode_cfg, sort_keys=True, default=str).encode()).hexdigest()

def _encode_cover(cover) -> dict | None:
    if not cover: return None
    if not cover.raw_data: return {"raw_data": None, "alt": cover.alt, "url": cover.url, "format": cover.image_format}

    fmt = cover.image_format
    if fmt in ("heic", "heif"):
        converted = cover.convert("jpeg", quality=90)
        if converted.image_format != "jpeg":
            return {"raw_data": None, "alt": cover.alt, "url": cover.url, "format": fmt}
        cover = converted
        fmt = "jpeg"

    return {"raw_data": b64encode(cover.raw_data).decode(), "alt": cover.alt, "url": cover.url, "format": fmt}

def _load_site_cfg(platform: str) -> dict:
    """加载 app_data/config/sites/{platform}.yaml"""
    import yaml
    site_path = Path(__file__).parent.parent.parent / "app_data" / "config" / "sites" / f"{platform}.yaml"
    if site_path.exists():
        with open(site_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def _find_provider_options(provider: str) -> dict | None:
    """在所有站点配置中查找指定 API provider 的选项（返回第一个启用的）。"""
    import yaml
    sites_dir = Path(__file__).parent.parent.parent / "app_data" / "config" / "sites"
    if not sites_dir.is_dir():
        return None
    for p in sites_dir.glob("*.yaml"):
        with open(p, encoding="utf-8") as f:
            site = yaml.safe_load(f) or {}
        api = site.get("api", {})
        if isinstance(api, dict) and provider in api:
            prov_cfg = api[provider]
            if isinstance(prov_cfg, dict) and prov_cfg.get("enabled", True):
                return prov_cfg
    return None

def _get_engine(engine_id: str, mode: str | None = None, provider: str | None = None, platform: str | None = None):
    cfg = load_config()
    if mode is None:
        mode = cfg.get("mode", "browser")

    # ── API 模式：自动发现 platform 首个启用 provider ──
    if mode == "api" and not provider and platform:
        site = _load_site_cfg(platform)
        api_section = site.get("api", {}) if isinstance(site.get("api"), dict) else {}
        for name, prov in api_section.items():
            if isinstance(prov, dict) and prov.get("enabled", True):
                provider = name
                break

    # ── API 模式：一个 provider 一个 engine ──
    if mode == "api" and provider:
        prov_cfg = _find_provider_options(provider) or {}
        key = os.environ.get(f"{provider.upper()}_API_KEY", "") or prov_cfg.get("key", "")
        fp = _mode_fingerprint({**prov_cfg, "key": key})
        cache_key = f"{engine_id}:api:{provider}"
        if cache_key in _engines:
            stored_engine, stored_fp = _engines[cache_key]
            if stored_fp == fp:
                return stored_engine
            try:
                stored_engine.close()
            except Exception:
                pass
            del _engines[cache_key]
        opts = Options().set_mode("api").set_api_options(
            name=provider,
            key=key,
            delay=tuple(prov_cfg.get("delay", [3, 5])),
            timeout=prov_cfg.get("timeout", 30),
            retry_times=prov_cfg.get("retry_times", 3),
            backoff_factor=prov_cfg.get("backoff_factor", 2),
            params=prov_cfg.get("params"),
        )
        engine = create_engine(opts)
        _engines[cache_key] = (engine, fp)
        return engine

    # ── browser / requests / api(无provider) 模式 ──
    dl = cfg.get("download", {})
    mode_cfg = dl.get(mode, {})
    fp = _mode_fingerprint(mode_cfg)
    cache_key = f"{engine_id}:{mode}"

    if cache_key in _engines:
        stored_engine, stored_fp = _engines[cache_key]
        if stored_fp == fp:
            return stored_engine
        try:
            stored_engine.close()
        except Exception:
            pass
        del _engines[cache_key]

    opts = Options().set_mode(mode)
    if mode == "browser":
        opts = opts.set_browser_options(
            headless=mode_cfg.get("headless", True),
            browser_type=mode_cfg.get("browser_type", "chromium"),
            user_data_dir=mode_cfg.get("user_data_dir"),
            delay=tuple(mode_cfg.get("delay", [3, 5])),
            timeout=mode_cfg.get("timeout", 30),
            retry_times=mode_cfg.get("retry_times", 3),
            backoff_factor=mode_cfg.get("backoff_factor", 2),
        )
    elif mode == "requests":
        opts = opts.set_requests_options(
            delay=tuple(mode_cfg.get("delay", [3, 5])),
            timeout=mode_cfg.get("timeout", 30),
            retry_times=mode_cfg.get("retry_times", 3),
            backoff_factor=mode_cfg.get("backoff_factor", 2),
        )
    elif mode == "api":
        opts = opts.set_api_options(
            name=mode_cfg.get("name", "default"),
            delay=tuple(mode_cfg.get("delay", [3, 5])),
            timeout=mode_cfg.get("timeout", 30),
            retry_times=mode_cfg.get("retry_times", 3),
            backoff_factor=mode_cfg.get("backoff_factor", 2),
        )

    engine = create_engine(opts)
    _engines[cache_key] = (engine, fp)
    return engine

@router.get("/search")
async def search_novels(platform: str = Query(...), query: str = Query(...), page: int = Query(1), mode: str | None = Query(None), provider: str | None = Query(None), engine_id: str = Query("default")):
    from nldlder.core.downloader import get_fetcher_for_url, get_fetcher_for_id

    engine = _get_engine(engine_id, mode, provider=provider, platform=platform)

    # ── URL / ID 直搜：跳过关键词，直接 fetch_meta ──
    if query.startswith("http://") or query.startswith("https://"):
        fetcher_cls = get_fetcher_for_url(query)
        if fetcher_cls:
            dl = NovelDownloader(engine)
            try:
                novel = dl.fetch_meta(query)
                return [SearchResultData(title=novel.title, author=novel.author, url=novel.url, description=novel.description)]
            except Exception as e:
                raise HTTPException(500, str(e))

    if query.isdigit():
        fetcher_cls = get_fetcher_for_id(query)
        if fetcher_cls:
            try:
                novel = fetcher_cls().fetch_novel_info(url=query, engine=engine)
                return [SearchResultData(title=novel.title, author=novel.author, url=novel.url, description=novel.description)]
            except Exception as e:
                raise HTTPException(500, str(e))

    # ── 关键词搜索 ──
    try: results = search(platform, query, engine, page=page)
    except Exception as e: raise HTTPException(500, str(e))
    return [SearchResultData(title=r.title, author=r.author, url=r.url, description=r.description) for r in results]

@router.post("/novel")
async def fetch_meta(body: FetchMetaRequest, mode: str | None = Query(None), provider: str | None = Query(None)):
    engine = _get_engine(body.engine_id, mode, provider=provider); dl = NovelDownloader(engine)
    try: novel = dl.fetch_meta(body.url)
    except Exception as e: raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count,
            "cover": _encode_cover(novel.cover)}

@router.get("/novel/{novel_id}")
async def get_remote_novel(novel_id: str, url: str = Query(...), engine_id: str = Query("default"), mode: str | None = Query(None), provider: str | None = Query(None)):
    engine = _get_engine(engine_id, mode, provider=provider); dl = NovelDownloader(engine)
    try: novel = dl.fetch_meta(url)
    except Exception as e: raise HTTPException(500, str(e))
    return {"title": novel.title, "url": novel.url, "id": novel.id, "serial": novel.serial,
            "author": novel.author, "description": novel.description,
            "tags": list(novel.tags) if novel.tags else None, "count": novel.count}

@router.get("/novel/{novel_id}/chapters")
async def fetch_chapter_list(novel_id: str, url: str = Query(...), engine_id: str = Query("default"), mode: str | None = Query(None), provider: str | None = Query(None)):
    engine = _get_engine(engine_id, mode, provider=provider); dl = NovelDownloader(engine)
    try: chapters = dl.fetch_chapter_list(url)
    except Exception as e: raise HTTPException(500, str(e))
    return [ChapterBrief(id=ch.id, url=ch.url, novel_id=ch.novel_id, title=ch.title,
                         order=ch.order, volume=ch.volume, count=ch.count) for ch in chapters]

@router.post("/novel/{novel_id}/chapter")
async def download_chapters(novel_id: str, body: list[DownloadChapterRequest],
                            title: str = Query(""), engine_id: str = Query("default"),
                            mode: str | None = Query(None), provider: str | None = Query(None),
                            novel_url: str = Query("")):
    task_id = uuid.uuid4().hex[:12]
    chapters_data = [{"id": ch.id, "url": ch.url, "title": ch.title,
                       "order": ch.order, "volume": ch.volume} for ch in body]
    task = {
        "task_id": task_id, "novel_id": novel_id, "title": title,
        "total": len(chapters_data), "progress": 0, "status": "downloading",
        "error": None, "errors": [], "current_title": "", "detail": "",
        "chapters": chapters_data, "novel_url": novel_url,
        "_pause": threading.Event(),
    }
    with _tasks_lock:
        _tasks[task_id] = task
    threading.Thread(target=_run_download, args=(task, engine_id, mode, provider), daemon=True).start()
    return {"task_id": task_id, "total": task["total"]}

@router.get("/tasks")
async def list_tasks():
    with _tasks_lock:
        return [{k: v for k, v in t.items() if not k.startswith("_") and k not in ("chapters",)}
                for t in _tasks.values()]

@router.post("/task/{task_id}/pause")
async def pause_task(task_id: str):
    with _tasks_lock:
        t = _tasks.get(task_id)
        if not t: raise HTTPException(404, "任务不存在")
        if t["status"] == "downloading":
            t["_pause"].set()
    return {"status": "ok"}

@router.post("/task/{task_id}/resume")
async def resume_task(task_id: str):
    with _tasks_lock:
        t = _tasks.get(task_id)
        if not t: raise HTTPException(404, "任务不存在")
        if t["status"] == "paused":
            t["_pause"].clear()
    return {"status": "ok"}

@router.delete("/task/{task_id}")
async def delete_task(task_id: str):
    with _tasks_lock:
        t = _tasks.pop(task_id, None)
        if not t: raise HTTPException(404, "任务不存在")
    return {"status": "ok"}

@router.get("/platform")
async def list_platforms():
    return [{"id": name, "label": cls.__name__ if hasattr(cls, "__name__") else name} for name, cls in get_fetchers().items()]
