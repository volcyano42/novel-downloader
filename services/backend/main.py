"""Novel Downloader — FastAPI 后端入口。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from services.backend.routers import storage, download, export, engine, config

app = FastAPI(title="Novel Downloader API", version="2.0.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

app.include_router(storage.router)
app.include_router(download.router)
app.include_router(export.router)
app.include_router(engine.router)
app.include_router(config.router)

@app.get("/api/v2/health")
async def health():
    return {"ok": True, "message": "success", "data": {"status": "ok"}}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("services.backend.main:app", host="0.0.0.0", port=8000, reload=True)
