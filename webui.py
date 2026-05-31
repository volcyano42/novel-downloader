"""
novel-downloader Web UI — service.py
FastAPI + SSE 进度推送，功能与 main.py 对等
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse

from nldlder import (
    NovelDownloader, Options, create_engine,
    get_exporter_options, get_exporters,
    search, login,
)
from nldlder.core.storage import Storage
from nldlder.core.exceptions import AntiCrawlError

APP_DATA = Path(__file__).parent / "app_data"
CONFIG_DIR = APP_DATA / "config"

# ═══════════════════════════════════════════════════════════════════
# 配置加载（与 main.py 一致）
# ═══════════════════════════════════════════════════════════════════

def load_configs():
    cfg_path = CONFIG_DIR / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    site_path = CONFIG_DIR / "sites" / "fanqie.yaml"
    site = yaml.safe_load(site_path.read_text(encoding="utf-8")) if site_path.exists() else {}
    fmts = {}
    fmt_dir = CONFIG_DIR / "formats"
    if fmt_dir.exists():
        for f in fmt_dir.glob("*.yaml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            for k, v in data.items():
                fmts[k] = v
    return cfg, site, fmts


def build_options(cfg: dict, site_cfg: dict) -> Options:
    options = Options()
    mode = cfg.get("mode", "browser")
    options.set_mode(mode)
    dl_cfg = cfg.get("download", {})
    options.set_download_options(max_workers=dl_cfg.get("max_workers", 3))
    if mode == "browser":
        bc = site_cfg.get("browser", {})
        ud = bc.get("user_data_dir", "")
        ud_path = Path(ud) if ud else None
        if ud_path and not ud_path.is_absolute():
            ud_path = Path(__file__).parent / ud_path
        options.set_browser_options(
            headless=bc.get("headless", False),
            user_data_dir=str(ud_path) if ud_path else None,
            timeout=bc.get("timeout", 30),
            retry_times=bc.get("retry_times", 3),
            backoff_factor=bc.get("backoff_factor", 2),
            delay=tuple(bc.get("delay", [3, 5])),
            viewport=bc.get("viewport"),
        )
    elif mode == "api":
        api_s = site_cfg.get("api", {})
        for name, p in api_s.items():
            if isinstance(p, dict) and p.get("enabled", True):
                options.set_api_options(
                    name=name, key=p.get("key", ""),
                    timeout=p.get("timeout", 30), retry_times=p.get("retry_times", 3),
                    batch_size=p.get("batch_size", 3), backoff_factor=p.get("backoff_factor", 2),
                    delay=tuple(p.get("delay", [3, 5])), params=p.get("params", {}),
                )
                break
    elif mode == "requests":
        rc = site_cfg.get("requests", {})
        cookies_val = rc.get("cookies")
        if isinstance(cookies_val, str) and cookies_val:
            d = {}
            for item in cookies_val.split(";"):
                item = item.strip()
                if "=" in item:
                    k, v = item.split("=", 1)
                    d[k.strip()] = v.strip()
            cookies_val = d
        elif not isinstance(cookies_val, dict):
            cookies_val = None
        options.set_requests_options(
            headers=rc.get("headers"), cookies=cookies_val,
            proxies=rc.get("proxies"), timeout=rc.get("timeout", 30),
            retry_times=rc.get("retry_times", 3), backoff_factor=rc.get("backoff_factor", 2),
            delay=tuple(rc.get("delay", [3, 5])),
        )
    return options


# ═══════════════════════════════════════════════════════════════════
# 全局状态
# ═══════════════════════════════════════════════════════════════════

cfg, site_cfg, format_configs = load_configs()
group = cfg.get("group", "default")
mode = cfg.get("mode", "browser")
options = build_options(cfg, site_cfg)
engine = create_engine(options)
dl = NovelDownloader(engine, options=options)
storage = Storage(APP_DATA / "storage")

# 任务进度追踪: {task_id: {"status": "running"|"done"|"error", "message": str, "result": any}}
_task_progress: dict[str, dict] = {}
_task_lock = threading.Lock()

# ═══════════════════════════════════════════════════════════════════
# FastAPI 应用
# ═══════════════════════════════════════════════════════════════════

app = FastAPI(title="novel-downloader")

# ═══════════════════════════════════════════════════════════════════
# SSE 进度推送
# ═══════════════════════════════════════════════════════════════════

async def sse_progress(task_id: str):
    """SSE 端点，推送任务进度。"""
    async def generate():
        last_idx = 0
        while True:
            with _task_lock:
                msgs = _task_progress.get(task_id, [])
                new_msgs = msgs[last_idx:]
                last_idx = len(msgs)
            for msg in new_msgs:
                yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
            # 检查是否结束
            with _task_lock:
                status = _task_progress.get(f"{task_id}_status", "running")
            if status in ("done", "error"):
                yield f"data: {json.dumps({'type': 'end', 'status': status}, ensure_ascii=False)}\n\n"
                break
            await asyncio.sleep(0.3)
    return StreamingResponse(generate(), media_type="text/event-stream")


def _emit(task_id: str, msg_type: str, text: str, **extra):
    """向任务追加一条进度消息。"""
    with _task_lock:
        if task_id not in _task_progress:
            _task_progress[task_id] = []
        _task_progress[task_id].append({"type": msg_type, "text": text, **extra})


def _finish(task_id: str, status: str):
    with _task_lock:
        _task_progress[f"{task_id}_status"] = status


# ═══════════════════════════════════════════════════════════════════
# 导出逻辑（与 main.py 一致）
# ═══════════════════════════════════════════════════════════════════

def _do_export(novel, grp: str, fmts: dict, task_id: str | None = None):
    registered = get_exporters()
    opt_map = get_exporter_options()
    for fmt, fc in fmts.items():
        if not fc.get("enabled", True):
            continue
        ec = registered.get(fmt)
        oc = opt_map.get(fmt)
        if ec is None or oc is None:
            continue
        raw = fc.get("output_path", "").replace("{group}", grp)
        extra = {}
        for k in ("encoding", "file_name_template", "extension", "css_style", "include_toc"):
            if k in fc:
                extra[k] = fc[k]
        export_opts = oc(output_path=raw, **extra)
        exporter = ec(options=export_opts, novel=novel)
        exporter.export(novel.chapters)
        if task_id:
            _emit(task_id, "log", f"  已导出: {fmt}")


# ═══════════════════════════════════════════════════════════════════
# 核心下载流程
# ═══════════════════════════════════════════════════════════════════

def _download_novel(url: str, task_id: str):
    """在后台线程中执行完整下载流程。"""
    _emit(task_id, "log", f"开始下载: {url}")
    try:
        # 1. 获取信息
        _emit(task_id, "log", "正在获取小说信息...")
        novel = dl.fetch_novel(url)
        _emit(task_id, "novel_info", novel.title, author=novel.author,
               tags="、".join(novel.tags) if novel.tags else "",
               count=novel.count or "未知")
        storage.save_meta(novel)

        # 2. 章节列表
        _emit(task_id, "log", "正在获取章节列表...")
        chapters = dl.fetch_chapter_list(novel)
        _emit(task_id, "log", f"  共 {len(chapters)} 章")
        novel.update_chapter(chapters)

        # 3. 合并本地
        local = storage.load_chapters(novel.id)
        if local:
            novel.update_chapter(local)

        # 4. 下载
        incomplete = novel.chapters.get_incompleted_chapters()
        target = list(incomplete) if incomplete else []
        if not target:
            _emit(task_id, "log", "所有章节已下载完毕！")
        else:
            _emit(task_id, "log", f"待下载: {len(target)} 章，正在下载...")
            dl._progress = type(dl._progress)("")
            try:
                downloaded = dl.download_chapters(target)
                _emit(task_id, "log", f"  下载完成: {len(downloaded)} 章")
            except AntiCrawlError:
                _emit(task_id, "error", "触发反爬，保存已下载部分...")
                if dl.partial:
                    storage.save_chapter(novel, dl.partial)
                    storage.save_progress(dl.progress, novel.id)
                    novel.update_chapter(dl.partial)
                _finish(task_id, "error")
                return
            else:
                storage.save_chapter(novel, downloaded)
                storage.save_progress(dl.progress, novel.id)
                novel.update_chapter(downloaded)

        # 5. 导出
        _emit(task_id, "log", "正在导出...")
        _do_export(novel, group, format_configs, task_id)
        _emit(task_id, "done", f"导出完成 → app_data/export/{group}/")
        _finish(task_id, "done")

    except Exception as e:
        _emit(task_id, "error", str(e))
        _finish(task_id, "error")


# ═══════════════════════════════════════════════════════════════════
# 获取已存储小说列表
# ═══════════════════════════════════════════════════════════════════

def get_stored_novels() -> list[dict]:
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
        # 只统计章节文件数，不加载内容（避免启动时大量 IO）
        chapters_dir = d / "chapters"
        downloaded = 0
        if chapters_dir.is_dir():
            downloaded = sum(1 for _ in chapters_dir.glob("*.json"))
        result.append({
            "id": meta.id, "title": meta.title, "author": meta.author,
            "url": meta.url, "serial": meta.serial,
            "downloaded": downloaded, "tags": list(meta.tags or []),
        })
    return result


# ═══════════════════════════════════════════════════════════════════
# HTML 模板
# ═══════════════════════════════════════════════════════════════════

PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>novel-downloader</title>
<style>
:root { --bg: #111; --card: #1a1a1a; --text: #ddd; --muted: #888;
        --accent: #4af; --danger: #f55; --success: #5f5; --border: #333; }
* { box-sizing:border-box; margin:0; padding:0; }
body { background:var(--bg); color:var(--text); font:14px/1.6 system-ui,sans-serif;
       max-width:900px; margin:0 auto; padding:20px; }
h2 { font-size:1.2em; margin:20px 0 10px; color:var(--accent); }
.card { background:var(--card); border:1px solid var(--border); border-radius:8px;
        padding:16px; margin-bottom:16px; }
.row { display:flex; gap:10px; flex-wrap:wrap; align-items:center; }
input, button, select { background:#222; color:var(--text); border:1px solid var(--border);
    border-radius:6px; padding:8px 14px; font:inherit; }
input { flex:1; min-width:200px; }
button { cursor:pointer; background:var(--accent); color:#000; border:none; font-weight:600; }
button.danger { background:var(--danger); }
button.success { background:var(--success); color:#000; }
button:disabled { opacity:0.4; cursor:default; }
.novel-list { list-style:none; }
.novel-list li { padding:12px; border-bottom:1px solid var(--border);
    display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; }
.novel-list li:last-child { border-bottom:none; }
.tag { display:inline-block; background:#333; color:var(--muted); padding:2px 8px;
       border-radius:4px; font-size:12px; margin-right:4px; }
#log { background:#000; border:1px solid var(--border); border-radius:8px;
       padding:12px; height:300px; overflow-y:auto; font:13px monospace; white-space:pre-wrap; }
#log .info { color:var(--muted); }
#log .error { color:var(--danger); }
#log .done { color:var(--success); }
.spinner { display:inline-block; width:14px; height:14px; border:2px solid var(--muted);
    border-top-color:var(--accent); border-radius:50%; animation:spin .6s linear infinite; }
@keyframes spin { to { transform:rotate(360deg); } }
.status { font-size:13px; color:var(--muted); }
</style>
</head>
<body>

<h1>📚 novel-downloader</h1>
<p class="status">模式: {{mode}} | 分组: {{group}} | 已存储: {{novel_count}} 本 | <a href="/settings">⚙️ 设置</a></p>

<!-- 搜索 & 下载 -->
<div class="card">
  <h2>🔍 搜索 & 下载</h2>
  <div class="row">
    <input id="search-input" placeholder="输入关键词搜索小说...">
    <button onclick="doSearch()">搜索</button>
  </div>
  <div id="search-results" style="margin-top:10px;"></div>
</div>

<!-- 直接下载 -->
<div class="card">
  <h2>📥 直接下载</h2>
  <div class="row">
    <input id="url-input" placeholder="粘贴小说链接 https://fanqienovel.com/page/...">
    <button onclick="doDownload()">下载</button>
  </div>
</div>

<!-- 已存储小说 -->
<div class="card">
  <h2>📦 已存储小说</h2>
  <ul class="novel-list" id="novel-list">
    {% for n in novels %}
    <li>
      <div>
        <strong>{{n.title}}</strong>
        <span class="status"> — {{n.author}}</span>
        <div>
          {% for t in (n.tags or [])[:3] %}<span class="tag">{{t}}</span>{% endfor %}
          <span class="status">已下载 {{n.downloaded}}/{{n.serial or "?"}} 章</span>
        </div>
      </div>
      <div class="row">
        <button class="success" onclick="doAction('update','{{n.id}}')">更新</button>
        <button onclick="doAction('export','{{n.id}}')">导出</button>
      </div>
    </li>
    {% endfor %}
    {% if not novels %}
    <li class="status">暂无已下载的小说</li>
    {% endif %}
  </ul>
  <div class="row" style="margin-top:12px;">
    <button onclick="doAction('update_all')">🔄 全部更新</button>
    <button onclick="doAction('export_all')">📦 全部导出</button>
  </div>
</div>

<!-- 登录 -->
<div class="card">
  <h2>🔑 登录</h2>
  <button onclick="doLogin()">打开浏览器登录</button>
  <span class="status">（需要在运行服务器的机器上有桌面环境）</span>
</div>

<!-- 日志 -->
<div class="card">
  <h2>📋 运行日志</h2>
  <div id="log"><span class="info">就绪，等待操作...</span></div>
</div>

<script>
const LOG = document.getElementById('log');
function log(msg, cls='info') {
  LOG.innerHTML += `<div class="${cls}">${msg}</div>`;
  LOG.scrollTop = LOG.scrollHeight;
}
function clearLog() { LOG.innerHTML = ''; }

async function doSearch() {
  const q = document.getElementById('search-input').value.trim();
  if (!q) return;
  clearLog(); log('搜索中: ' + q);
  try {
    const r = await fetch('/search?q=' + encodeURIComponent(q));
    const data = await r.json();
    const div = document.getElementById('search-results');
    if (!data.results || !data.results.length) {
      div.innerHTML = '<p class="status">未找到结果</p>';
      log('未找到任何结果');
      return;
    }
    log(`搜索到 ${data.results.length} 个结果`);
    div.innerHTML = data.results.map((n, i) => `
      <div class="row" style="margin:6px 0; padding:8px; background:#222; border-radius:6px;">
        <span style="flex:1"><strong>${n.title}</strong> — ${n.author}</span>
        <button onclick="startDownload('${n.url}')">下载</button>
      </div>`).join('');
  } catch(e) { log('搜索失败: ' + e, 'error'); }
}

function doDownload() {
  const url = document.getElementById('url-input').value.trim();
  if (!url) return;
  startDownload(url);
}

function doAction(action, novelId) {
  if (action === 'update') {
    clearLog(); log('开始更新...');
    const taskId = crypto.randomUUID();
    streamProgress(taskId);
    fetch('/update/' + novelId + '?task_id=' + taskId, {method:'POST'}).catch(e => log('请求失败', 'error'));
  } else if (action === 'export') {
    clearLog(); log('开始导出...');
    const taskId = crypto.randomUUID();
    streamProgress(taskId);
    fetch('/re_export/' + novelId + '?task_id=' + taskId, {method:'POST'}).catch(e => log('请求失败', 'error'));
  } else if (action === 'update_all') {
    clearLog(); log('全部更新中...');
    const taskId = crypto.randomUUID();
    streamProgress(taskId);
    fetch('/update_all?task_id=' + taskId, {method:'POST'}).catch(e => log('请求失败', 'error'));
  } else if (action === 'export_all') {
    clearLog(); log('全部导出中...');
    const taskId = crypto.randomUUID();
    streamProgress(taskId);
    fetch('/export_all?task_id=' + taskId, {method:'POST'}).catch(e => log('请求失败', 'error'));
  }
}

function startDownload(url) {
  clearLog(); log('开始下载: ' + url);
  const taskId = crypto.randomUUID();
  streamProgress(taskId);
  fetch('/download?task_id=' + taskId, {method:'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: 'url=' + encodeURIComponent(url)
  }).catch(e => log('请求失败', 'error'));
}

function doLogin() {
  clearLog(); log('正在打开浏览器...（请在浏览器中完成登录）');
  const taskId = crypto.randomUUID();
  streamProgress(taskId);
  fetch('/login?task_id=' + taskId, {method:'POST'}).catch(e => log('请求失败', 'error'));
}

function streamProgress(taskId) {
  const es = new EventSource('/progress/' + taskId);
  es.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.type === 'end') {
      es.close();
      if (msg.status === 'done') { log('✓ 完成', 'done'); setTimeout(() => location.reload(), 1000); }
      else { log('✗ 任务异常结束', 'error'); }
      return;
    }
    const cls = msg.type === 'error' ? 'error' : msg.type === 'done' ? 'done' : 'info';
    log(msg.text, cls);
  };
  es.onerror = () => { es.close(); };
}
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════
# 路由
# ═══════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index():
    novels = get_stored_novels()
    html = PAGE_HTML.replace("{{mode}}", mode).replace("{{group}}", group)
    html = html.replace("{{novel_count}}", str(len(novels)))
    # 内联替换 novels 列表
    if novels:
        items = []
        for n in novels:
            tags_html = "".join(f'<span class="tag">{t}</span>' for t in (n["tags"] or [])[:3])
            items.append(f'''<li>
      <div>
        <strong>{n["title"]}</strong>
        <span class="status"> — {n["author"]}</span>
        <div>{tags_html}<span class="status">已下载 {n["downloaded"]}/{n["serial"] or "?"} 章</span></div>
      </div>
      <div class="row">
        <button class="success" onclick="doAction('update','{n["id"]}')">更新</button>
        <button onclick="doAction('export','{n["id"]}')">导出</button>
      </div>
    </li>''')
        html = html.replace(
            "{% for n in novels %}{% endfor %}",
            "".join(items)
        )
        html = html.replace("{% if not novels %}", "").replace("{% endif %}", "")
    else:
        html = html.replace(
            "{% for n in novels %}{% endfor %}",
            '<li class="status">暂无已下载的小说</li>'
        )
        html = html.replace(
            "{% if not novels %}<li class=\"status\">暂无已下载的小说</li>{% endif %}",
            ""
        )
    return HTMLResponse(html)


@app.get("/api/novels")
async def api_novels():
    return JSONResponse(get_stored_novels())


@app.get("/api/config")
async def api_config():
    return JSONResponse({"mode": mode, "group": group})


@app.get("/settings", response_class=HTMLResponse)
async def settings_page():
    cfg = yaml.safe_load((CONFIG_DIR / "config.yaml").read_text(encoding="utf-8"))
    site = yaml.safe_load((CONFIG_DIR / "sites" / "fanqie.yaml").read_text(encoding="utf-8"))
    # 构建 settings HTML
    mode_val = cfg.get("mode", "browser")
    group_val = cfg.get("group", "default")
    workers_val = cfg.get("download", {}).get("max_workers", 3)

    bc = site.get("browser", {})
    ac = site.get("api", {}).get("oiapi", {})
    rc = site.get("requests", {})

    api_key = ac.get("key", "")
    api_key_masked = api_key[:4] + "****" + api_key[-4:] if len(api_key) > 8 else (api_key[:2] + "****" if api_key else "")

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>设置 — novel-downloader</title>
<style>
:root {{ --bg:#111; --card:#1a1a1a; --text:#ddd; --muted:#888; --accent:#4af; --danger:#e55; --success:#4a4; --border:#333; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font:15px/1.5 system-ui,sans-serif; background:var(--bg); color:var(--text); max-width:800px; margin:0 auto; padding:20px; }}
h1 {{ margin-bottom:4px; }}
h2 {{ margin-bottom:10px; font-size:17px; }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:8px; padding:20px; margin-bottom:16px; }}
.row {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
label {{ font-size:13px; color:var(--muted); display:block; margin-bottom:3px; }}
input, select, textarea {{ background:#222; color:var(--text); border:1px solid var(--border); border-radius:6px; padding:8px 12px; font:inherit; width:100%; }}
.form-group {{ margin-bottom:14px; }}
.form-group.inline {{ display:flex; gap:10px; align-items:center; }}
.form-group.inline label {{ margin-bottom:0; min-width:80px; }}
button {{ cursor:pointer; background:var(--accent); color:#000; border:none; border-radius:6px; padding:8px 20px; font:inherit; font-weight:600; }}
button.success {{ background:var(--success); }}
.status {{ font-size:13px; color:var(--muted); margin:8px 0; }}
a {{ color:var(--accent); text-decoration:none; }}
hr {{ border:none; border-top:1px solid var(--border); margin:16px 0; }}
</style>
</head>
<body>
<h1>⚙️ 设置</h1>
<p class="status"><a href="/">← 返回主页</a></p>

<form class="card" method="POST" action="/settings/save">
<h2>📋 主配置</h2>
<div class="row">
  <div class="form-group" style="flex:1; min-width:120px;">
    <label>模式</label>
    <select name="mode">
      <option value="browser" {"selected" if mode_val=="browser" else ""}>browser</option>
      <option value="api" {"selected" if mode_val=="api" else ""}>api</option>
      <option value="requests" {"selected" if mode_val=="requests" else ""}>requests</option>
    </select>
  </div>
  <div class="form-group" style="flex:1; min-width:120px;">
    <label>分组</label>
    <input name="group" value="{group_val}">
  </div>
  <div class="form-group" style="flex:1; min-width:120px;">
    <label>并发数</label>
    <input name="max_workers" type="number" value="{workers_val}" min="1" max="10">
  </div>
</div>
<button type="submit" class="success">保存主配置</button>
</form>

<form class="card" method="POST" action="/settings/site/save">
<h2>🌐 站点配置 (fanqie)</h2>

<h3 style="font-size:14px; margin:12px 0 8px;">Browser 模式</h3>
<div class="row">
  <div class="form-group" style="flex:1;">
    <label>headless</label>
    <select name="browser_headless">
      <option value="false" {"" if bc.get("headless") else "selected"}>否</option>
      <option value="true" {"selected" if bc.get("headless") else ""}>是</option>
    </select>
  </div>
  <div class="form-group" style="flex:2;">
    <label>user_data_dir</label>
    <input name="browser_user_data_dir" value="{bc.get('user_data_dir','')}">
  </div>
</div>
<div class="row">
  <div class="form-group" style="flex:1;">
    <label>timeout (秒)</label>
    <input name="browser_timeout" type="number" value="{bc.get('timeout',30)}">
  </div>
  <div class="form-group" style="flex:1;">
    <label>retry_times</label>
    <input name="browser_retry_times" type="number" value="{bc.get('retry_times',3)}">
  </div>
  <div class="form-group" style="flex:1;">
    <label>delay (下限,上限)</label>
    <input name="browser_delay" value="{bc.get('delay',[3,5])[0]},{bc.get('delay',[3,5])[1]}">
  </div>
</div>

<hr>
<h3 style="font-size:14px; margin:12px 0 8px;">API 模式 (oiapi)</h3>
<div class="form-group">
  <label>API Key</label>
  <div class="row">
    <input id="api-key-field" name="api_key" type="password" value="{api_key}" placeholder="输入 API Key" style="flex:1;">
    <button type="button" onclick="toggleKey()" style="background:#444;color:#ddd;padding:8px 12px;">👁</button>
  </div>
  <div class="status" id="key-hint">当前: {api_key_masked}</div>
</div>
<div class="row">
  <div class="form-group" style="flex:1;">
    <label>timeout (秒)</label>
    <input name="api_timeout" type="number" value="{ac.get('timeout',30)}">
  </div>
  <div class="form-group" style="flex:1;">
    <label>batch_size</label>
    <input name="api_batch_size" type="number" value="{ac.get('batch_size',3)}">
  </div>
  <div class="form-group" style="flex:1;">
    <label>retry_times</label>
    <input name="api_retry_times" type="number" value="{ac.get('retry_times',3)}">
  </div>
</div>

<hr>
<h3 style="font-size:14px; margin:12px 0 8px;">Requests 模式</h3>
<div class="form-group">
  <label>User-Agent</label>
  <input name="req_ua" value="{rc.get('headers',{}).get('User-Agent','')}">
</div>
<div class="form-group">
  <label>Cookies (dict 格式，可留空用浏览器登录自动填充)</label>
  <textarea name="req_cookies" rows="3" placeholder='{{"k1":"v1","k2":"v2"}}'>{json.dumps(rc.get('cookies',{}), ensure_ascii=False) if isinstance(rc.get('cookies'), dict) else rc.get('cookies','')}</textarea>
</div>
<div class="row">
  <div class="form-group" style="flex:1;">
    <label>timeout (秒)</label>
    <input name="req_timeout" type="number" value="{rc.get('timeout',30)}">
  </div>
  <div class="form-group" style="flex:1;">
    <label>retry_times</label>
    <input name="req_retry_times" type="number" value="{rc.get('retry_times',3)}">
  </div>
</div>

<button type="submit" class="success">保存站点配置</button>
</form>

<script>
function toggleKey() {{
  const f = document.getElementById('api-key-field');
  f.type = f.type === 'password' ? 'text' : 'password';
}}
</script>
</body>
</html>""")


