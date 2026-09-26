# -*- coding: utf-8 -*-
"""server.py 逻辑的本地可测部分（Android 环境外验证 env 注入、前端交付与 /api/v2/health 可达性）。

不启 TestClient/lifespan（本仓库有 lifespan 在部分环境下挂起的历史问题），
统一用 `httpx.ASGITransport` 直接打 ASGI app。
"""
import asyncio
import hashlib
import importlib
import os
import shutil
import sys
import zipfile
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVER_PY_DIR = str(REPO_ROOT / "android" / "app" / "src" / "main" / "python")
FALLBACK_APP_DATA_DIR = REPO_ROOT / "android" / "app" / "src" / "main" / "app_data"
PLACEHOLDER_TEXT = "前端尚未构建"


@pytest.fixture(autouse=True)
def _restore_server_modules():
    """每个用例前后快照/恢复 server 与 backend.main，避免模块缓存跨用例污染。"""
    saved = {name: sys.modules.get(name) for name in ("server", "backend.main")}
    yield
    for name, mod in saved.items():
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod


def _import_server():
    """确保以全新状态 import server 模块（弹出缓存，避免共享旧 app / 旧 env）。"""
    sys.path.insert(0, SERVER_PY_DIR)
    try:
        sys.modules.pop("server", None)
        sys.modules.pop("backend.main", None)
        return importlib.import_module("server")
    finally:
        sys.path.pop(0)


def _get(app, path: str):
    """同步打一次 ASGI 请求（每个请求独立事件循环，等价于真实 HTTP 访问）。"""

    async def _call():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(_call())


