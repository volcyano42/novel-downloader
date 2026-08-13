import sqlite3
from pathlib import Path

from shared import user_data


def test_user_data_db_path_under_users_default(tmp_path, monkeypatch):
    # 用 monkeypatch 覆盖模块级 DB_PATH
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.add_favorite("fanqie_123")
    assert user_data.load_favorites() == ["fanqie_123"]
    user_data.remove_favorite("fanqie_123")
    assert user_data.load_favorites() == []


def test_groups_roundtrip(tmp_path, monkeypatch):
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    assert user_data.add_novel_to_group("fanqie_1", "default")
    assert user_data.get_novel_group("fanqie_1") == "default"
    assert user_data.load_groups() == {"default": {"fanqie_1": {"pending_export": False}}}