@app.post("/settings/save")
async def save_main_config(request: Request):
    body = await request.body()
    data = dict(p.split("=", 1) for p in body.decode().split("&") if "=" in p)
    from urllib.parse import unquote_plus
    cfg_path = CONFIG_DIR / "config.yaml"
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    cfg["mode"] = data.get("mode", cfg.get("mode", "browser"))
    cfg["group"] = data.get("group", cfg.get("group", "default"))
    mw = data.get("max_workers", "3")
    try:
        mw = int(mw)
    except ValueError:
        mw = 3
    if "download" not in cfg:
        cfg["download"] = {}
    cfg["download"]["max_workers"] = mw
    cfg_path.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")

    global mode, group, options, engine, dl
    mode = cfg["mode"]
    group = cfg["group"]
    site_cfg = yaml.safe_load((CONFIG_DIR / "sites" / "fanqie.yaml").read_text(encoding="utf-8"))
    options = build_options(cfg, site_cfg)
    if engine:
        engine.close()
    engine = create_engine(options)
    dl = NovelDownloader(engine, options=options)
    return HTMLResponse('<p style="color:var(--success)">✓ 已保存，<a href="/settings">返回</a></p>')


@app.post("/settings/site/save")
async def save_site_config(request: Request):
    body = await request.body()
    from urllib.parse import unquote_plus
    data = {}
    for p in body.decode().split("&"):
        if "=" in p:
            k, v = p.split("=", 1)
            data[k] = unquote_plus(v)

    site_path = CONFIG_DIR / "sites" / "fanqie.yaml"
    site = yaml.safe_load(site_path.read_text(encoding="utf-8")) if site_path.exists() else {}

    # Browser
    if "browser" not in site:
        site["browser"] = {}
    site["browser"]["headless"] = data.get("browser_headless", "false") == "true"
    site["browser"]["user_data_dir"] = data.get("browser_user_data_dir", "")
    try: site["browser"]["timeout"] = int(data.get("browser_timeout", "30"))
    except ValueError: pass
    try: site["browser"]["retry_times"] = int(data.get("browser_retry_times", "3"))
    except ValueError: pass
    delay = data.get("browser_delay", "3,5")
    try:
        parts = [float(x.strip()) for x in delay.split(",")]
        site["browser"]["delay"] = [parts[0], parts[1]]
    except (ValueError, IndexError):
        pass
    # API
    if "api" not in site:
        site["api"] = {}
    if "oiapi" not in site["api"]:
        site["api"]["oiapi"] = {}
    ak = data.get("api_key", "")
    if ak:
        site["api"]["oiapi"]["key"] = ak
    try: site["api"]["oiapi"]["timeout"] = int(data.get("api_timeout", "30"))
    except ValueError: pass
    try: site["api"]["oiapi"]["batch_size"] = int(data.get("api_batch_size", "3"))
    except ValueError: pass
    try: site["api"]["oiapi"]["retry_times"] = int(data.get("api_retry_times", "3"))
    except ValueError: pass
    # Requests
    if "requests" not in site:
        site["requests"] = {}
    ua = data.get("req_ua", "")
    if ua:
        if "headers" not in site["requests"]:
            site["requests"]["headers"] = {}
        site["requests"]["headers"]["User-Agent"] = ua
    cookies_str = data.get("req_cookies", "")
    if cookies_str:
        try:
            site["requests"]["cookies"] = json.loads(cookies_str)
        except json.JSONDecodeError:
            pass
    try: site["requests"]["timeout"] = int(data.get("req_timeout", "30"))
    except ValueError: pass
    try: site["requests"]["retry_times"] = int(data.get("req_retry_times", "3"))
    except ValueError: pass

    site_path.write_text(yaml.safe_dump(site, allow_unicode=True), encoding="utf-8")
    return HTMLResponse('<p style="color:var(--success)">✓ 已保存站点配置，<a href="/settings">返回</a></p>')


