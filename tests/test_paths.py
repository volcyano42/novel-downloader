"""编译产物路径定位：Nuitka（`__compiled__`）与 PyInstaller（`sys.frozen`）都要落在 exe 同目录。

回归背景（用户报「exe 无法识别同目录下的 app_data」）：
三处 app_data 定位（`shared/config.py`、`cli/config.py`、`init_config.py`）都只认
PyInstaller 的 `sys.frozen`，而 Nuitka 产物**不设**该属性（实测 `sys.frozen=False`、
`__compiled__=True`），于是全部走源码分支，指向与 exe 无关的目录。
"""
from pathlib import Path

import pytest

import init_config
from cli import config as cli_config
from shared import config as shared_config
from shared import paths

# ── shared.paths ──────────────────────────────────────────────

def test_source_run_is_not_compiled():
    assert paths.is_compiled() is False
    assert paths.exe_dir() is None


def test_exe_dir_prefers_onefile_directory(monkeypatch, tmp_path):
    """Nuitka onefile：sys.executable 指向临时解包目录，必须用 NUITKA_ONEFILE_DIRECTORY。"""
    monkeypatch.setattr(paths, "is_compiled", lambda: True)
    monkeypatch.setenv("NUITKA_ONEFILE_DIRECTORY", str(tmp_path))
    assert paths.exe_dir() == tmp_path.resolve()


def test_exe_dir_falls_back_to_sys_executable(monkeypatch, tmp_path):
    """PyInstaller / Nuitka standalone：进程即 exe，sys.executable 指向它。"""
    monkeypatch.setattr(paths, "is_compiled", lambda: True)
    monkeypatch.delenv("NUITKA_ONEFILE_DIRECTORY", raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(tmp_path / "app.exe"))
    assert paths.exe_dir() == tmp_path.resolve()


# ── app_data 定位（shared / cli 两份实现）─────────────────────

@pytest.mark.parametrize("module", [shared_config, cli_config])
def test_app_data_dir_uses_exe_dir_when_compiled(monkeypatch, tmp_path, module):
    monkeypatch.setattr(module, "exe_dir", lambda: tmp_path / "dist")
    app_data = module._get_app_data_dir()
    assert app_data == tmp_path / "dist" / "app_data"
    assert app_data.is_dir()


@pytest.mark.parametrize("module", [shared_config, cli_config])
def test_nld_app_data_env_wins(monkeypatch, tmp_path, module):
    monkeypatch.setenv("NLD_APP_DATA", str(tmp_path / "custom"))
    monkeypatch.setattr(module, "exe_dir", lambda: tmp_path / "dist")
    assert module._get_app_data_dir() == (tmp_path / "custom").resolve()


# ── init_config 目标目录 ──────────────────────────────────────

def test_init_config_targets_exe_dir_when_compiled(monkeypatch, tmp_path):
    """编译产物：config 与 user_data.db 都初始化到 exe 同目录的 app_data/ 下。"""
    monkeypatch.setattr(init_config, "exe_dir", lambda: tmp_path / "dist")
    assert init_config._target_dir() == tmp_path / "dist" / "app_data" / "config"
    assert init_config._user_db_target_dir() == (
        tmp_path / "dist" / "app_data" / "storage" / "users" / "default"
    )


def test_init_config_source_run_targets_project_root():
    project_root = Path(init_config.__file__).resolve().parent
    assert init_config._target_dir() == project_root / "app_data" / "config"


# ── 运行时用户数据（user_data.db / groups.yaml）────────────────

def test_user_data_paths_track_app_data(monkeypatch, tmp_path):
    """`user_data.db`（groups/favorites/历史）必须派生自 `shared.config.APP_DATA`。

    回归背景：它曾用 `Path(__file__).resolve().parent.parent` 推导 —— Nuitka onefile 下
    `__file__` 在**临时解包目录**，于是这些读写全落在解包目录（每次运行新建空库），
    表现为「书架里的书全部归到未分类」，而走 APP_DATA 的小说库却正常加载。
    """
    import importlib

    from shared import user_data

    try:
        monkeypatch.setattr(shared_config, "APP_DATA", tmp_path / "exe_app_data")
        importlib.reload(user_data)
        assert user_data.DB_PATH == (
            tmp_path / "exe_app_data" / "storage" / "users" / "default" / "user_data.db"
        )
        assert user_data.GROUPS_YAML == tmp_path / "exe_app_data" / "config" / "groups.yaml"
    finally:
        importlib.reload(user_data)  # 还原真实路径，避免污染其它用例
