"""API 路由（搜索、下载、更新、导出、设置保存、登录等）。"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path
from urllib.parse import unquote_plus

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, HTMLResponse

from nldlder import (
    NovelDownloader, Options, create_engine,
    get_exporters, get_exporter_options,
    search, login,
)
from nldlder.core.exceptions import AntiCrawlError

from .. import state
from ..config import APP_DATA, CONFIG_DIR, build_options, load_configs
from ..core import download_novel, get_stored_novels, _do_export
from ..progress import emit, finish, sse_progress

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════
# 搜索
# ═══════════════════════════════════════════════════════════════════

@router.get("/search")
async def search_novels(q: str, platform: str = "fanqie",
                        page: int = 0):
    try:
        result = search(platform, q, state.engine, page=page)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    if not result:
        return JSONResponse({"results": []})
    data = []
    for r in result:
        data.append({
            "title": getattr(r, "title", ""),
            "author": getattr(r, "author", ""),
            "url": getattr(r, "url", ""),
            "description": getattr(r, "description", ""),
        })
    return JSONResponse({"results": data})


# ═══════════════════════════════════════════════════════════════════
# 下载
# ═══════════════════════════════════════════════════════════════════

@router.post("/download")
async def download_route(request: Request, url: str = "", task_id: str = ""):
    if not url:
        body = await request.body()
        for part in body.decode().split("&"):
            if part.startswith("url="):
                url = unquote_plus(part[4:])
                break
    if not url:
        return JSONResponse({"error": "missing url"}, status_code=400)
    if not task_id:
        task_id = str(uuid.uuid4())
    emit(task_id, "log", "任务已创建")
    threading.Thread(
        target=download_novel,
        args=(url, task_id, state.dl, state.group, state.format_configs, state.storage),
        daemon=True,
    ).start()
    return JSONResponse({"task_id": task_id})


@router.post("/update/{novel_id}")
async def update_novel(novel_id: str, task_id: str = ""):
    if not task_id:
        task_id = str(uuid.uuid4())
    meta = state.storage.load_meta(novel_id)
    if meta is None:
        emit(task_id, "error", "小说未找到")
        finish(task_id, "error")
        return JSONResponse({"error": "not found"}, status_code=404)
    emit(task_id, "log", f"更新: {meta.title}")
    threading.Thread(
        target=download_novel,
        args=(meta.url, task_id, state.dl, state.group, state.format_configs, state.storage),
        daemon=True,
    ).start()
    return JSONResponse({"task_id": task_id})


@router.post("/update_all")
async def update_all(task_id: str = ""):
    if not task_id:
        task_id = str(uuid.uuid4())
    novels = get_stored_novels(state.storage)
    if not novels:
        emit(task_id, "error", "无已存储小说")
        finish(task_id, "error")
        return JSONResponse({"error": "no novels"}, status_code=404)

    def _run():
        for n in novels:
            emit(task_id, "log", f"── 更新: {n['title']} ──")
            download_novel(n["url"], task_id, state.dl, state.group, state.format_configs, state.storage)
        emit(task_id, "done", "全部更新完成")
        finish(task_id, "done")

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"task_id": task_id})


# ═══════════════════════════════════════════════════════════════════
# 导出
# ═══════════════════════════════════════════════════════════════════

@router.post("/export/{novel_id}")
async def export_novel(novel_id: str, task_id: str = ""):
    if not task_id:
        task_id = str(uuid.uuid4())
    meta = state.storage.load_meta(novel_id)
    if meta is None:
        emit(task_id, "error", "小说未找到")
        finish(task_id, "error")
        return JSONResponse({"error": "not found"}, status_code=404)
    emit(task_id, "log", f"导出: {meta.title}")
    local = state.storage.load_chapters(novel_id)
    if local:
        meta.update_chapter(local)
    try:
        _do_export(meta, state.group, state.format_configs, task_id)
        emit(task_id, "done", "导出完成")
        finish(task_id, "done")
    except Exception as e:
        emit(task_id, "error", str(e))
        finish(task_id, "error")
    return JSONResponse({"task_id": task_id})


@router.post("/export_all")
async def export_all(task_id: str = ""):
    if not task_id:
        task_id = str(uuid.uuid4())
    novels = get_stored_novels(state.storage)
    if not novels:
        emit(task_id, "error", "无已存储小说")
        finish(task_id, "error")
        return JSONResponse({"error": "no novels"}, status_code=404)

    def _run():
        for n in novels:
            emit(task_id, "log", f"── 导出: {n['title']} ──")
            meta = state.storage.load_meta(n["id"])
            if meta:
                local = state.storage.load_chapters(n["id"])
                if local:
                    meta.update_chapter(local)
                _do_export(meta, state.group, state.format_configs, task_id)
        emit(task_id, "done", "全部导出完成")
        finish(task_id, "done")

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"task_id": task_id})


@router.post("/export_selected")
async def export_selected(task_id: str = "", dir: str = "", fmts: str = ""):
    """重新导出：选择目录和格式，导出全部已存储小说。"""
    if not task_id:
        task_id = str(uuid.uuid4())

    novels = get_stored_novels(state.storage)
    if not novels:
        emit(task_id, "error", "无已存储小说")
        finish(task_id, "error")
        return JSONResponse({"error": "no novels"}, status_code=404)

    selected_fmts = [f.strip() for f in fmts.split(",") if f.strip()] if fmts else []
    if not selected_fmts:
        emit(task_id, "error", "未选择导出格式")
        finish(task_id, "error")
        return JSONResponse({"error": "no formats"}, status_code=400)

    def _run():
        for n in novels:
            emit(task_id, "log", f"── 导出: {n['title']} ──")
            meta = state.storage.load_meta(n["id"])
            if meta:
                local = state.storage.load_chapters(n["id"])
                if local:
                    meta.update_chapter(local)
                custom_fmts = {}
                for fmt_name in selected_fmts:
                    fc = state.format_configs.get(fmt_name, {})
                    fc = dict(fc)
                    fc["enabled"] = True
                    if dir:
                        fc["output_path"] = str(Path(dir) / "{group}" / "{title}" / "{file_name_template}")
                    custom_fmts[fmt_name] = fc
                _do_export(meta, state.group, custom_fmts, task_id)
        emit(task_id, "done", "导出完成")
        finish(task_id, "done")

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"task_id": task_id})


# ═══════════════════════════════════════════════════════════════════
# 存储查询
# ═══════════════════════════════════════════════════════════════════

@router.get("/api/novels")
async def api_novels():
    return JSONResponse(get_stored_novels(state.storage))


@router.get("/api/export_dirs")
async def api_export_dirs():
    """返回 app_data/exports/ 下的可用导出目录列表。"""
    export_dir = APP_DATA / "exports"
    dirs = []
    if export_dir.exists():
        dirs = sorted(d.name for d in export_dir.iterdir() if d.is_dir())
    return JSONResponse({"dirs": dirs})


# ═══════════════════════════════════════════════════════════════════
# 任务管理
# ═══════════════════════════════════════════════════════════════════

@router.get("/api/tasks")
async def api_tasks():
    """返回当前活跃任务列表。"""
    from ..tasks import get_active_tasks
    return JSONResponse({"tasks": get_active_tasks()})


@router.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消一个正在运行的任务。"""
    from ..tasks import set_status
    set_status(task_id, "cancelled", "已取消")
    emit(task_id, "log", "任务已取消")
    finish(task_id, "cancelled")
    return JSONResponse({"status": "ok"})


