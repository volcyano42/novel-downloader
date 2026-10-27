import asyncio
import hashlib

import pytest
from fastapi import HTTPException

from novelbase.models.novel import Illustration
from backend.routers import storage as storage_router

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8


class FakeStore:
    def __init__(self, covers=None):
        self._covers = covers or {}

    def load_illustrations(self, novel_id, owner_type, owner_id):
        if owner_type == "novel":
            img = self._covers.get(novel_id)
            return (img,) if img else ()
        return ()


def test_cover_image_returns_raw_bytes(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: FakeStore({"n1": Illustration(raw_data=PNG)}))
    resp = asyncio.run(storage_router.get_cover_image("n1"))
    assert resp.body == PNG and resp.media_type == "image/png"


def test_cover_image_hash_returns_32hex(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: FakeStore({"n1": Illustration(raw_data=PNG)}))
    assert asyncio.run(storage_router.get_cover_image_hash("n1")) == \
        hashlib.sha256(PNG).hexdigest()[:32]


def test_cover_image_missing_404(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage", lambda: FakeStore({}))
    with pytest.raises(HTTPException) as e:
        asyncio.run(storage_router.get_cover_image("n1"))
    assert e.value.status_code == 404
