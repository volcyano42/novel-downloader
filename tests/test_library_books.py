# -*- coding: utf-8 -*-
"""books.yaml 书维度账本：读写、原子写、解析失败、多组、title 同步。

隔离方式：monkeypatch 模块级路径常量，绝不碰真实 app_data/。
"""
import os
import sqlite3

import pytest

from shared import user_data


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "LIBRARY_DIR", tmp_path / "library")
    monkeypatch.setattr(user_data, "BOOKS_PATH", tmp_path / "library" / "books.yaml")
    monkeypatch.setattr(user_data, "HISTORY_PATH", tmp_path / "library" / "search_history.jsonl")
    monkeypatch.setattr(user_data, "NOVELS_DIR", tmp_path / "novels")
    return user_data


def _write_books(lib, text: str) -> None:
    lib.BOOKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lib.BOOKS_PATH.write_text(text, encoding="utf-8")


def _make_novel_db(lib, novel_id: str, title: str) -> None:
    """造一个最小 novels/<id>.db（只需要 meta.title）。"""
    lib.NOVELS_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(lib.NOVELS_DIR / f"{novel_id}.db"))
    conn.execute("CREATE TABLE IF NOT EXISTS meta (id TEXT PRIMARY KEY, title TEXT NOT NULL)")
    conn.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (f"https://x/{novel_id}", title))
    conn.commit()
    conn.close()


# ── 读取基础 ────────────────────────────────────────

def test_missing_file_reads_empty(lib):
    assert lib.load_groups() == {}
    assert lib.load_favorites() == []
    assert lib.get_novel_source("nope") is None


def test_corrupt_file_raises_and_is_not_overwritten(lib):
    """YAML 语法错误 → 读写都抛；原文件绝不被覆盖。"""
    bad = "a: [1, 2\n"
    _write_books(lib, bad)

    with pytest.raises(lib.LibraryCorruptError):
        lib.load_groups()
    with pytest.raises(lib.LibraryCorruptError):
        lib.add_favorite("n1")

    assert lib.BOOKS_PATH.read_text(encoding="utf-8") == bad


def test_top_level_not_dict_raises(lib):
    _write_books(lib, "- a\n- b\n")
    with pytest.raises(lib.LibraryCorruptError):
        lib.load_groups()


def test_null_entry_normalized_to_empty_dict(lib):
    """手写成 `n1:`（值为 null）→ 归一成 {}，后续操作不抛 AttributeError。"""
    _write_books(lib, "n1:\n")

    assert lib.load_favorites() == []
    assert lib.add_favorite("n1") is True
    assert lib.is_favorite("n1") is True


# ── 分组 ────────────────────────────────────────────

def test_groups_roundtrip(lib):
    assert lib.add_novel_to_group("n1", "default") is True
    assert lib.get_novel_group("n1") == "default"
    assert lib.load_groups() == {"default": {"n1": {}}}


def test_add_novel_to_group_moves_out_of_other_groups(lib):
    lib.add_novel_to_group("n1", "A")
    assert lib.add_novel_to_group("n1", "A") is False
    assert lib.add_novel_to_group("n1", "B") is True
    assert lib.load_groups() == {"B": {"n1": {}}}


def test_multi_group_via_save_groups(lib):
    lib.save_groups({"A": {"n1": {"pending_export": True}}, "B": {"n1": {}}})
    assert lib.load_groups() == {"A": {"n1": {"pending_export": True}}, "B": {"n1": {}}}


def test_save_groups_keeps_favorite_and_source(lib):
    """全量覆盖 groups 不得抹掉 favorite / source。"""
    lib.set_novel_source("n1", "src-a")
    lib.add_favorite("n1")

    lib.save_groups({"G": {"n1": {}}})

    assert lib.get_novel_source("n1") == "src-a"
    assert lib.is_favorite("n1") is True
    assert lib.load_groups() == {"G": {"n1": {}}}