# ═══════════════════════════════════════════════════════════════════
# 小说管理
# ═══════════════════════════════════════════════════════════════════

@router.get("/api/novels/{novel_id}/chapters/count")
async def novel_chapter_count(novel_id: str):
    """懒加载：返回小说的总章节数（从章节列表获取，不加载内容）。"""
    from ..core import get_chapter_count
    downloaded = get_chapter_count(state.storage, novel_id)
    meta = state.storage.load_meta(novel_id)
    total = meta.serial if meta else 0
    return JSONResponse({"downloaded": downloaded, "total": total})


# ═══════════════════════════════════════════════════════════════════
# 导出下载
# ═══════════════════════════════════════════════════════════════════

@router.post("/api/export/{novel_id}/download")
async def export_download(novel_id: str, request: Request):
    """选择格式导出小说到 exports/ 目录（静默，不触发浏览器下载）。"""
    body = await request.body()
    params = dict(p.split("=", 1) for p in body.decode().split("&") if "=" in p)
    fmts_str = params.get("fmts", "")
    selected_fmts = [f.strip() for f in fmts_str.split(",") if f.strip()]
    if not selected_fmts:
        return JSONResponse({"error": "missing fmts"}, status_code=400)

    meta = state.storage.load_meta(novel_id)
    if meta is None:
        return JSONResponse({"error": "not found"}, status_code=404)

    local = state.storage.load_chapters(novel_id)
    if local:
        meta.update_chapter(local)

    # 从 exports 推断分组，fallback 到 state.group
    from ..core import _infer_group_from_exports
    grp = _infer_group_from_exports(meta.id, meta.title)

    try:
        custom_fmts = {}
        for fmt_name in selected_fmts:
            fc = dict(state.format_configs.get(fmt_name, {}))
            fc["enabled"] = True
            custom_fmts[fmt_name] = fc
        _do_export(meta, grp, custom_fmts, "")
        exported_to = str(APP_DATA / "exports" / grp / meta.title)
        return JSONResponse({"status": "ok", "exported_to": exported_to})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ═══════════════════════════════════════════════════════════════════
