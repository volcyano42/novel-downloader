"""模型层测试：Illustration / Chapter / Chapters / Novel / SearchResult"""
from __future__ import annotations

import pytest

from novelbase.models.novel import Illustration, Chapter, Chapters, Novel, SearchResult

# ═══════════════════════════════════════════════════════════════
# Illustration
# ═══════════════════════════════════════════════════════════════

class TestIllustration:
    def test_create(self, img_bytes: bytes):
        img = Illustration(raw_data=img_bytes, alt="图", insert=5, url="http://x.com/a.jpg")
        assert img.raw_data == img_bytes
        assert img.alt == "图"
        assert img.insert == 5
        assert img.url == "http://x.com/a.jpg"

    def test_defaults(self, img_bytes: bytes):
        img = Illustration(raw_data=img_bytes)
        assert img.alt is None
        assert img.insert is None
        assert img.url is None

    def test_hash_by_raw_data(self, img_bytes: bytes):
        a = Illustration(raw_data=img_bytes, alt="x")
        b = Illustration(raw_data=img_bytes, alt="y")
        assert hash(a) == hash(b)

    def test_to_json_roundtrip(self, img_bytes: bytes):
        original = Illustration(raw_data=img_bytes, alt="封面", insert=0, url="http://x.com")
        data = original.to_json()
        assert isinstance(data["raw_data"], str)  # base64 编码
        restored = Illustration.loads(**data)
        assert restored.raw_data == img_bytes
        assert restored.alt == "封面"
        assert restored.insert == 0
        assert restored.url == "http://x.com"

    def test_loads_from_bytes(self, img_bytes: bytes):
        img = Illustration.loads(raw_data=img_bytes, alt="直接字节")
        assert img.raw_data == img_bytes

    def test_loads_from_base64(self, img_bytes: bytes):
        import base64
        b64 = base64.b64encode(img_bytes).decode()
        img = Illustration.loads(raw_data=b64, alt="来自base64")
        assert img.raw_data == img_bytes

    def test_loads_extra_kwargs(self, img_bytes: bytes):
        img = Illustration.loads(raw_data=img_bytes, extra_field="hello")
        assert img.extra_field == "hello"  # noqa

# ═══════════════════════════════════════════════════════════════
# Chapter
# ═══════════════════════════════════════════════════════════════

class TestChapter:
    def test_create(self, chapter_1: Chapter):
        assert chapter_1.id == "ch1"
        assert chapter_1.title == "第一章 开端"
        assert chapter_1.order == 1
        assert chapter_1.content == "这是第一章的内容。"

    def test_eq_by_id_only(self):
        a = Chapter(id="x", url="a", novel_id="i", title="t", order=1, content="aaa")
        b = Chapter(id="x", url="b", novel_id="i", title="t", order=2, content="bbb")
        assert a == b

    def test_ne_different_id(self):
        a = Chapter(id="x", url="a", novel_id="i", title="t", order=1)
        b = Chapter(id="y", url="a", novel_id="i", title="t", order=1)
        assert a != b

    def test_eq_with_non_chapter(self):
        c = Chapter(id="x", url="a", novel_id="i", title="t", order=1)
        assert c.__eq__("not a chapter") is NotImplemented

    def test_hash_by_id(self):
        a = Chapter(id="same", url="a", novel_id="i", title="t", order=1)
        b = Chapter(id="same", url="b", novel_id="i", title="t", order=2)
        assert hash(a) == hash(b)

    def test_loads_full(self):
        ch = Chapter.loads(
            id="ch99", url="http://x.com/99", novel_id="http://x.com",
            title="第99章", order=99, volume="终卷",
            content="终章内容", time=999.0, count=5000,
             images=[],
        )
        assert ch.id == "ch99"
        assert ch.volume == "终卷"
        assert ch.content == "终章内容"

    def test_loads_with_images(self, img_bytes: bytes):
        import base64
        b64 = base64.b64encode(img_bytes).decode()
        ch = Chapter.loads(
            id="ch_img", url="u", novel_id="i", title="t", order=1,
            images=[{"raw_data": b64, "alt": "插图1"}],
        )
        assert len(ch.images) == 1
        assert ch.images[0].raw_data == img_bytes

    def test_loads_extra_kwargs(self):
        ch = Chapter.loads(id="x", url="u", novel_id="i", title="t", order=1, custom="val")
        assert ch.custom == "val"  # noqa

    def test_images_default_empty_tuple(self):
        ch = Chapter(id="x", url="u", novel_id="i", title="t", order=1)
        assert ch.images == ()

# ═══════════════════════════════════════════════════════════════
# Chapters (Sequence[Chapter])
# ═══════════════════════════════════════════════════════════════