def test_save_groups_drops_key_only_when_entry_empties(lib):
    """判据是「整个条目为空」，不是「没有已知字段」。"""
    lib.add_favorite("n1")
    lib.save_groups({})                      # 清掉 group，favorite 还在
    assert lib.is_favorite("n1") is True

    lib.remove_favorite("n1")                # 现在什么都没有了
    assert lib._load_books() == {}


def test_unknown_fields_survive_rewrite(lib):
    """用户手写的未知字段不能丢。"""
    _write_books(lib, "n1:\n  note: 好看\n")
    lib.add_favorite("n1")
    assert lib._load_books()["n1"]["note"] == "好看"


# ── 收藏 ────────────────────────────────────────────

def test_favorites_ordered_by_favorited_at_desc(lib):
    _write_books(
        lib,
        'a:\n  favorite: true\n  favorited_at: "2026-01-01 00:00:00"\n'
        'b:\n  favorite: true\n  favorited_at: "2026-02-01 00:00:00"\n'
        'c:\n  favorite: true\n',
    )
    assert lib.load_favorites() == ["b", "a", "c"]   # 无时间戳的排最后


def test_favorite_toggle(lib):
    assert lib.add_favorite("n1") is True
    assert lib.add_favorite("n1") is False
    assert lib.remove_favorite("n1") is True
    assert lib.remove_favorite("n1") is False
    assert lib.is_favorite("n1") is False


# ── 来源与书名 ──────────────────────────────────────

def test_set_novel_source_skips_empty(lib):
    lib.set_novel_source("n1", "")
    assert lib._load_books() == {}


def test_set_novel_source_always_syncs_title(lib):
    """title 保持最新：每次 set_novel_source 都从 meta.title 覆盖。"""
    _make_novel_db(lib, "n1", "新书名")
    lib.set_novel_source("n1", "src-a")
    assert lib._load_books()["n1"]["title"] == "新书名"

    _make_novel_db(lib, "n1", "改名后")
    lib.set_novel_source("n1", "src-a")
    assert lib._load_books()["n1"]["title"] == "改名后"


def test_title_sync_tolerates_missing_novels_db(lib):
    lib.set_novel_source("n1", "src-a")      # 没有书籍库
    entry = lib._load_books()["n1"]
    assert entry["source"] == "src-a"
    assert "title" not in entry


def test_novel_sources_batch_and_delete(lib):
    lib.set_novel_source("n1", "src-a")
    lib.set_novel_source("n2", "src-b")

    assert lib.get_novel_sources(["n1", "n2", "n3"]) == {"n1": "src-a", "n2": "src-b"}
    assert lib.get_novel_sources([]) == {}
    assert lib.delete_novel_source("n1") is True
    assert lib.delete_novel_source("n1") is False
    assert lib.get_novel_source("n1") is None


# ── 写入安全 ────────────────────────────────────────

def test_atomic_write_leaves_backup(lib):
    lib.set_novel_source("n1", "src-a")
    lib.set_novel_source("n2", "src-b")

    bak = lib.BOOKS_PATH.with_name("books.yaml.bak")
    assert bak.exists()
    assert "n1" in bak.read_text(encoding="utf-8")      # 备份是上一次的内容


def test_write_failure_leaves_original_intact(lib):
    """目录不可写 → 抛 OSError，原文件不变（Review Focus 5）。"""
    if os.geteuid() == 0:
        pytest.skip("root 无视目录权限")

    lib.set_novel_source("n1", "src-a")
    before = lib.BOOKS_PATH.read_text(encoding="utf-8")

    lib.LIBRARY_DIR.chmod(0o500)
    try:
        with pytest.raises(OSError):
            lib.set_novel_source("n2", "src-b")
        assert lib.BOOKS_PATH.read_text(encoding="utf-8") == before
    finally:
        lib.LIBRARY_DIR.chmod(0o700)


def test_dump_has_header_and_field_order(lib):
    lib.add_novel_to_group("n1", "G")
    lib.add_favorite("n1")
    lib.set_novel_source("n1", "src-a")

    text = lib.BOOKS_PATH.read_text(encoding="utf-8")
    assert text.startswith("#")

    body = text[text.index("n1:"):]
    assert body.index("groups") < body.index("favorite") < body.index("source")