# 格式配置
# ═══════════════════════════════════════════════════════════════════

@router.get("/api/format-configs")
async def api_format_configs():
    """返回当前格式配置。"""
    return JSONResponse(state.format_configs)


# ═══════════════════════════════════════════════════════════════════
# 统一设置保存
# ═══════════════════════════════════════════════════════════════════

@router.post("/api/settings/save_all")
async def save_all_settings(request: Request):
    """统一保存：基本配置 + 站点配置 + 导出配置。"""
    body = await request.body()
    data = json.loads(body.decode()) if body else {}

    # ── 基本配置 ──
    main = data.get("main", {})
    cfg_path = CONFIG_DIR / "config.yaml"
    new_cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    if "mode" in main:
        new_cfg["mode"] = main["mode"]
    if "group" in main:
        new_cfg["group"] = main["group"]
    if "max_workers" in main:
        try:
            mw = int(main["max_workers"])
        except (ValueError, TypeError):
            mw = 3
        if "download" not in new_cfg:
            new_cfg["download"] = {}
        new_cfg["download"]["max_workers"] = mw
    cfg_path.write_text(yaml.safe_dump(new_cfg, allow_unicode=True), encoding="utf-8")

    # ── 站点配置 ──
    site = data.get("site", {})
    site_platform = site.get("platform", state.platform) if site else state.platform
    if site:
        site_path = CONFIG_DIR / "sites" / f"{site_platform}.yaml"
        site_data = yaml.safe_load(site_path.read_text(encoding="utf-8")) if site_path.exists() else {}
        for section in ("browser", "api", "requests"):
            if section in site:
                if section not in site_data:
                    site_data[section] = {}
                for k, v in site[section].items():
                    site_data[section][k] = v
        site_path.write_text(yaml.safe_dump(site_data, allow_unicode=True), encoding="utf-8")

    # ── 导出配置 ──
    exports = data.get("exports", {})
    if exports:
        for fmt_name, fc in exports.items():
            fmt_path = CONFIG_DIR / "formats" / f"{fmt_name}.yaml"
            if fmt_path.exists():
                existing = yaml.safe_load(fmt_path.read_text(encoding="utf-8")) or {}
                if fmt_name in existing and isinstance(existing[fmt_name], dict):
                    existing[fmt_name].update(fc)
                    fmt_path.write_text(yaml.safe_dump(existing, allow_unicode=True), encoding="utf-8")

    # 刷新运行时状态
    state.reload_engine()

    return JSONResponse({"status": "ok"})

