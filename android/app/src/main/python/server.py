# -*- coding: utf-8 -*-
"""Android APK 版后端入口：注入 NLD_APP_DATA / NLD_PLATFORM → 解压前端资源 → 启动现有 FastAPI app。

前端交付：构建期把 `frontend/dist` 打成 `frontend.zip` 随 APK 资产分发（见
`android/scripts/build-apk.sh`）；本模块启动时把该 zip 解压到 App 私有可写目录并设置
`NLD_FRONTEND_DIR`，交给 `backend/main.py` 的 SPA fallback 统一服务——本模块**不再自行挂载**
前端（曾有的根挂载注册在 SPA fallback 之后，永不命中，是死代码）。
原因：Chaquopy 把 `src/main/python/` 打成 APK 资产，其中的数据文件不是真实目录
（`os.listdir`/`os.scandir` 不可用），`StaticFiles` 的「真实目录」假设不成立。

健康检查不在此处自注册 /health：MainActivity 轮询 backend/main.py 中注册于
SPA fallback 之前的 /api/v2/health（两种环境始终可达）。

启动条件：仅当以 __main__ 运行（本地 python server.py，或 Chaquopy
Python.start(..., "server") 使入口模块以 __main__ 方式执行）时阻塞启动 uvicorn。
模块被 import（如 pytest）时不启动；不依赖 _ANDROID 判定（_ANDROID 仅用于
get_app_data 的 Android 存储兜底）。
"""
import hashlib
import os
import shutil
import zipfile
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


def _extract_frontend() -> None:
    """把随 APK 资产分发的 frontend.zip 解压到可写目录，并设置 NLD_FRONTEND_DIR。

    必须在 `from backend.main import app` **之前**调用——后端在模块级定位前端。
    幂等（`.zip-sha256` 标记命中则跳过解压）；zip-slip 防护（越界成员跳过）。
    任何失败都只打日志、不抛异常、不设 NLD_FRONTEND_DIR：前端回落占位页，
    保持可诊断（不静默）。
    """
    # 外部显式指定且有效 → 直接采用，不解压、不覆盖（本机联调 / 自定义布局）
    explicit = os.environ.get("NLD_FRONTEND_DIR")
    if explicit and (Path(explicit) / "index.html").is_file():
        print(f"[server] 使用已指定的 NLD_FRONTEND_DIR：{explicit}")
        return

    zip_path = Path(__file__).resolve().parent / "frontend.zip"
    if not zip_path.is_file():
        print(f"[server] error: 未找到前端资源 zip：{zip_path}（前端将回落占位页）")
        return

    # App 私有目录（Chaquopy 提供 HOME）；缺失时退到 app_data 下的隐藏目录
    home = os.environ.get("HOME")
    target = Path(home) / "frontend" / "dist" if home else Path(os.environ["NLD_APP_DATA"]) / ".frontend" / "dist"

    try:
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    except OSError as e:
        print(f"[server] error: 读取前端 zip 失败：{e}（前端将回落占位页）")
        return

    marker = target / ".zip-sha256"
    try:
        if marker.is_file() and marker.read_text(encoding="utf-8").strip() == digest:
            os.environ["NLD_FRONTEND_DIR"] = str(target)
            print(f"[server] 前端资源已是最新（sha256 命中），跳过解压：{target}")
            return
    except OSError:
        pass  # 标记不可读 → 按需重新解压

    target_root = target.resolve()
    try:
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            for member in zf.namelist():
                if member.endswith("/"):
                    continue  # 目录条目：写文件时按需创建
                if Path(member).is_absolute() or ".." in Path(member).parts:
                    print(f"[server] warning: 跳过不安全 zip 成员：{member}")
                    continue
                dest = (target_root / member).resolve()
                if dest != target_root and target_root not in dest.parents:
                    print(f"[server] warning: 跳过越界 zip 成员：{member}")
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out)
    except (OSError, zipfile.BadZipFile) as e:
        print(f"[server] error: 解压前端资源失败：{e}（前端将回落占位页）")
        return

    marker.write_text(digest, encoding="utf-8")
    os.environ["NLD_FRONTEND_DIR"] = str(target)
    print(f"[server] 前端资源已解压到：{target}")


APP_DATA = get_app_data()
os.environ["NLD_APP_DATA"] = str(APP_DATA)  # config_service.py 优先读此 env
ensure_app_data_writable()

# 环境能力表：APK 构建时已排除 playwright，故本环境不支持 browser 引擎。
# 由 shared.config.platform()/supported_modes() 读取，贯穿 core → 后端 → 前端。
os.environ.setdefault("NLD_PLATFORM", "android")

_extract_frontend()  # 必须在 import backend.main 之前：后端在其模块级定位前端

from backend.main import app  # noqa: E402  （现有 FastAPI app）


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