def _write_zip(path: Path, entries: dict) -> str:
    """按 {成员名: 文本} 写 zip，返回 sha256。"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in entries.items():
            zf.writestr(name, text)
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── env 注入 ──────────────────────────────────────────────────

def test_server_module_sets_nld_app_data_when_env_present(tmp_path, monkeypatch):
    monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "app_data"))
    monkeypatch.setenv("NLD_FRONTEND_DIR", str(tmp_path / "no-frontend"))
    server = _import_server()
    assert os.environ["NLD_APP_DATA"] == str(tmp_path / "app_data")
    assert server.get_app_data() == (tmp_path / "app_data").resolve()


def test_server_module_injects_nld_platform_android(tmp_path, monkeypatch):
    """server 模块必须注入 NLD_PLATFORM=android（环境能力表据此排除 browser）。"""
    monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "app_data"))
    monkeypatch.delenv("NLD_PLATFORM", raising=False)
    _import_server()
    assert os.environ.get("NLD_PLATFORM") == "android"


def test_server_module_injects_app_data_env_when_absent(monkeypatch):
    """无 NLD_APP_DATA env 时，server 模块必须自行注入兜底目录（I1 回归）。"""
    monkeypatch.delenv("NLD_APP_DATA", raising=False)
    monkeypatch.delenv("NLD_FRONTEND_DIR", raising=False)
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
            (FALLBACK_APP_DATA_DIR / ".write_probe").unlink(missing_ok=True)


# ── 端到端：前端交付（NLD_FRONTEND_DIR 指向真实目录） ─────────

def test_frontend_served_end_to_end(tmp_path, monkeypatch):
    """根路径必须返回前端（不再是占位页），assets / SPA 路由 / health 均可达。"""
    front = tmp_path / "frontend" / "dist"
    (front / "assets").mkdir(parents=True)
    (front / "index.html").write_text("<html><body>SHELL-OK</body></html>", encoding="utf-8")
    (front / "assets" / "x.js").write_text("console.log('x');", encoding="utf-8")

    monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "app_data"))
    monkeypatch.setenv("NLD_FRONTEND_DIR", str(front))
    server = _import_server()

    root = _get(server.app, "/")
    assert root.status_code == 200
    assert "SHELL-OK" in root.text
    assert PLACEHOLDER_TEXT not in root.text  # 关键断言：白页不再出现

    asset = _get(server.app, "/assets/x.js")
    assert asset.status_code == 200
    assert "console.log" in asset.text

    spa = _get(server.app, "/novels")  # SPA 路由回 index.html
    assert spa.status_code == 200
    assert "SHELL-OK" in spa.text

    health = _get(server.app, "/api/v2/health")
    assert health.status_code == 200
    assert health.json()["data"]["status"] == "ok"


def test_find_frontend_dist_returns_none_when_candidates_missing(tmp_path, monkeypatch):
    """候选全部落空时 _find_frontend_dist() 返回 None（这是占位页分支的判据）。

    注意：本地仓库根确实存在 frontend/dist，所以不能用「删目录」制造负例——
    改为把 _project_root / cwd / NLD_FRONTEND_DIR 全指向空临时目录后直接断言。
    """
    import backend.main as bm

    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    monkeypatch.setattr(bm, "_project_root", empty)
    monkeypatch.delenv("NLD_FRONTEND_DIR", raising=False)

    candidates = bm._frontend_candidates()
    assert candidates, "候选列表不应为空"
    assert all(not (c / "index.html").exists() for c in candidates)
    assert bm._find_frontend_dist() is None


# ── zip 解压 ─────────────────────────────────────────────────

def _prepare_extract(tmp_path, monkeypatch, entries: dict):
    """构造 <tmp>/frontend.zip 并把 server.__file__ 指到同目录，返回 (server, target, digest)。"""
    monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "app_data"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("NLD_FRONTEND_DIR", raising=False)
    digest = _write_zip(tmp_path / "frontend.zip", entries)

    server = _import_server()
    monkeypatch.setattr(server, "__file__", str(tmp_path / "server.py"))
    return server, tmp_path / "home" / "frontend" / "dist", digest


def test_extract_frontend_extracts_and_sets_env(tmp_path, monkeypatch):
    server, target, digest = _prepare_extract(tmp_path, monkeypatch, {
        "index.html": "<html>SHELL-OK</html>",
        "assets/x.js": "console.log('x');",
    })
    server._extract_frontend()

    assert (target / "index.html").read_text(encoding="utf-8") == "<html>SHELL-OK</html>"
    assert (target / "assets" / "x.js").read_text(encoding="utf-8") == "console.log('x');"
    assert os.environ["NLD_FRONTEND_DIR"] == str(target)
    assert (target / ".zip-sha256").read_text(encoding="utf-8").strip() == digest


def test_extract_frontend_idempotent_via_sha256(tmp_path, monkeypatch):
    """二次调用命中 sha256 标记 → 不重复解压（被删掉的产物不会被重建）。"""
    server, target, _ = _prepare_extract(tmp_path, monkeypatch, {
        "index.html": "<html>ok</html>", "assets/x.js": "x",
    })
    server._extract_frontend()
    assert (target / "index.html").is_file()

    (target / "index.html").unlink()  # 破坏产物：命中标记时不应被重建
    server._extract_frontend()
    assert not (target / "index.html").exists()
    assert os.environ["NLD_FRONTEND_DIR"] == str(target)


def test_extract_frontend_rejects_zip_slip(tmp_path, monkeypatch):
    """含 ../evil.txt 成员的 zip 不得把文件写到目标目录之外。"""
    server, target, _ = _prepare_extract(tmp_path, monkeypatch, {
        "index.html": "<html>ok</html>", "../evil.txt": "pwned",
    })
    server._extract_frontend()

    assert (target / "index.html").is_file()
    assert not (tmp_path / "home" / "frontend" / "evil.txt").exists()
    assert not (tmp_path / "evil.txt").exists()


def test_extract_frontend_missing_zip_leaves_env_unset(tmp_path, monkeypatch):
    """zip 缺失 → 不设 NLD_FRONTEND_DIR（前端回落占位页），且不抛异常。"""
    monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "app_data"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("NLD_FRONTEND_DIR", raising=False)
    server = _import_server()
    monkeypatch.setattr(server, "__file__", str(tmp_path / "server.py"))  # 该目录下无 frontend.zip

    server._extract_frontend()

    assert "NLD_FRONTEND_DIR" not in os.environ
