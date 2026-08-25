"""CLI 存储路径回归测试 — cli.core._get_storage 必须与 backend 共用存储目录。

回归背景：cli.core._get_storage 曾硬编码 `sqlite:///app_data/storage/novels.db`，
导致 SQLiteStorage.base_dir = app_data/storage（父目录），扫不到实际小说目录
app_data/storage/novels/ 下的 <id>.db，交互式菜单"更新已有小说"误报
"没有已下载的小说"。
"""
from shared import config as shared_config
from novelbase.core.options import StorageOptions
from novelbase.core.storage import create_storage
from novelbase.models.novel import Novel

import cli.core


def _make_novel(novel_id: str = "fanqie_1") -> Novel:
    return Novel(
        id=novel_id,
        title="测试小说",
        url="https://fanqienovel.com/page/1",
        author="测试作者",
        serial=1,
        description="",
        count=0,
    )


def test_cli_get_storage_lists_downloaded_novels(tmp_path, monkeypatch):
    """cli 存储应扫描到 backend 同目录下已下载的小说。"""
    monkeypatch.setattr(shared_config, "APP_DATA", tmp_path)
    monkeypatch.setattr(cli.core, "_storage", None)

    # 预置一本已下载小说（backend 同款配置写入）
    store = create_storage(StorageOptions(
        backend="sqlite", database_url=shared_config.get_database_url(),
    ))
    store.save_meta(_make_novel())

    metas = list(cli.core._get_storage().iter_metas())
    assert len(metas) == 1
    assert metas[0].id == "fanqie_1"


def test_cli_build_options_default_storage_matches_shared(tmp_path, monkeypatch):
    """cli build_options 在配置未指定 storage.database_url 时，默认与 backend 一致。"""
    import cli.config

    monkeypatch.setattr(shared_config, "APP_DATA", tmp_path)

    options = cli.config.build_options({"mode": "browser"}, {})
    assert options.storage is not None
    assert options.storage.database_url == shared_config.get_database_url()


def test_cli_build_options_honors_explicit_storage_config(tmp_path, monkeypatch):
    """cli build_options 尊重显式配置的 storage.database_url。"""
    import cli.config

    explicit = "sqlite:////custom/path/novels.db"
    options = cli.config.build_options(
        {"mode": "browser", "storage": {"database_url": explicit}}, {},
    )
    assert options.storage is not None
    assert options.storage.database_url == explicit
