# -*- coding: utf-8 -*-
"""Android APK 版后端入口：注入 NLD_APP_DATA → 启动现有 FastAPI app → 挂载前端。"""
import os
from pathlib import Path

try:
    from android.os import Environment  # Chaquopy Android 环境
    _ANDROID = True
except ImportError:
    _ANDROID = False


def get_app_data() -> Path:
    """返回 app_data 目录：优先 NLD_APP_DATA env；Android 上默认公共 Documents。"""
    env = os.environ.get("NLD_APP_DATA")
    if env:
        return Path(env).resolve()
    if _ANDROID:
        docs = Path(str(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOCUMENTS)))
        return docs / "novel-downloader" / "app_data"
    # 本地测试兜底
    return Path(__file__).resolve().parent.parent / "app_data"


def ensure_app_data_writable() -> None:
    """确保 app_data 可写；不可写抛 RuntimeError（调用方转 503）。"""
    app_data = get_app_data()
    try:
        app_data.mkdir(parents=True, exist_ok=True)
        probe = app_data / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as e:
        raise RuntimeError(f"app_data 不可写：{app_data}（请授予存储权限）") from e


APP_DATA = get_app_data()
os.environ["NLD_APP_DATA"] = str(APP_DATA)  # config_service.py 优先读此 env
ensure_app_data_writable()

from services.backend.main import app  # noqa: E402  （现有 FastAPI app）

from fastapi.staticfiles import StaticFiles  # noqa: E402

_frontend_dir = Path(__file__).resolve().parent.parent / "assets" / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")


@app.get("/health")
async def health() -> dict:
    """MainActivity 轮询的就绪探针。"""
    return {"status": "ok"}