@router.post("/switch_platform")
async def switch_platform(platform: str):
    site_path = CONFIG_DIR / "sites" / f"{platform}.yaml"
    site_cfg = yaml.safe_load(site_path.read_text(encoding="utf-8")) if site_path.exists() else {}
    state.site_cfg = site_cfg
    state.options = build_options(state.cfg, site_cfg)
    if state.engine:
        state.engine.close()
    state.engine = create_engine(state.options)
    state.dl = NovelDownloader(state.engine, options=state.options)
    # 返回站点配置供前端刷新表单
    return JSONResponse({
        "status": "ok",
        "platform": platform,
        "site_config": site_cfg,
    })


# ═══════════════════════════════════════════════════════════════════
# 登录
# ═══════════════════════════════════════════════════════════════════

@router.post("/login")
async def login_route(platform: str, task_id: str = ""):
    if not task_id:
        task_id = str(uuid.uuid4())
    emit(task_id, "log", "正在打开浏览器...")

    def _run():
        from nldlder import create_engine, Options
        login_engine = None
        cookie_count = 0
        try:
            browser_cfg = state.site_cfg.get("browser", {})
            login_engine = create_engine(
                Options().set_mode("browser").set_browser_options(
                    headless=False,
                    user_data_dir=browser_cfg.get("user_data_dir") or None,
                    timeout=browser_cfg.get("timeout", 30),
                    retry_times=browser_cfg.get("retry_times", 3),
                    backoff_factor=browser_cfg.get("backoff_factor", 2),
                    delay=tuple(browser_cfg.get("delay", [3, 5])),
                )
            )
            cred = login(platform, login_engine)
            cookie_count = len(cred.cookies) if cred and cred.cookies else 0
            if cookie_count > 0:
                emit(task_id, "log", f"✓ 登录成功！获取到 {cookie_count} 个 cookies")
                site_path = CONFIG_DIR / "sites" / f"{platform}.yaml"
                site_yaml = yaml.safe_load(site_path.read_text(encoding="utf-8")) if site_path.exists() else {}
                if "requests" not in site_yaml:
                    site_yaml["requests"] = {}
                site_yaml["requests"]["cookies"] = cred.cookies
                site_path.write_text(yaml.safe_dump(site_yaml, allow_unicode=True), encoding="utf-8")
                emit(task_id, "done", f"Cookies 已保存到 {site_path}")
            else:
                emit(task_id, "error", "登录完成但未获取到 cookies")
        except Exception as e:
            emit(task_id, "error", f"登录失败: {e}")
        finally:
            if login_engine:
                login_engine.close()
            finish(task_id, "done" if cookie_count else "error")

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"task_id": task_id})


# ═══════════════════════════════════════════════════════════════════
# 设置保存
# ═══════════════════════════════════════════════════════════════════

@router.post("/settings/save")
async def save_main_config(request: Request):
    body = await request.body()
    data = dict(p.split("=", 1) for p in body.decode().split("&") if "=" in p)
    cfg_path = CONFIG_DIR / "config.yaml"
    new_cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    new_cfg["mode"] = data.get("mode", new_cfg.get("mode", "browser"))
    new_cfg["group"] = data.get("group", new_cfg.get("group", "default"))
    try:
        mw = int(data.get("max_workers", "3"))
    except ValueError:
        mw = 3
    if "download" not in new_cfg:
        new_cfg["download"] = {}
    new_cfg["download"]["max_workers"] = mw
    cfg_path.write_text(yaml.safe_dump(new_cfg, allow_unicode=True), encoding="utf-8")

    # 刷新引擎
    state.reload_engine()

    return HTMLResponse("""
    <!DOCTYPE html><html lang="zh"><head>
    <meta charset="UTF-8"><meta http-equiv="refresh" content="0;url=/settings">
    <link rel="stylesheet" href="/static/style.css">
    </head><body>
    <p style="color:var(--success);padding:20px;">✓ 已保存，正在跳转...</p>
    </body></html>
    """)


