"""Novel Downloader — FastAPI 后端入口。"""
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# dev mode: ensure project root is on path
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from services.backend.routers import storage, download, export, engine, config
from services.backend.services.engine_manager import clear_engine_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup — 检查并初始化配置
    from init_config import check_config, init_all_config
    result = check_config()
    if result["missing"]:
        if result["all_missing"]:
            print("首次运行，正在从默认模板初始化配置...")
        init_all_config()
        print(f"已初始化 {len(result['missing'])} 个配置文件")
    yield
    # shutdown — 清理所有缓存引擎
    clear_engine_cache()


app = FastAPI(title="Novel Downloader API", version="2.0.0", docs_url="/docs", lifespan=lifespan)

# ── v2 response wrapper — { ok, message, data } ──
class V2ResponseMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        # Only wrap /api/v2 and /config responses that are JSON
        if not request.url.path.startswith("/api/v2"):
            return response
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response
        # Read and wrap the original body
        try:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk
            import json as _json
            original = _json.loads(body) if body else None
        except Exception:
            return response
        if response.status_code >= 400:
            detail = original.get("detail", "服务器错误") if isinstance(original, dict) else "服务器错误"
            return JSONResponse(
                status_code=response.status_code,
                content={"ok": False, "message": str(detail), "data": None},
            )
        # Wrap success (skip if already wrapped)
        if isinstance(original, dict) and "ok" in original:
            return JSONResponse(status_code=response.status_code, content=original)
        return JSONResponse(
            status_code=response.status_code,
            content={"ok": True, "message": "success", "data": original},
        )

app.add_middleware(V2ResponseMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(storage.router)
app.include_router(download.router)
app.include_router(export.router)
app.include_router(engine.router)
app.include_router(config.router)

@app.get("/api/v2/health")
async def health():
    return {"ok": True, "message": "success", "data": {"status": "ok"}}

# ── 前端静态文件 ──
def _find_frontend_dist() -> Path | None:
    """定位前端构建产物目录。"""
    candidates = []
    # Nuitka：不设 sys.frozen/_MEIPASS；onefile 数据文件解压到 __file__ 所在目录（对齐 init_config._get_root，sys.executable 指向 bootstrap exe 不可用）
    if "__compiled__" in globals():
        candidates.append(Path(__file__).resolve().parent / "services" / "frontend" / "dist")
    # PyInstaller
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys._MEIPASS) / "services" / "frontend" / "dist")
    candidates.extend([
        _project_root / "services" / "frontend" / "dist",
        Path.cwd() / "services" / "frontend" / "dist",
    ])
    for p in candidates:
        if (p / "index.html").exists():
            return p
    return None

_frontend = _find_frontend_dist()
if _frontend:
    app.mount("/assets", StaticFiles(directory=str(_frontend / "assets")), name="assets")


@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """SPA fallback：非 API 路由返回 index.html；前端未构建时返回提示页。"""
    if _frontend is not None:
        path = _frontend / (full_path or "index.html")
        if path.is_file():
            return FileResponse(str(path))
        return FileResponse(str(_frontend / "index.html"))
    # 前端未构建：返回 HTML 提示
    if full_path and full_path != "index.html":
        return JSONResponse({"ok": False, "message": "前端未构建，仅 API 可用"}, status_code=404)
    return HTMLResponse("""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>novel-downloader</title>
<style>body{font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f8fafc;color:#334155}main{text-align:center;max-width:420px;padding:2rem}h1{font-size:1.5rem;margin-bottom:.5rem}p{color:#64748b;line-height:1.6}code{background:#e2e8f0;padding:.15em .4em;border-radius:4px;font-size:.9em}</style>
</head><body><main>
<h1>📖 novel-downloader</h1>
<p>API 服务已启动（<code>localhost:8000</code>）</p>
<p>前端尚未构建。运行以下命令后刷新页面：</p>
<code>cd services/frontend &amp;&amp; npm run build</code>
<p style="margin-top:1.5rem;font-size:.85rem">仅 API 模式：<a href="/docs">/docs</a> · <a href="/api/v2/health">/api/v2/health</a></p>
</main></body></html>""")

def main():
    """启动 Web 后端服务。"""
    import uvicorn, webbrowser, threading
    # 打包版（exe）判断：__compiled__ 或 sys.frozen
    compiled = "__compiled__" in globals() or getattr(sys, "frozen", False)

    # 1 秒后自动打开浏览器
    def _open_browser():
        import time
        time.sleep(1)
        webbrowser.open("http://localhost:8000")

    threading.Thread(target=_open_browser, daemon=True).start()

    if compiled:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        uvicorn.run("services.backend.main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    main()