@app.get("/search")
async def search_novels(q: str):
    try:
        results = search("fanqie", q, engine)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    if not results:
        return JSONResponse({"results": []})
    data = []
    for r in results:
        data.append({
            "title": getattr(r, "title", ""),
            "author": getattr(r, "author", ""),
            "url": getattr(r, "url", ""),
            "description": getattr(r, "description", ""),
        })
    return JSONResponse({"results": data})


@app.post("/download")
async def download_novel(request: Request, task_id: str = ""):
    body = await request.body()
    # parse url=... from form body
    url = ""
    for part in body.decode().split("&"):
        if part.startswith("url="):
            from urllib.parse import unquote_plus
            url = unquote_plus(part[4:])
            break
    if not url:
        return JSONResponse({"error": "missing url"}, status_code=400)
    if not task_id:
        task_id = str(uuid.uuid4())
    _emit(task_id, "log", "任务已创建")
    threading.Thread(target=_download_novel, args=(url, task_id), daemon=True).start()
    return JSONResponse({"task_id": task_id})


@app.post("/update/{novel_id}")
async def update_novel(novel_id: str, task_id: str = ""):
    if not task_id:
        task_id = str(uuid.uuid4())
    meta = storage.load_meta(novel_id)
    if meta is None:
        _emit(task_id, "error", "小说未找到")
        _finish(task_id, "error")
        return JSONResponse({"error": "not found"}, status_code=404)
    _emit(task_id, "log", f"更新: {meta.title}")
    threading.Thread(target=_download_novel, args=(meta.url, task_id), daemon=True).start()
    return JSONResponse({"task_id": task_id})