class TestChapters:
    def test_empty(self):
        c = Chapters()
        assert len(c) == 0
        assert list(c) == []

    def test_empty_from_none(self):
        c = Chapters(None)
        assert len(c) == 0

    def test_single_chapter(self, chapter_1: Chapter):
        c = Chapters(chapter_1)
        assert len(c) == 1
        assert c[0] == chapter_1

    def test_sort_by_order(self, chapter_1: Chapter, chapter_2: Chapter):
        """确保构造时按 order 排序"""
        c = Chapters([chapter_2, chapter_1])  # 逆序传入
        assert c[0].order == 1
        assert c[1].order == 2

    def test_sequence_protocol(self, chapters: Chapters):
        assert len(chapters) == 3
        assert chapters[0].id == "ch1"
        assert chapters[-1].id == "ch3"

    def test_iteration(self, chapters: Chapters):
        ids = [ch.id for ch in chapters]
        assert ids == ["ch1", "ch2", "ch3"]

    def test_contains_chapter(self, chapters: Chapters, chapter_1: Chapter):
        assert chapter_1 in chapters

    def test_contains_non_chapter(self, chapters: Chapters):
        assert "ch1" not in chapters  # str, not Chapter

    def test_repr(self, chapters: Chapters):
        assert repr(chapters) == "Chapters(3 items)"

    def test_eq(self, chapters: Chapters, chapter_1, chapter_2, chapter_3_incomplete):
        other = Chapters([chapter_1, chapter_2, chapter_3_incomplete])
        assert chapters == other

    def test_get_chapter_by_id(self, chapters: Chapters):
        ch = chapters.get_chapter_by_id("ch2")
        assert ch is not None
        assert ch.title == "第二章 发展"

    def test_get_chapter_by_id_missing(self, chapters: Chapters):
        assert chapters.get_chapter_by_id("ghost") is None

    def test_get_chapter_by_url(self, chapters: Chapters):
        ch = chapters.get_chapter_by_url("https://example.com/novel/ch3")
        assert ch is not None
        assert ch.id == "ch3"

    def test_get_chapter_by_url_missing(self, chapters: Chapters):
        assert chapters.get_chapter_by_url("https://x.com/nope") is None

    def test_get_chapter_by_order(self, chapters: Chapters):
        ch = chapters.get_chapter_by_order(2)
        assert ch is not None
        assert ch.id == "ch2"

    def test_get_chapter_by_order_missing(self, chapters: Chapters):
        assert chapters.get_chapter_by_order(999) is None

    def test_get_incompleted_chapters(self, chapters: Chapters):
        inc = [ch for ch in chapters if ch.content is None]
        assert len(inc) == 1
        assert inc[0].id == "ch3"

    def test_get_incompleted_chapters_all_complete(self, chapter_1, chapter_2):
        c = Chapters([chapter_1, chapter_2])
        inc = [ch for ch in c if ch.content is None]
        assert len(inc) == 0

    def test_merge_with_chapter(self, chapters: Chapters):
        new_ch = Chapter(id="ch4", url="u4", novel_id="i", title="第四章", order=4)
        merged = chapters.merge(new_ch)
        assert len(merged) == 4
        assert merged.get_chapter_by_id("ch4") is not None

    def test_merge_overwrite_by_id(self, chapters: Chapters):
        updated = Chapter(id="ch1", url="u1_new", novel_id="i", title="第一章 改", order=1, content="新内容")
        merged = chapters.merge(updated)
        assert merged.get_chapter_by_id("ch1").title == "第一章 改"
        assert len(merged) == 3  # 不增加数量

    def test_merge_preserves_original(self, chapters: Chapters):
        """merge 返回新对象，原对象不变"""
        new_ch = Chapter(id="ch4", url="u4", novel_id="i", title="第四章", order=4)
        merged = chapters.merge(new_ch)
        assert len(chapters) == 3
        assert len(merged) == 4

    def test_merge_keeps_new_images_when_both_have_same_count(self, illustration):
        """新旧图片数相同时保留新的"""
        old_img = illustration
        new_img = Illustration(raw_data=b"\x89PNG\r\n\x1a\n" + b"\x01" * 20,
                               alt="新图", insert=0, url="http://new.com/img.png")
        old = Chapter(id="ch1", url="u1", novel_id="n1", title="第一章", order=1,
                      images=(old_img,))
        new = Chapter(id="ch1", url="u1", novel_id="n1", title="第一章", order=1,
                      images=(new_img,))
        merged = Chapters([old]).merge(new)
        result = merged.get_chapter_by_id("ch1")
        assert result.images[0] is new_img

    def test_merge_keeps_new_images_when_both_have_images(self, illustration):
        """新旧都有 images → 保留新的（无论数量是否相同）"""
        new_img = Illustration(raw_data=b"\x89PNG\r\n\x1a\n" + b"\x02" * 20,
                               alt="新图", insert=0, url="http://new.com/img.png")
        old = Chapter(id="ch1", url="u1", novel_id="n1", title="第一章", order=1,
                      images=(illustration,))
        new = Chapter(id="ch1", url="u1", novel_id="n1", title="第一章", order=1,
                      images=(new_img,))
        merged = Chapters([old]).merge(new)
        result = merged.get_chapter_by_id("ch1")
        assert result.images[0] is new_img

    def test_total_property(self, chapters: Chapters):
        assert chapters.total == 3

    def test_chapters_property_returns_tuple(self, chapters: Chapters):
        assert isinstance(chapters._chapters, tuple)

