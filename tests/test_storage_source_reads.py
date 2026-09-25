"""来源读点：storage 列表与详情端点返回 novel_sources 里的 source_name。"""
import asyncio

import pytest

from novelbase.models.novel import Novel
from shared import user_data
from backend.routers import storage as storage_router


@pytest.fixture
def isolated_user_db(tmp_path, monkeypatch):
    monkeypatch.setattr(user_data, "DB_PATH", tmp_path / "user_data.db")
    monkeypatch.setattr(user_data, "GROUPS_YAML", tmp_path / "groups.yaml")
    return user_data


def _novel(novel_id: str) -> Novel:
    return Novel(title="t", url=f"https://x/{novel_id}", id=novel_id,
                 serial=1, author="a", description="d")


class FakeStore:
    def __init__(self, novels):
        self._novels = list(novels)

    def iter_metas(self, include_images=False):
        return iter(self._novels)

    def load_meta(self, novel_id):
        return next((n for n in self._novels if n.id == novel_id), None)


def test_get_meta_returns_source_name(monkeypatch, isolated_user_db):
    isolated_user_db.set_novel_source("n1", "fanqie-api-rain")
    monkeypatch.setattr(storage_router, "_get_storage", lambda: FakeStore([_novel("n1")]))
    meta = asyncio.run(storage_router.get_meta("n1"))
    assert meta.source_name == "fanqie-api-rain"


def test_get_meta_without_source_is_none(monkeypatch, isolated_user_db):
    monkeypatch.setattr(storage_router, "_get_storage", lambda: FakeStore([_novel("n9")]))
    assert asyncio.run(storage_router.get_meta("n9")).source_name is None


def test_list_novels_returns_source_names(monkeypatch, isolated_user_db):
    isolated_user_db.set_novel_source("n1", "fanqie-api-rain")
    isolated_user_db.set_novel_source("n2", "92xs-requests-default")
    store = FakeStore([_novel("n1"), _novel("n2"), _novel("n3")])
    monkeypatch.setattr(storage_router, "_get_storage", lambda: store)

    rows = asyncio.run(storage_router.list_novels())

    assert {r["id"]: r["source_name"] for r in rows} == {
        "n1": "fanqie-api-rain",
        "n2": "92xs-requests-default",
        "n3": None,
    }
