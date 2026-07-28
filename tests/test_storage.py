"""Storage 层测试：SQLiteStorage CRUD + 级联删除"""
from __future__ import annotations

import gc
import tempfile
from pathlib import Path

import pytest

from novelbase.core.storage import SQLiteStorage
from novelbase.core.options import StorageOptions
from novelbase.models.novel import Novel, Chapter, Chapters


# ── 辅助函数 ───────────────────────────────────────────────────

def _make_storage() -> SQLiteStorage:
    """创建临时目录中的 SQLite storage（目录隔离，互不干扰）"""
    tmp_dir = tempfile.mkdtemp(prefix="novel_test_")
    db_path = Path(tmp_dir) / "novels.db"
    return SQLiteStorage(StorageOptions(database_url=f"sqlite:///{db_path}"))


def _make_novel(novel_id: str = "n1") -> Novel:
    return Novel(
        id=novel_id, title="测试小说", url="https://example.com/novel",
        author="测试作者", serial=3, description="描述文本",
        tags=("奇幻", "测试"), count=100000,
    )


def _make_chapter(chapter_id: str, order: int, novel_id: str = "n1",
                  content: str | None = "正文内容") -> Chapter:
    return Chapter(
        id=chapter_id,
        url=f"https://example.com/novel/{chapter_id}",
        novel_id=novel_id, title=f"第{order}章",
        order=order, volume="第一卷",
        content=content, time=1000.0, count=len(content) if content else None,
    )


# ── 元数据 CRUD ────────────────────────────────────────────────

class TestMetaCRUD:
    def test_save_and_load(self):
        store = _make_storage()
        novel = _make_novel()
        store.save_meta(novel)
        loaded = store.load_meta("n1")
        assert loaded is not None
        assert loaded.id == "n1"
        assert loaded.title == "测试小说"
        assert loaded.author == "测试作者"
        assert loaded.serial == 3
        assert loaded.tags == ("奇幻", "测试")
        assert loaded.count == 100000

    def test_load_nonexistent(self):
        store = _make_storage()
        assert store.load_meta("no_such_id") is None

    def test_save_overwrite(self):
        store = _make_storage()
        novel = _make_novel()
        store.save_meta(novel)
        novel.title = "改名后的小说"
        novel.count = 200000
        store.save_meta(novel)
        loaded = store.load_meta("n1")
        assert loaded.title == "改名后的小说"
        assert loaded.count == 200000

    def test_iter_metas(self):
        store = _make_storage()
        for i in range(3):
            store.save_meta(_make_novel(novel_id=f"n{i}"))
        metas = list(store.iter_metas())
        assert len(metas) == 3
        ids = {m.id for m in metas}
        assert ids == {"n0", "n1", "n2"}


# ── 章节 CRUD ──────────────────────────────────────────────────

class TestChapterCRUD:
    def test_save_single_and_load(self):
        store = _make_storage()
        novel = _make_novel()
        store.save_meta(novel)
        ch = _make_chapter("ch1", order=1)
        store.save_chapter(novel, ch)
        loaded = store.load_chapter("n1", "ch1")
        assert loaded is not None
        assert loaded.id == "ch1"
        assert loaded.title == "第1章"
        assert loaded.content == "正文内容"
        assert loaded.order == 1

    def test_save_batch(self):
        store = _make_storage()
        novel = _make_novel()
        store.save_meta(novel)
        ch1 = _make_chapter("ch1", order=1)
        ch2 = _make_chapter("ch2", order=2)
        ch3 = _make_chapter("ch3", order=3)
        ids = store.save_chapter(novel, [ch1, ch2, ch3])
        assert ids == ["ch1", "ch2", "ch3"]

    def test_load_chapters_order(self):
        store = _make_storage()
        novel = _make_novel()
        store.save_meta(novel)
        store.save_chapter(novel, [
            _make_chapter("ch3", order=3),
            _make_chapter("ch1", order=1),
            _make_chapter("ch2", order=2),
        ])
        chapters = store.load_chapters("n1")
        orders = [ch.order for ch in chapters]
        assert orders == [1, 2, 3]

    def test_load_chapter_nonexistent(self):
        store = _make_storage()
        assert store.load_chapter("n1", "no_such") is None

    def test_save_overwrite_chapter(self):
        store = _make_storage()
        novel = _make_novel()
        store.save_meta(novel)
        ch = _make_chapter("ch1", order=1, content="旧内容")
        store.save_chapter(novel, ch)
        ch.content = "新内容"
        ch.count = 999
        store.save_chapter(novel, ch)
        loaded = store.load_chapter("n1", "ch1")
        assert loaded.content == "新内容"
        assert loaded.count == 999

    def test_chapter_without_content(self):
        """未下载章节 content=None 应正确存取"""
        store = _make_storage()
        novel = _make_novel()
        store.save_meta(novel)
        ch = _make_chapter("ch1", order=1, content=None)
        store.save_chapter(novel, ch)
        loaded = store.load_chapter("n1", "ch1")
        assert loaded.content is None
        assert loaded.count is None


# ── 删除 ───────────────────────────────────────────────────────

class TestDelete:
    def test_delete_novel_cascades_chapters(self):
        store = _make_storage()
        novel = _make_novel()
        store.save_meta(novel)
        store.save_chapter(novel, [
            _make_chapter("ch1", 1), _make_chapter("ch2", 2),
        ])
        gc.collect()  # Windows: 强制释放 SQLite WAL 文件句柄
        store.delete_novel("n1")
        assert store.load_meta("n1") is None
        assert store.load_chapter("n1", "ch1") is None
        assert store.load_chapter("n1", "ch2") is None

    def test_delete_nonexistent_no_error(self):
        store = _make_storage()
        store.delete_novel("no_such")  # 不应抛异常
