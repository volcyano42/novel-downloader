"""init_config 的 user_data.db 空表模板初始化测试。"""
import sqlite3

import init_config
from shared.user_data import _SCHEMA_SQL

_TABLES = ("groups", "favorites", "search_history", "bookmarks")


def _db_objects(db_path) -> list[str]:
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','index') "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def _template_db() -> str:
    return str(init_config._get_root() / "template" / "storage" / "users" / "default" / "user_data.db")


def test_template_db_exists_with_empty_schema():
    """template/ 下模板库存在，四张表齐备且全空"""
    tmpl = _template_db()
    assert __import__("os").path.exists(tmpl), "template user_data.db 缺失"
    objs = _db_objects(tmpl)
    for t in _TABLES:
        assert t in objs, f"模板库缺表 {t}"
    conn = sqlite3.connect(tmpl)
    counts = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in _TABLES
    }
    conn.close()
    assert all(c == 0 for c in counts.values()), f"模板库应为空表，实际: {counts}"


def test_template_schema_matches_runtime():
    """模板库 schema 与运行时 _SCHEMA_SQL 一致（防止模板与建表逻辑漂移）"""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        runtime_db = f"{td}/runtime.db"
        conn = sqlite3.connect(runtime_db)
        conn.executescript(_SCHEMA_SQL)
        conn.close()
        assert _db_objects(runtime_db) == _db_objects(_template_db())


def test_init_user_db_copies_template_once(tmp_path, monkeypatch):
    """init_user_db 目标不存在时复制模板；已存在时幂等不覆盖"""
    monkeypatch.setattr(init_config, "_user_db_target_dir", lambda: tmp_path)
    copied = init_config.init_user_db()
    assert len(copied) == 1
    assert (tmp_path / "user_data.db").exists()
    # 幂等：再次调用不复制（目标已存在），不覆盖用户数据
    assert init_config.init_user_db() == []


def test_user_db_target_dir_respects_env(tmp_path, monkeypatch):
    """NLD_APP_DATA env 下 user_data.db 目标目录正确"""
    monkeypatch.setenv("NLD_APP_DATA", str(tmp_path))
    target = init_config._user_db_target_dir()
    assert target == tmp_path / "storage" / "users" / "default"
