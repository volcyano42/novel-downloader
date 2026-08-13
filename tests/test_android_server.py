# -*- coding: utf-8 -*-
"""server.py 逻辑的本地可测部分（Android 环境外验证 env 注入、挂载与 /api/v2/health 可达性）。"""
import os
import sys
import shutil
import importlib
from pathlib import Path
import pytest
from starlette.routing import Mount

SERVER_PY_DIR = str(
    Path(__file__).resolve().parent.parent / "android" / "app" / "src" / "main" / "python"
)
ASSETS_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "android" / "app" / "src" / "main" / "assets" / "frontend"
FALLBACK_APP_DATA_DIR = Path(__file__).resolve().parent.parent / "android" / "app" / "src" / "main" / "app_data"


def _import_server():
    """确保以全新状态 import server 模块（避免模块缓存污染）。

    importlib.import_module 对已加载模块直接命中 sys.modules 缓存，
    必须在每次导入前弹出缓存，否则第二个测试会拿到第一个测试加载时的
    模块实例（那时 assets/frontend 尚不存在，mount 不会生效）。
    同时弹出 backend.main，避免两次测试共享同一 FastAPI app
    导致 /api/v2/health 与根挂载重复注册。
    """
    sys.path.insert(0, SERVER_PY_DIR)
    try:
        sys.modules.pop("server", None)
        sys.modules.pop("backend.main", None)
        return importlib.import_module("server")
    finally:
        sys.path.pop(0)


def _remove_frontend_mount(server):
    """从共享的 backend.main.app 移除本次挂载的根 Mount（name == "frontend"）。

    server 模块级 mount 挂在进程内共享的 FastAPI app 上，若测试后不清理，
    会永久污染后续测试（指向已删除目录）。见 I3。
    """
    if server is not None:
        server.app.routes[:] = [
            r for r in server.app.routes
            if not (isinstance(r, Mount) and r.name == "frontend")
        ]


def test_server_module_sets_nld_app_data_when_env_present(tmp_path, monkeypatch):
    monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "app_data"))
    server = _import_server()
    assert os.environ["NLD_APP_DATA"] == str(tmp_path / "app_data")
    assert server.get_app_data() == (tmp_path / "app_data").resolve()


def test_server_module_has_app_with_static_mount(tmp_path, monkeypatch):
    # 模拟 CI 产物：创建 assets/frontend 目录，确保 mount 生效
    assets = Path(__file__).resolve().parent.parent / "android" / "app" / "src" / "main" / "assets" / "frontend"
    assets_existed_before = assets.exists()
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "index.html").write_text("<html>test</html>", encoding="utf-8")
    try:
        monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "app_data"))
        server = _import_server()
        mount_paths = [r.path for r in server.app.routes if isinstance(r, Mount)]
        assert any(p in ("/", "") for p in mount_paths), f"根挂载缺失，实际 mounts: {mount_paths}"
    finally:
        if not assets_existed_before:
            import shutil
            shutil.rmtree(assets.parent, ignore_errors=True)
        else:
            (assets / "index.html").unlink(missing_ok=True)


@pytest.mark.skip(reason="TestClient lifespan 在部分环境下挂起，待 #I4 修复")
def test_health_route_reachable_via_test_client(tmp_path, monkeypatch):
    """健康检查复用 backend.main 的 /api/v2/health（注册于 SPA fallback 与根 mount 之前，始终可达）。

    已知问题：TestClient 触发 async lifespan 时在 Windows / CI 的某些 Python 版本下挂起，
    底层与 Starlette/FastAPI 的事件循环管理有关，暂时 skip 等待 #I4 修复。
    """
    import asyncio
    from fastapi.testclient import TestClient
    assets_existed_before = ASSETS_FRONTEND_DIR.exists()
    ASSETS_FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
    (ASSETS_FRONTEND_DIR / "index.html").write_text("<html>test</html>", encoding="utf-8")
    server = None
    try:
        monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "app_data"))
        server = _import_server()
        with TestClient(server.app, raise_server_exceptions=False) as client:
            resp = client.get("/api/v2/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("ok") is True
        assert body["data"]["status"] == "ok"
    finally:
        _remove_frontend_mount(server)
        if not assets_existed_before:
            shutil.rmtree(ASSETS_FRONTEND_DIR.parent, ignore_errors=True)
        else:
            (ASSETS_FRONTEND_DIR / "index.html").unlink(missing_ok=True)


def test_server_module_injects_app_data_env_when_absent(monkeypatch):
    """无 NLD_APP_DATA env 时，server 模块必须自行注入兜底目录（I1 回归）。"""
    # 确保 env 不存在，验证模块级注入不是空操作
    monkeypatch.delenv("NLD_APP_DATA", raising=False)
    app_data_existed_before = FALLBACK_APP_DATA_DIR.exists()
    server = _import_server()
    try:
        injected = os.environ["NLD_APP_DATA"]
        assert injected == str(server.get_app_data())
        # 无 env 时走本地兜底分支：android/app/src/main/app_data
        assert server.get_app_data() == FALLBACK_APP_DATA_DIR
    finally:
        # 清理模块级 ensure_app_data_writable() 创建的兜底目录（仅当测试自建时）
        if not app_data_existed_before:
            shutil.rmtree(FALLBACK_APP_DATA_DIR, ignore_errors=True)
        else:
            probe = FALLBACK_APP_DATA_DIR / ".write_probe"
            probe.unlink(missing_ok=True)