@app.post("/update_all")
async def update_all(task_id: str = ""):
    if not task_id:
        task_id = str(uuid.uuid4())
    novels = get_stored_novels()
    if not novels:
        _emit(task_id, "error", "无已存储小说")
        _finish(task_id, "error")
        return JSONResponse({"error": "no novels"}, status_code=404)

    def _run():
        for n in novels:
            _emit(task_id, "log", f"── 更新: {n['title']} ──")
            _download_novel(n["url"], task_id)
        _emit(task_id, "done", "全部更新完成")
        _finish(task_id, "done")

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"task_id": task_id})


@app.post("/re_export/{novel_id}")
async def re_export_novel(novel_id: str, task_id: str = ""):
    if not task_id:
        task_id = str(uuid.uuid4())
    meta = storage.load_meta(novel_id)
    if meta is None:
        _emit(task_id, "error", "小说未找到")
        _finish(task_id, "error")
        return JSONResponse({"error": "not found"}, status_code=404)
    _emit(task_id, "log", f"导出: {meta.title}")
    local = storage.load_chapters(novel_id)
    if local:
        meta.update_chapter(local)
    try:
        _do_export(meta, group, format_configs, task_id)
        _emit(task_id, "done", "导出完成")
        _finish(task_id, "done")
    except Exception as e:
        _emit(task_id, "error", str(e))
        _finish(task_id, "error")
    return JSONResponse({"task_id": task_id})