# ═══════════════════════════════════════════════════════════════
# Novel
# ═══════════════════════════════════════════════════════════════

class TestNovel:
    def test_create(self, novel: Novel):
        assert novel.title == "测试小说"
        assert novel.author == "测试作者"
        assert novel.id == "novel123"
        assert novel.serial == 3
        assert len(novel.chapters) == 3

    def test_loads(self):
        n = Novel.loads(
            title="加载测试", url="http://x.com/n", id="n1", serial=2,
            author="作者", description="简介",
            tags=["tag1"], count=500,
        )
        assert n.title == "加载测试"
        assert n.tags == ["tag1"]

    def test_loads_with_cover(self, img_bytes: bytes):
        import base64
        b64 = base64.b64encode(img_bytes).decode()
        n = Novel.loads(
            title="有封面", url="u", id="n2", serial=1,
            author="a", description="d",
            tags=[], count=0,
            cover={"raw_data": b64, "alt": "封面图"},
        )
        assert n.cover is not None
        assert n.cover.raw_data == img_bytes

    def test_loads_with_chapters(self):
        n = Novel.loads(
            title="有章节", url="u", id="n3", serial=2,
            author="a", description="d",
            tags=[], count=0,
            chapters=[
                {"id": "c1", "url": "u1", "novel_id": "u", "title": "章1", "order": 1},
                {"id": "c2", "url": "u2", "novel_id": "u", "title": "章2", "order": 2},
            ],
        )
        assert len(n.chapters) == 2

    def test_loads_cover_none(self):
        n = Novel.loads(
            title="无封面", url="u", id="n4", serial=1,
            author="a", description="d",
            tags=[], count=0, cover=None,
        )
        assert n.cover is None

    def test_update_chapter_add(self, novel: Novel):
        new = Chapter(id="ch_new", url="u", novel_id="i", title="新章", order=99)
        novel.update_chapter(new)
        assert len(novel.chapters) == 4
        assert novel.chapters.get_chapter_by_id("ch_new") is not None

    def test_update_chapter_overwrite(self, novel: Novel):
        updated = Chapter(id="ch1", url="u", novel_id="i", title="第一章 已修改", order=1)
        novel.update_chapter(updated)
        assert novel.chapters.get_chapter_by_id("ch1").title == "第一章 已修改"
        assert len(novel.chapters) == 3  # 数量不变

    def test_update_chapter_batch(self, novel: Novel):
        batch = [
            Chapter(id="c_a", url="u", novel_id="i", title="A", order=10),
            Chapter(id="c_b", url="u", novel_id="i", title="B", order=11),
        ]
        novel.update_chapter(batch)
        assert len(novel.chapters) == 5

    # ── serial 兜底：serial=0 时跟随本地章节数 ──

    def test_serial_zero_with_chapters_defaults_to_length(self):
        n = Novel(title="t", url="u", id="n", serial=0,
                  author="a", description="d",
                  chapters=Chapters([
                      Chapter(id="c1", url="u1", novel_id="n", title="章1", order=1),
                      Chapter(id="c2", url="u2", novel_id="n", title="章2", order=2),
                  ]))
        assert n.serial == 2

    def test_serial_zero_without_chapters_stays_zero(self):
        n = Novel(title="t", url="u", id="n", serial=0, author="a", description="d")
        assert n.serial == 0

    def test_serial_nonzero_not_overridden(self):
        n = Novel(title="t", url="u", id="n", serial=12, author="a", description="d",
                  chapters=Chapters([
                      Chapter(id="c1", url="u1", novel_id="n", title="章1", order=1),
                  ]))
        assert n.serial == 12  # 源站总章节数优先，不被本地章节数覆盖

    def test_update_chapter_syncs_serial_when_zero(self):
        n = Novel(title="t", url="u", id="n", serial=0, author="a", description="d")
        assert n.serial == 0
        n.update_chapter(Chapter(id="c1", url="u1", novel_id="n", title="章1", order=1))
        assert n.serial == 1
        n.update_chapter(Chapter(id="c2", url="u2", novel_id="n", title="章2", order=2))
        assert n.serial == 2

    def test_update_chapter_keeps_nonzero_serial(self):
        n = Novel(title="t", url="u", id="n", serial=10, author="a", description="d")
        n.update_chapter(Chapter(id="c1", url="u1", novel_id="n", title="章1", order=1))
        assert n.serial == 10  # 显式 serial 不被 update_chapter 改动

# ═══════════════════════════════════════════════════════════════
# SearchResult
# ═══════════════════════════════════════════════════════════════

class TestSearchResult:
    def test_create(self):
        r = SearchResult(title="结果1", author="作者1", url="http://x.com/1", description="描述")
        assert r.title == "结果1"
        assert r.url == "http://x.com/1"

    def test_defaults(self):
        r = SearchResult(title="t", author="a")
        assert r.url is None
        assert r.description is None
