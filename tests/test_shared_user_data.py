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


def test_search_history_dedup_same_key_upsert(tmp_path, monkeypatch):
    """同键 (platform, keyword, mode, variant) 重复添加不新增行，只更新 searched_at。"""
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.add_search_history("fanqie", "斗破苍穹", "api", "rain")
    user_data.add_search_history("fanqie", "斗破苍穹", "api", "rain")
    rows = user_data.get_search_history()
    assert len(rows) == 1
    assert rows[0]["mode"] == "api"
    assert rows[0]["variant"] == "rain"
    assert rows[0]["keyword"] == "斗破苍穹"


def test_search_history_dedup_mode_variant_distinct(tmp_path, monkeypatch):
    """不同 mode/variant 的相同关键词各自保留一条。"""
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.add_search_history("fanqie", "斗破苍穹", "api", "rain")
    user_data.add_search_history("fanqie", "斗破苍穹", "api", "oiapi")
    user_data.add_search_history("fanqie", "斗破苍穹", "browser", "")
    rows = user_data.get_search_history()
    assert len(rows) == 3
    assert {(r["mode"], r["variant"]) for r in rows} == {
        ("api", "rain"), ("api", "oiapi"), ("browser", ""),
    }


def test_search_history_migration_old_db(tmp_path, monkeypatch):
    """旧库（无 mode/variant 列）迁移：加列、fanqie 填 api/rain、其余留空、清理重复、唯一索引生效。"""
    import sqlite3

    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    # 预置旧版表结构 + 数据（fanqie 两条重复）
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE search_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            platform     TEXT NOT NULL,
            keyword      TEXT NOT NULL,
            searched_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        INSERT INTO search_history(platform, keyword) VALUES ('fanqie', '斗破苍穹');
        INSERT INTO search_history(platform, keyword) VALUES ('fanqie', '斗破苍穹');
        INSERT INTO search_history(platform, keyword) VALUES ('qidian', '凡人修仙传');
    """)
    conn.commit()
    conn.close()

    rows = user_data.get_search_history()  # 触发 _connection → _ensure_schema 迁移
    fanqie_rows = [r for r in rows if r["platform"] == "fanqie"]
    qidian_rows = [r for r in rows if r["platform"] == "qidian"]
    assert len(fanqie_rows) == 1, "fanqie 重复记录应被清理为一条"
    assert fanqie_rows[0]["mode"] == "api"
    assert fanqie_rows[0]["variant"] == "rain"
    assert len(qidian_rows) == 1
    assert qidian_rows[0]["mode"] == ""
    assert qidian_rows[0]["variant"] == ""

    # 唯一索引生效：同键写入走 UPSERT，不新增行
    user_data.add_search_history("fanqie", "斗破苍穹", "api", "rain")
    assert len(user_data.get_search_history()) == 2


def test_search_history_migration_guard_keeps_new_records(tmp_path, monkeypatch):
    """PRAGMA user_version 一次性守卫：迁移只执行一次，迁移后写入的 fanqie mode='' 记录不被改写。"""
    db = tmp_path / "user_data.db"
    monkeypatch.setattr(user_data, "DB_PATH", db)
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")

    user_data.get_search_history()  # 首次连接触发迁移
    user_data.add_search_history("fanqie", "凡人修仙传", "")  # 迁移后写入的新记录（mode=''）
    rows = user_data.get_search_history()  # 再次触发连接
    fanqie = [r for r in rows if r["platform"] == "fanqie"]
    assert len(fanqie) == 1
    assert fanqie[0]["mode"] == ""
    assert fanqie[0]["variant"] == ""
