# -*- coding: utf-8 -*-
"""server.py 逻辑的本地可测部分（Android 环境外验证 env 注入与挂载）。"""
import os
import sys
import importlib
from pathlib import Path
from starlette.routing import Mount

SERVER_PY_DIR = str(
    Path(__file__).resolve().parent.parent / "android" / "app" / "src" / "main" / "python"
)


def _import_server():
    """确保以全新状态 import server 模块（避免模块缓存污染）。

    importlib.import_module 对已加载模块直接命中 sys.modules 缓存，
    必须在每次导入前弹出缓存，否则第二个测试会拿到第一个测试加载时的
    模块实例（那时 assets/frontend 尚不存在，mount 不会生效）。
    """
    sys.path.insert(0, SERVER_PY_DIR)
    try:
        sys.modules.pop("server", None)
        return importlib.import_module("server")
    finally:
        sys.path.pop(0)


def test_server_module_sets_nld_app_data_when_env_present(tmp_path, monkeypatch):
    monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "app_data"))
    server = _import_server()
    assert os.environ["NLD_APP_DATA"] == str(tmp_path / "app_data")
    assert server.get_app_data() == (tmp_path / "app_data").resolve()


def test_server_module_has_app_with_static_mount(tmp_path, monkeypatch):
    # 模拟 CI 产物：创建 assets/frontend 目录，确保 mount 生效
    assets = Path(__file__).resolve().parent.parent / "android" / "app" / "src" / "main" / "assets" / "frontend"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "index.html").write_text("<html>test</html>", encoding="utf-8")
    try:
        monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "app_data"))
        server = _import_server()
        mount_paths = [r.path for r in server.app.routes if isinstance(r, Mount)]
        assert any(p in ("/", "") for p in mount_paths), f"根挂载缺失，实际 mounts: {mount_paths}"
    finally:
        import shutil
        shutil.rmtree(assets.parent, ignore_errors=True)
