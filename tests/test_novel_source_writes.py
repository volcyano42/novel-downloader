"""写入点覆盖：删书端点清理来源、CLI 下载流程写入来源。"""
import asyncio

import pytest
from fastapi import HTTPException

from cli import core as cli_core
from novelbase.models.novel import Chapter, Chapters, Novel
from shared import user_data
from backend.routers import storage as storage_router


@pytest.fixture
def isolated_user_db(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")
    return user_data


def test_delete_novel_cleans_novel_sources(monkeypatch, isolated_user_db):
    isolated_user_db.set_novel_source("n1", "fanqie-api-rain")

    class FakeStore:
        def load_meta(self, novel_id):
            return object() if novel_id == "n1" else None

        def delete_novel(self, novel_id):
            return None

    monkeypatch.setattr(storage_router, "_get_storage", lambda: FakeStore())
    asyncio.run(storage_router.delete_novel("n1"))
    assert isolated_user_db.get_novel_source("n1") is None


def test_delete_unknown_novel_404(monkeypatch, isolated_user_db):
    class FakeStore:
        def load_meta(self, novel_id):
            return None

    monkeypatch.setattr(storage_router, "_get_storage", lambda: FakeStore())
    with pytest.raises(HTTPException) as ei:
        asyncio.run(storage_router.delete_novel("nope"))
    assert ei.value.status_code == 404


def test_cli_download_writes_novel_source(monkeypatch, isolated_user_db):
    """CLI 下载流程走到写入点即应落库。

    让 storage.load_chapters 返回「章节已存在」，从而在写入点之后的
    `if not to_download: return` 处提前返回 —— 无需进入真实下载循环。
    """
    novel = Novel(title="t", url="https://x/n1", id="n1", serial=1,
                  author="a", description="d")
    ch = Chapter(id="c1", url="https://x/n1/c1", novel_id="n1",
                 title="第一章", order=1)

    async def fake_resolve_meta(url, source_name, engines, **kw):
        return novel

    async def fake_resolve_chapter_list(url, source_name, engines, **kw):
        return Chapters([ch])

    class FakeStorage:
        def save_meta(self, n):
            return None

        def load_chapters(self, novel_id):
            return [ch]                      # 章节已在 → to_download 为空 → 提前返回

    monkeypatch.setattr(cli_core, "resolve_meta", fake_resolve_meta)
    monkeypatch.setattr(cli_core, "resolve_chapter_list", fake_resolve_chapter_list)
    monkeypatch.setattr(cli_core, "_get_storage", lambda: FakeStorage())
    monkeypatch.setattr(cli_core, "add_novel_to_group", lambda nid, grp: None)

    asyncio.run(cli_core._do_download_inner(
        "fanqie-api-rain", "https://x/n1", "default", {}))

    assert isolated_user_db.get_novel_source("n1") == "fanqie-api-rain"


def test_cli_update_reads_source_from_user_data(monkeypatch, isolated_user_db):
    """cli/core.do_update 的读点改查 user_data（字段已从 Novel 剥离）。

    这是「更新已有小说」取书源的唯一来源；不改造则该功能会整体跳过。
    """
    novel = Novel(title="t", url="https://x/n1", id="n1", serial=1,
                  author="a", description="d")
    isolated_user_db.set_novel_source("n1", "fanqie-api-rain")
    seen = {}

    class FakeStorage:
        def iter_metas(self):
            return iter([novel])

    async def fake_resolve_chapter_list(url, source_name, engines, **kw):
        return Chapters([])              # 空列表 → 走「无法获取远程章节」分支即可

    def fake_make_engines(source_name, **kw):
        seen["source"] = source_name
        return {}

    monkeypatch.setattr(cli_core, "_get_storage", lambda: FakeStorage())
    monkeypatch.setattr(cli_core, "load_groups", lambda: {})
    monkeypatch.setattr(cli_core, "_make_engines", fake_make_engines)
    monkeypatch.setattr(cli_core, "resolve_chapter_list", fake_resolve_chapter_list)

    asyncio.run(cli_core.do_update({}, max_workers=1))
    assert seen.get("source") == "fanqie-api-rain"