@router.post("/settings/save_site")
async def save_site_switch(request: Request):
    """切换站点配置页时自动加载对应平台配置。"""
    body = await request.body()
    data = dict(p.split("=", 1) for p in body.decode().split("&") if "=" in p)
    site_platform = data.get("site_platform", state.platform)
    return HTMLResponse(f"""
    <!DOCTYPE html><html lang="zh"><head>
    <meta charset="UTF-8"><meta http-equiv="refresh" content="0;url=/settings/site/{site_platform}">
    <link rel="stylesheet" href="/static/style.css">
    </head><body>
    <p style="color:var(--success);padding:20px;">已切换到 <a href="/settings/site/{site_platform}">编辑 {state.PLATFORM_LABELS.get(site_platform, site_platform)} 配置</a></p>
    </body></html>
    """)


@router.post("/settings/site/save")
async def save_site_config(request: Request):
    body = await request.body()
    data = {}
    for p in body.decode().split("&"):
        if "=" in p:
            k, v = p.split("=", 1)
            data[k] = unquote_plus(v)

    site_platform = data.get("site_platform", "fanqie")
    site_path = CONFIG_DIR / "sites" / f"{site_platform}.yaml"
    site_data = yaml.safe_load(site_path.read_text(encoding="utf-8")) if site_path.exists() else {}

    # Browser
    if "browser" not in site_data:
        site_data["browser"] = {}
    site_data["browser"]["headless"] = data.get("browser_headless", "false") == "true"
    site_data["browser"]["user_data_dir"] = data.get("browser_user_data_dir", "")
    for k, f in [("browser_timeout", "timeout"), ("browser_retry_times", "retry_times")]:
        try:
            site_data["browser"][f] = int(data.get(k, str(site_data["browser"].get(f, 30))))
        except ValueError:
            pass
    delay = data.get("browser_delay", "3,5")
    try:
        parts = [float(x.strip()) for x in delay.split(",")]
        site_data["browser"]["delay"] = [parts[0], parts[1]]
    except (ValueError, IndexError):
        pass

    # API
    if "api" not in site_data:
        site_data["api"] = {}
    if "oiapi" not in site_data["api"]:
        site_data["api"]["oiapi"] = {}
    ak = data.get("api_key", "")
    if ak:
        site_data["api"]["oiapi"]["key"] = ak
    for k, f in [("api_timeout", "timeout"), ("api_batch_size", "batch_size"),
                  ("api_retry_times", "retry_times")]:
        try:
            site_data["api"]["oiapi"][f] = int(data.get(k, str(site_data["api"]["oiapi"].get(f, 30))))
        except ValueError:
            pass

    # Requests
    if "requests" not in site_data:
        site_data["requests"] = {}
    ua = data.get("req_ua", "")
    if ua:
        if "headers" not in site_data["requests"]:
            site_data["requests"]["headers"] = {}
        site_data["requests"]["headers"]["User-Agent"] = ua
    cookies_str = data.get("req_cookies", "")
    if cookies_str:
        try:
            site_data["requests"]["cookies"] = json.loads(cookies_str)
        except json.JSONDecodeError:
            pass
    for k, f in [("req_timeout", "timeout"), ("req_retry_times", "retry_times")]:
        try:
            site_data["requests"][f] = int(data.get(k, str(site_data["requests"].get(f, 30))))
        except ValueError:
            pass

    site_path.write_text(yaml.safe_dump(site_data, allow_unicode=True), encoding="utf-8")

    # 如果保存的站点正是当前使用的，刷新运行时状态
    if site_platform == state.platform:
        state.site_cfg = site_data
        state.options = build_options(state.cfg, site_data)
        if state.engine:
            state.engine.close()
        state.engine = create_engine(state.options)
        state.dl = NovelDownloader(state.engine, options=state.options)

    plat_label = state.PLATFORM_LABELS.get(site_platform, site_platform)
    return HTMLResponse(f"""
    <!DOCTYPE html><html lang="zh"><head>
    <meta charset="UTF-8"><meta http-equiv="refresh" content="0;url=/settings/site/{site_platform}">
    <link rel="stylesheet" href="/static/style.css">
    </head><body>
    <p style="color:var(--success);padding:20px;">✓ {plat_label} 配置已保存，正在跳转...</p>
    </body></html>
    """)


# ═══════════════════════════════════════════════════════════════════
# SSE 进度
# ═══════════════════════════════════════════════════════════════════

@router.get("/progress/{task_id}")
async def progress(task_id: str):
    return await sse_progress(task_id)
