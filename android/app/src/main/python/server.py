# -*- coding: utf-8 -*-
"""Android APK 版后端入口：注入 NLD_APP_DATA → 启动现有 FastAPI app → 挂载前端。

健康检查不在此处自注册 /health：MainActivity 轮询 services/backend/main.py 中
注册于 SPA fallback 与根 mount 之前的 /api/v2/health（两种环境始终可达）；
本模块注册的 /health 会被 SPA fallback（本地 services/frontend/dist 存在时）
或根 StaticFiles mount 拦截，实际不可达。

启动条件：仅当以 __main__ 运行（本地 python server.py，或 Chaquopy
Python.start(..., "server") 使入口模块以 __main__ 方式执行）时阻塞启动 uvicorn。
模块被 import（如 pytest）时不启动；不依赖 _ANDROID 判定（_ANDROID 仅用于
get_app_data 的 Android 存储兜底）。
"""
import os
from pathlib import Path

import uvicorn

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


# 优先 Chaquopy 打包目录内的 frontend/（build-apk.sh 复制进 src/main/python/frontend）；
# 回退旧 assets/frontend（本地直接运行/现有 test_android_server.py 的兼容路径）
_frontend_dir = Path(__file__).resolve().parent / "frontend"
if not _frontend_dir.is_dir():
    _frontend_dir = Path(__file__).resolve().parent.parent / "assets" / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")


# ── 启动 / 关闭 ────────────────────────────────────────────────
_server: "uvicorn.Server | None" = None


def _start() -> None:
    """阻塞启动 uvicorn（Chaquopy Python.start 调用入口）；幂等：已在运行则直接返回。"""
    global _server
    if _server is not None:
        return
    config = uvicorn.Config(app, host="127.0.0.1", port=18080, log_level="info")
    _server = uvicorn.Server(config)
    try:
        _server.run()
    finally:
        _server = None  # 无论正常退出还是异常，都允许再次启动


def _shutdown() -> None:
    """Service onDestroy 调用：优雅停止 uvicorn。"""
    if _server is not None:
        _server.should_exit = True


if __name__ == "__main__":
    _start()