@app.post("/export_all")
async def export_all(task_id: str = ""):
    if not task_id:
        task_id = str(uuid.uuid4())
    novels = get_stored_novels()
    if not novels:
        _emit(task_id, "error", "无已存储小说")
        _finish(task_id, "error")
        return JSONResponse({"error": "no novels"}, status_code=404)

    def _run():
        for n in novels:
            meta = storage.load_meta(n["id"])
            if meta is None:
                continue
            local = storage.load_chapters(n["id"])
            if local:
                meta.update_chapter(local)
            _emit(task_id, "log", f"── 导出: {meta.title} ──")
            try:
                _do_export(meta, group, format_configs, task_id)
            except Exception as e:
                _emit(task_id, "error", str(e))
        _emit(task_id, "done", "全部导出完成")
        _finish(task_id, "done")

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"task_id": task_id})


@app.post("/login")
async def web_login(task_id: str = ""):
    if not task_id:
        task_id = str(uuid.uuid4())
    _emit(task_id, "log", "正在打开浏览器，请在浏览器中完成登录（最多等待 120 秒）...")

    def _run():
        browser_cfg = site_cfg.get("browser", {})
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
        try:
            cred = login("fanqie", login_engine)
            cookie_count = len(cred.cookies) if cred and cred.cookies else 0
            if cookie_count > 0:
                _emit(task_id, "log", f"登录成功，获取 {cookie_count} 个 cookies")
                site_path = CONFIG_DIR / "sites" / "fanqie.yaml"
                with open(site_path, encoding="utf-8") as f:
                    sy = yaml.safe_load(f) or {}
                if "requests" not in sy:
                    sy["requests"] = {}
                sy["requests"]["cookies"] = cred.cookies
                with open(site_path, "w", encoding="utf-8") as f:
                    yaml.safe_dump(sy, f, allow_unicode=True)
                _emit(task_id, "done", "Cookies 已保存到 fanqie.yaml")
            else:
                _emit(task_id, "error", "登录完成但未获取到 cookies")
        except Exception as e:
            _emit(task_id, "error", f"登录失败: {e}")
        finally:
            login_engine.close()
        _finish(task_id, "done")

    threading.Thread(target=_run, daemon=True).start()
    return JSONResponse({"task_id": task_id})


@app.get("/progress/{task_id}")
async def progress(task_id: str):
    return await sse_progress(task_id)


# ═══════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("service:app", host="127.0.0.1", port=8000, reload=True)
