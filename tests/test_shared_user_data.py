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


def test_search_history_add_get_delete(tmp_path, monkeypatch):
    """搜索历史增查删：add 倒序返回、delete 单条、不存在返回 False。"""
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    assert user_data.get_search_history() == []

    user_data.add_search_history("fanqie", "斗破苍穹")
    user_data.add_search_history("qidian", "凡人修仙传")
    rows = user_data.get_search_history()
    assert len(rows) == 2
    # 同秒插入时 searched_at 相同、顺序不确定，只断言集合
    assert {r["keyword"] for r in rows} == {"斗破苍穹", "凡人修仙传"}

    # 删除单条
    target_id = rows[0]["id"]
    assert user_data.delete_search_history(target_id) is True
    assert user_data.delete_search_history(999999) is False  # 不存在返回 False

    rows = user_data.get_search_history()
    assert len(rows) == 1
    assert rows[0]["id"] != target_id  # 剩下的是未被删的那条
