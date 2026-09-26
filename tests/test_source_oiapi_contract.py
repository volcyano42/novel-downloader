"""fanqie-api-oiapi 源契约测试：用 mock 的 engine.async_fetch_json 钉住实测响应结构。

契约实测 2026-09-26（https://oiapi.net/api/FqRead，POST form + key/type=json）：
- novel_info   ：method=ids       → data=dict{thumb,id,title,author,serial,word_number,docs}
- chapter_list ：method=chapters  → data=分卷嵌套 list[list[dict]]（真实）；兼容扁平 list[dict]
                   章节字段 {chapter_id,title,index,volume,volume_name,time,pay}
- chapter_content：method=chapter → data=list（首项含 content/word_number/chapter_title…）；
                    越界 code=-3 message="请检测章节选择是否正确"

这些用例在旧实现下会红（旧实现用 method=detail、按分卷嵌套解析、在 dict 上取值）。
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from novelbase.core.exceptions import AntiCrawlError, ChapterNotFoundError, NovelNotFoundError
from novelbase.models.novel import Chapter

_BOOK_ID = "7406592861791063064"
_NOVEL_URL = f"https://fanqienovel.com/page/{_BOOK_ID}"

# 实测 novel_info（method=ids）响应
_IDS_RESPONSE = {
    "code": 1,
    "data": {
        "thumb": "http://img.oiapi.example/cover.jpg",
        "id": _BOOK_ID,
        "title": "测试书名",
        "author": "测试作者",
        "serial": 12,
        "word_number": "345678",
        "read_count": "12345",
        "docs": "这是一段简介。",
    },
}

# 实测 chapter_list（method=chapters）响应：**分卷嵌套** list[list[dict]]（真实形态）
_CHAPTERS_VOLUME_RESPONSE = {
    "code": 1,
    "data": [
        [
            {"chapter_id": 7000000000000000001, "title": "第一章 开端",
             "index": 1, "volume": 1, "volume_name": "第一卷", "time": 1600000001.0, "pay": False},
            {"chapter_id": 7000000000000000002, "title": "第二章 发展",
             "index": 2, "volume": 1, "volume_name": "第一卷", "time": 1600000002.0, "pay": False},
        ],
        [
            {"chapter_id": 7000000000000000003, "title": "第三章 转折",
             "index": 3, "volume": 2, "volume_name": "第二卷", "time": 1600000003.0, "pay": True},
        ],
    ],
}

# 兼容形态：扁平 list[dict]
_CHAPTERS_RESPONSE = {
    "code": 1,
    "data": [
        {"chapter_id": 7000000000000000001, "title": "第一章 开端",
         "index": 1, "volume": 1, "volume_name": "第一卷", "time": 1600000001.0, "pay": 0},
        {"chapter_id": 7000000000000000002, "title": "第二章 发展",
         "index": 2, "volume": 1, "volume_name": "第一卷", "time": 1600000002.0, "pay": 0},
        {"chapter_id": 7000000000000000003, "title": "第三章 转折",
         "index": 3, "volume": 2, "volume_name": "第二卷", "time": 1600000003.0, "pay": 1},
    ],
}

# 实测 chapter_content（method=chapter）响应：data 是 list
_CHAPTER_CONTENT_RESPONSE = {
    "code": 1,
    "data": [
        {
            "chapter_id": 7000000000000000001,
            "chapter_title": "第一章 开端",
            "volume_name": "第一卷",
            "word_number": 321,
            "content": "第一章 开端\n\n这是第一章的正文内容。",
        }
    ],
}

_CHAPTER_OVERFLOW_RESPONSE = {"code": -3, "message": "请检测章节选择是否正确"}
_CHAPTER_FREQ_RESPONSE = {
    "code": -5,
    "message": "实例化失败：Trying to access array offset on value of type bool line 197 in api.php",
}


def _engine(json_response) -> MagicMock:
    engine = MagicMock()
    engine.options.key = "test-key"
    engine.async_fetch_json = AsyncMock(return_value=json_response)
    engine.async_fetch_images = AsyncMock(return_value=[b"cover-bytes"])
    return engine


def _chapter() -> Chapter:
    return Chapter(
        id="7000000000000000001",
        url="https://fanqienovel.com/reader/7000000000000000001",
        novel_id=f"fanqie_{_BOOK_ID}",
        title="第一章 开端",
        order=1,
    )


class TestOiApiNovelInfo:
    def test_maps_ids_response(self):
        from novelbase.sources.fanqie_api_oiapi import novel_info as mod
        engine = _engine(_IDS_RESPONSE)

        novel = asyncio.run(mod.novel_info(_NOVEL_URL, engine))

        assert novel.title == "测试书名"
        assert novel.author == "测试作者"
        assert novel.count == 345678              # word_number
        assert novel.description == "这是一段简介。"
        assert novel.serial == 12                 # 直接取自 ids 的 serial
        assert novel.id == f"fanqie_{_BOOK_ID}"   # 前缀不可改
        assert novel.url == _NOVEL_URL

    def test_cover_from_thumb_and_downloaded_via_engine(self):
        from novelbase.sources.fanqie_api_oiapi import novel_info as mod
        engine = _engine(_IDS_RESPONSE)

        novel = asyncio.run(mod.novel_info(_NOVEL_URL, engine))

        engine.async_fetch_images.assert_awaited_once_with(
            ["http://img.oiapi.example/cover.jpg"]
        )
        assert novel.cover is not None
        assert novel.cover.url == "http://img.oiapi.example/cover.jpg"
        assert novel.cover.raw_data == b"cover-bytes"

    def test_uses_ids_method_and_does_not_fetch_chapters(self):
        """method 必须是 ids，且不得再发起第二次 chapters 请求。"""
        from novelbase.sources.fanqie_api_oiapi import novel_info as mod
        engine = _engine(_IDS_RESPONSE)

        asyncio.run(mod.novel_info(_NOVEL_URL, engine))

        engine.async_fetch_json.assert_awaited_once()  # 只请求一次
        post_data = engine.async_fetch_json.await_args.kwargs["post_data"]
        assert post_data["method"] == "ids"
        assert post_data["type"] == "json"

    def test_raises_when_code_not_one(self):
        from novelbase.sources.fanqie_api_oiapi import novel_info as mod
        engine = _engine({"code": -5, "message": "default method: search, ids, chapter"})

        with pytest.raises(NovelNotFoundError):
            asyncio.run(mod.novel_info(_NOVEL_URL, engine))


class TestOiApiChapterList:
    def test_parses_volume_nested_list(self):
        """真实响应形态：data 为分卷嵌套 list[list[dict]]。"""
        from novelbase.sources.fanqie_api_oiapi import chapter_list as mod
        engine = _engine(_CHAPTERS_VOLUME_RESPONSE)

        chapters = asyncio.run(mod.chapter_list(_NOVEL_URL, engine))

        assert len(chapters) == 3
        assert [c.order for c in chapters] == [1, 2, 3]
        assert chapters[2].volume == "第二卷"
        assert chapters[0].url == "https://fanqienovel.com/reader/7000000000000000001"

    def test_parses_flat_list(self):
        """兼容形态：data 为扁平 list[dict]。"""
        from novelbase.sources.fanqie_api_oiapi import chapter_list as mod
        engine = _engine(_CHAPTERS_RESPONSE)

        chapters = asyncio.run(mod.chapter_list(_NOVEL_URL, engine))

        assert len(chapters) == 3
        first = chapters[0]
        assert first.order == 1
        assert first.title == "第一章 开端"
        assert first.volume == "第一卷"
        assert first.id == "7000000000000000001"
        assert first.url == "https://fanqienovel.com/reader/7000000000000000001"
        assert first.novel_id == _BOOK_ID
        assert first.time == 1600000001.0
        # 扁平列表按 order 排序
        assert [c.order for c in chapters] == [1, 2, 3]
        assert chapters[2].volume == "第二卷"

    def test_uses_chapters_method(self):
        from novelbase.sources.fanqie_api_oiapi import chapter_list as mod
        engine = _engine(_CHAPTERS_RESPONSE)

        asyncio.run(mod.chapter_list(_NOVEL_URL, engine))

        post_data = engine.async_fetch_json.await_args.kwargs["post_data"]
        assert post_data["method"] == "chapters"

    def test_empty_data_raises(self):
        from novelbase.sources.fanqie_api_oiapi import chapter_list as mod
        engine = _engine({"code": 1, "data": []})

        with pytest.raises(ChapterNotFoundError):
            asyncio.run(mod.chapter_list(_NOVEL_URL, engine))


class TestOiApiChapterContent:
    def test_extracts_content_and_word_count_from_list(self):
        from novelbase.sources.fanqie_api_oiapi import chapter_content as mod
        engine = _engine(_CHAPTER_CONTENT_RESPONSE)

        chapter = asyncio.run(mod.chapter_content(_chapter(), engine))

        assert chapter.content == "这是第一章的正文内容。"   # 去掉了标题前缀
        assert chapter.count == 321

    def test_uses_chapter_method_with_order(self):
        from novelbase.sources.fanqie_api_oiapi import chapter_content as mod
        engine = _engine(_CHAPTER_CONTENT_RESPONSE)

        asyncio.run(mod.chapter_content(_chapter(), engine))

        post_data = engine.async_fetch_json.await_args.kwargs["post_data"]
        assert post_data["method"] == "chapter"
        assert post_data["chapter"] == "1"

    def test_overflow_message_raises_chapter_not_found(self):
        from novelbase.sources.fanqie_api_oiapi import chapter_content as mod
        engine = _engine(_CHAPTER_OVERFLOW_RESPONSE)

        with pytest.raises(ChapterNotFoundError):
            asyncio.run(mod.chapter_content(_chapter(), engine))

    def test_frequency_message_raises_anti_crawl(self):
        from novelbase.sources.fanqie_api_oiapi import chapter_content as mod
        engine = _engine(_CHAPTER_FREQ_RESPONSE)

        with pytest.raises(AntiCrawlError):
            asyncio.run(mod.chapter_content(_chapter(), engine))
