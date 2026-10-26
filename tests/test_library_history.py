# -*- coding: utf-8 -*-
"""search_history.jsonl：append-only 追加、读取去重、压缩、删除。

隔离方式：monkeypatch 模块级路径常量，绝不碰真实 app_data/。
"""
import json

import pytest

from shared import user_data


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr(user_data, "BOOKS_PATH", tmp_path / "library" / "books.yaml")
    monkeypatch.setattr(user_data, "HISTORY_PATH", tmp_path / "library" / "search_history.jsonl")
    monkeypatch.setattr(user_data, "NOVELS_DIR", tmp_path / "novels")
    return user_data


def _write_lines(lib, rows, trailing_newline=True):
    """直接落文件，用来精确控制时间戳与坏行。"""
    lib.HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    if trailing_newline and text:
        text += "\n"
    lib.HISTORY_PATH.write_text(text, encoding="utf-8")


def _row(id_, keyword, when, source="a"):
    return {"id": id_, "source_name": source, "keyword": keyword, "searched_at": when}


# ── 读取 ────────────────────────────────────────────

def test_empty_file_returns_empty_list(lib):
    assert lib.get_search_history() == []


def test_append_and_read_back(lib, monkeypatch):
    monkeypatch.setattr(lib, "_now", lambda: "2026-01-01 00:00:00")
    lib.add_search_history("src-a", "斗破")
    monkeypatch.setattr(lib, "_now", lambda: "2026-01-02 00:00:00")
    lib.add_search_history("src-b", "诡秘")

    rows = lib.get_search_history()
    assert len(rows) == 2
    assert set(rows[0]) == {"id", "source_name", "keyword", "searched_at"}
    assert [r["keyword"] for r in rows] == ["诡秘", "斗破"]      # 倒序


def test_same_pair_appends_but_reads_once(lib):
    _write_lines(lib, [
        _row(1, "斗破", "2026-01-01 00:00:00"),
        _row(2, "斗破", "2099-01-01 00:00:00"),      # 同键、更晚
    ])
    assert len(lib.HISTORY_PATH.read_text(encoding="utf-8").splitlines()) == 2   # 文件里两行

    rows = lib.get_search_history()
    assert len(rows) == 1                                                        # 读取去重
    assert rows[0]["searched_at"] == "2099-01-01 00:00:00"                       # 保留较晚的


def test_order_desc_and_limit(lib):
    _write_lines(lib, [
        _row(1, "k1", "2026-01-01 00:00:00"),
        _row(2, "k2", "2026-03-01 00:00:00"),
        _row(3, "k3", "2026-02-01 00:00:00"),
    ])
    assert [r["keyword"] for r in lib.get_search_history()] == ["k2", "k3", "k1"]
    assert [r["keyword"] for r in lib.get_search_history(limit=2)] == ["k2", "k3"]


def test_bad_json_line_skipped(lib):
    lib.HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    lib.HISTORY_PATH.write_text(
        '{"id": 1, "source_name": "a", "keyword": "好", "searched_at": "2026-01-01 00:00:00"}\n'
        'not json\n',
        encoding="utf-8",
    )
    assert [r["keyword"] for r in lib.get_search_history()] == ["好"]


def test_line_without_id_skipped(lib):
    _write_lines(lib, [
        {"source_name": "a", "keyword": "无id", "searched_at": "2026-01-01 00:00:00"},
        _row(2, "有id", "2026-01-02 00:00:00"),
    ])
    assert [r["keyword"] for r in lib.get_search_history()] == ["有id"]


def test_missing_trailing_newline_is_handled(lib, monkeypatch):
    """末尾没有换行符时追加不能把两行拼成一条（Review Focus 3）。"""
    monkeypatch.setattr(lib, "_now", lambda: "2026-02-01 00:00:00")
    _write_lines(lib, [_row(1, "旧", "2026-01-01 00:00:00")], trailing_newline=False)

    lib.add_search_history("a", "新")

    assert len(lib.HISTORY_PATH.read_text(encoding="utf-8").splitlines()) == 2
    assert {r["keyword"] for r in lib.get_search_history()} == {"旧", "新"}


# ── 删除 ────────────────────────────────────────────

def test_delete_removes_all_rows_with_same_pair(lib):
    _write_lines(lib, [
        _row(1, "斗破", "2026-01-01 00:00:00"),
        _row(2, "斗破", "2099-01-01 00:00:00"),
        _row(3, "诡秘", "2026-01-02 00:00:00"),
    ])
    assert lib.delete_search_history(1) is True
    assert [r["keyword"] for r in lib.get_search_history()] == ["诡秘"]


def test_delete_unknown_id_returns_false(lib):
    _write_lines(lib, [_row(1, "斗破", "2026-01-01 00:00:00")])
    assert lib.delete_search_history(999999) is False


def test_clear_empties_file(lib):
    _write_lines(lib, [_row(1, "斗破", "2026-01-01 00:00:00")])
    lib.clear_search_history()
    assert lib.get_search_history() == []
    assert lib.HISTORY_PATH.exists()
    assert lib.HISTORY_PATH.read_text(encoding="utf-8") == ""


# ── 压缩 ────────────────────────────────────────────

def test_compaction_keeps_latest(lib, monkeypatch):
    monkeypatch.setattr(lib, "_HISTORY_MAX_LINES", 5)
    monkeypatch.setattr(lib, "_HISTORY_KEEP", 3)

    for i in range(6):
        monkeypatch.setattr(lib, "_now", lambda i=i: f"2026-01-0{i + 1} 00:00:00")
        lib.add_search_history("a", f"k{i}")

    lines = lib.HISTORY_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 5
    assert [r["keyword"] for r in lib.get_search_history()] == ["k5", "k4", "k3"]


def test_ids_are_stable_across_compaction(lib, monkeypatch):
    monkeypatch.setattr(lib, "_HISTORY_MAX_LINES", 3)
    monkeypatch.setattr(lib, "_HISTORY_KEEP", 2)

    monkeypatch.setattr(lib, "_now", lambda: "2026-01-01 00:00:00")
    lib.add_search_history("a", "k0")
    monkeypatch.setattr(lib, "_now", lambda: "2026-01-02 00:00:00")
    lib.add_search_history("a", "k1")
    before = {r["keyword"]: r["id"] for r in lib.get_search_history()}

    monkeypatch.setattr(lib, "_now", lambda: "2026-01-03 00:00:00")
    lib.add_search_history("a", "k2")            # 触发压缩

    after = {r["keyword"]: r["id"] for r in lib.get_search_history()}
    assert after["k2"] > before["k1"]            # 新 id 递增
    assert after["k1"] == before["k1"]           # 老 id 不变


def test_new_id_continues_after_existing(lib, monkeypatch):
    """压缩后重启进程，新 id 不能与文件里已有的撞车。"""
    monkeypatch.setattr(lib, "_now", lambda: "2026-01-01 00:00:00")
    _write_lines(lib, [_row(7, "旧", "2026-01-01 00:00:00")])
    monkeypatch.setattr(lib, "_next_id_cache", None)     # 模拟新进程

    lib.add_search_history("a", "新")

    ids = {r["keyword"]: r["id"] for r in lib.get_search_history()}
    assert ids["新"] > 7
