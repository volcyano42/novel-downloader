"""novel-downloader Web UI — FastAPI 应用入口。"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ── FastAPI 应用 ────────────────────────────────────────────────
app = FastAPI(title="novel-downloader")

# 挂载静态文件
_static_dir = Path(__file__).resolve().parent / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Jinja2 模板
_templates_dir = Path(__file__).resolve().parent / "templates"
jinja_templates = Jinja2Templates(directory=str(_templates_dir))


def render(name: str, **context):
    """渲染模板的快捷方式。"""
    request = context.get("request")
    return jinja_templates.TemplateResponse(request, name, context)


# ── 注册路由（延迟导入避免循环） ──────────────────────────────
from .routes import pages, api

app.include_router(pages.router)
app.include_router(api.router)

