# -*- coding: utf-8 -*-
"""一次性迁移：user_data.db → config/library/{books.yaml, search_history.jsonl}。

夹具在测试里内联旧 schema（生产代码里的 _SCHEMA_SQL 已随 SQLite 后端删除）。
"""
import json
import sqlite3
from pathlib import Path

import pytest
import yaml

from scripts.migrate_user_data import migrate

_OLD_SCHEMA = """
CREATE TABLE groups (
    group_name     TEXT NOT NULL,
    novel_id       TEXT NOT NULL,
    pending_export INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (group_name, novel_id)
);
CREATE TABLE favorites (
    novel_id     TEXT PRIMARY KEY,
    favorited_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    note         TEXT
);
CREATE TABLE search_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name  TEXT NOT NULL,
    keyword      TEXT NOT NULL,
    searched_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(source_name, keyword)
);
CREATE TABLE novel_sources (
    novel_id     TEXT PRIMARY KEY,
    source_name  TEXT NOT NULL,
    updated_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
"""


def _old_db(app) -> "Path":
    return app / "storage" / "users" / "default" / "user_data.db"


@pytest.fixture
def old_app(tmp_path):
    """3 本书：n1（default + 来源 + 收藏 + 有书名）、n2（双组，TEST 组带 pending_export）、
    n3（孤儿：只在 groups 里，无来源、无书籍库）。搜索历史 2 条。"""
    app = tmp_path / "app_data"

    novels = app / "storage" / "novels"
    novels.mkdir(parents=True)
    conn = sqlite3.connect(str(novels / "n1.db"))
    conn.execute("CREATE TABLE meta (id TEXT PRIMARY KEY, title TEXT NOT NULL)")
    conn.execute("INSERT INTO meta VALUES (?, ?)", ("https://x/1", "书名一"))
    conn.commit()
    conn.close()

    db = _old_db(app)
    db.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db))
    conn.executescript(_OLD_SCHEMA)
    conn.executemany("INSERT INTO groups VALUES (?,?,?)", [
        ("default", "n1", 0),
        ("TEST", "n2", 1),
        ("default", "n2", 0),
        ("default", "n3", 0),
    ])
    conn.execute("INSERT INTO favorites(novel_id, favorited_at) VALUES ('n1', '2026-09-20 10:00:00')")
    conn.execute("INSERT INTO novel_sources VALUES ('n1', 'src-a', datetime('now','localtime'))")
    conn.executemany(
        "INSERT INTO search_history(source_name, keyword, searched_at) VALUES (?,?,?)",
        [("src-a", "斗破", "2026-10-01 00:00:00"), ("src-b", "诡秘", "2026-10-02 00:00:00")],
    )
    conn.commit()
    conn.close()
    return app


def _books(app):
    return yaml.safe_load(
        (app / "config" / "library" / "books.yaml").read_text(encoding="utf-8")
    )


def _history(app):
    text = (app / "config" / "library" / "search_history.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# ── dry-run ─────────────────────────────────────────

def test_dry_run_writes_nothing(old_app):
    result = migrate(old_app)

    assert result["skipped"] is None
    assert result["books"] == 3
    assert result["history"] == 2
    assert result["written"] == []
    assert not (old_app / "config" / "library" / "books.yaml").exists()
    assert not (old_app / "config" / "library" / "search_history.jsonl").exists()
    assert _old_db(old_app).exists()          # 旧库原样保留


# ── apply ───────────────────────────────────────────

def test_apply_writes_both_files(old_app):
    result = migrate(old_app, apply=True)
    assert result["skipped"] is None

    books = _books(old_app)
    assert set(books) == {"n1", "n2", "n3"}

    assert books["n1"]["title"] == "书名一"
    assert books["n1"]["favorite"] is True
    assert books["n1"]["favorited_at"] == "2026-09-20 10:00:00"
    assert books["n1"]["source"] == "src-a"
    assert books["n1"]["groups"] == {"default": {}}

    assert books["n2"]["groups"] == {"TEST": {"pending_export": True}, "default": {}}
    assert "source" not in books["n2"]

    assert books["n3"]["groups"] == {"default": {}}
    assert "source" not in books["n3"]         # 孤儿没有来源
    assert "title" not in books["n3"]          # 也没有书籍库


def test_apply_migrates_all_history(old_app):
    migrate(old_app, apply=True)

    rows = _history(old_app)
    assert len(rows) == 2
    assert [r["id"] for r in rows] == [1, 2]
    assert {r["keyword"] for r in rows} == {"斗破", "诡秘"}
    assert rows[0]["searched_at"] == "2026-10-01 00:00:00"   # 按时间正序落盘


def test_apply_backup_contains_all_rows(old_app):
    """WAL 里有未合并写入时，备份文件必须完整 —— 迁移前要 wal_checkpoint。"""
    db = _old_db(old_app)
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "INSERT INTO search_history(source_name, keyword, searched_at) "
        "VALUES ('src-c', '新词', '2026-10-03 00:00:00')"
    )
    conn.commit()                              # 已提交，但仍在 -wal 里（未关连接）
    try:
        migrate(old_app, apply=True)
    finally:
        try:
            conn.close()
        except sqlite3.Error:                  # users/ 已被迁移删掉
            pass

    assert len(_history(old_app)) == 3

    backup = old_app / "config" / "library" / "user_data.db.migrated"
    assert backup.exists()
    bak = sqlite3.connect(str(backup))
    try:
        assert bak.execute("SELECT COUNT(*) FROM search_history").fetchone()[0] == 3
    finally:
        bak.close()


def test_refuses_when_target_exists(old_app):
    library = old_app / "config" / "library"
    library.mkdir(parents=True)
    (library / "books.yaml").write_text("", encoding="utf-8")

    result = migrate(old_app, apply=True)
    assert result["skipped"] is not None
    assert (library / "books.yaml").read_text(encoding="utf-8") == ""

    result = migrate(old_app, apply=True, force=True)
    assert result["skipped"] is None
    assert "n1" in (library / "books.yaml").read_text(encoding="utf-8")


def test_apply_backs_up_and_removes_users_dir(old_app):
    migrate(old_app, apply=True)

    assert (old_app / "config" / "library" / "user_data.db.migrated").exists()
    assert not (old_app / "storage" / "users").exists()
    assert (old_app / "storage" / "novels" / "n1.db").exists()      # 小说库不动


def test_apply_is_idempotent_when_no_source_db(tmp_path):
    app = tmp_path / "empty"
    result = migrate(app, apply=True)

    assert result["skipped"] is not None
    assert not (app / "config").exists()
