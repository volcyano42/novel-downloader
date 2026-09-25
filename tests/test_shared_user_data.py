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

    user_data.add_search_history("fanqie-api-rain", "斗破苍穹")
    user_data.add_search_history("qidian-browser-default", "凡人修仙传")
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


def test_search_history_uses_source_name(tmp_path, monkeypatch):
    """唯一键 (source_name, keyword)：同书源同词 upsert，不同书源各自保留。"""
    from shared import user_data

    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")
    user_data.add_search_history("fanqie-api-rain", "斗破")
    user_data.add_search_history("fanqie-api-rain", "斗破")  # 同键 upsert
    user_data.add_search_history("92xs-requests-default", "斗破")
    rows = user_data.get_search_history()
    assert len(rows) == 2
    assert {r["source_name"] for r in rows} == {"fanqie-api-rain", "92xs-requests-default"}
    assert "mode" not in rows[0] and "variant" not in rows[0] and "platform" not in rows[0]


def test_search_history_old_schema_dropped_rebuilt(tmp_path, monkeypatch):
    """旧库（含 platform 列）打开时 drop 重建为空的新表（不迁移旧数据）。"""
    import sqlite3

    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE search_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            platform     TEXT NOT NULL,
            keyword      TEXT NOT NULL,
            searched_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        INSERT INTO search_history(platform, keyword) VALUES ('fanqie', '斗破');
    """)
    conn.commit()
    conn.close()

    # 首次连接触发 drop 重建，旧数据不保留
    assert user_data.get_search_history() == []

    # 新表可用且唯一键为 (source_name, keyword)
    user_data.add_search_history("fanqie-api-rain", "斗破")
    rows = user_data.get_search_history()
    assert len(rows) == 1
    assert rows[0]["source_name"] == "fanqie-api-rain"


def test_novel_source_set_get_upsert(tmp_path, monkeypatch):
    """set 写入、get 读回、同 id 再 set 为 UPSERT 覆盖。"""
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    assert user_data.get_novel_source("n1") is None
    user_data.set_novel_source("n1", "fanqie-api-rain")
    assert user_data.get_novel_source("n1") == "fanqie-api-rain"

    user_data.set_novel_source("n1", "qimao-api-rain")   # UPSERT 覆盖
    assert user_data.get_novel_source("n1") == "qimao-api-rain"


def test_novel_source_skips_empty(tmp_path, monkeypatch):
    """空 source_name 不写行，避免无来源的孤儿记录。"""
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.set_novel_source("n1", "")
    assert user_data.get_novel_source("n1") is None


def test_novel_sources_batch_only_hits(tmp_path, monkeypatch):
    """批量查询只返回命中的 id。"""
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.set_novel_source("n1", "fanqie-api-rain")
    user_data.set_novel_source("n2", "qimao-api-rain")
    assert user_data.get_novel_sources(["n1", "n2", "n3"]) == {
        "n1": "fanqie-api-rain",
        "n2": "qimao-api-rain",
    }
    assert user_data.get_novel_sources([]) == {}


def test_novel_source_delete(tmp_path, monkeypatch):
    """删书清理：删掉返回 True，重复删返回 False。"""
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.set_novel_source("n1", "fanqie-api-rain")
    assert user_data.delete_novel_source("n1") is True
    assert user_data.delete_novel_source("n1") is False
    assert user_data.get_novel_source("n1") is None
