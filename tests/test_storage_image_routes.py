import asyncio
import hashlib

import httpx
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


def _chapter_store(imgs):
    class S(FakeStore):
        def load_illustrations(self, novel_id, owner_type, owner_id):
            if owner_type == "chapter":
                return imgs.get(owner_id, ())
            return ()
    return S({})


def test_image_length(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: _chapter_store({"ch1": (Illustration(raw_data=PNG), Illustration(raw_data=PNG))}))
    assert asyncio.run(storage_router.get_chapter_image_length("n1", "ch1")) == 2


def test_image_n_returns_bytes(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: _chapter_store({"ch1": (Illustration(raw_data=PNG), Illustration(raw_data=b"OTHER"))}))
    resp = asyncio.run(storage_router.get_chapter_image("n1", "ch1", 1))
    assert resp.body == b"OTHER"


def test_image_n_hash_is_string(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: _chapter_store({"ch1": (Illustration(raw_data=PNG),)}))
    got = asyncio.run(storage_router.get_chapter_image_hash("n1", "ch1", 0))
    assert isinstance(got, str) and got == hashlib.sha256(PNG).hexdigest()[:32]


def test_image_n_out_of_range_404(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: _chapter_store({"ch1": (Illustration(raw_data=PNG),)}))
    with pytest.raises(HTTPException) as e:
        asyncio.run(storage_router.get_chapter_image("n1", "ch1", 5))
    assert e.value.status_code == 404


def test_image_n_empty_raw_404(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: _chapter_store({"ch1": (Illustration(raw_data=None),)}))
    with pytest.raises(HTTPException) as e:
        asyncio.run(storage_router.get_chapter_image_hash("n1", "ch1", 0))
    assert e.value.status_code == 404


def test_images_returns_json_list(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: _chapter_store({"ch1": (Illustration(raw_data=PNG, alt="a"),)}))
    rows = asyncio.run(storage_router.get_chapter_images("n1", "ch1"))
    assert len(rows) == 1 and rows[0]["alt"] == "a"


def test_images_hash_returns_list(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: _chapter_store({"ch1": (Illustration(raw_data=PNG), Illustration(raw_data=b"B"))}))
    got = asyncio.run(storage_router.get_chapter_images_hash("n1", "ch1"))
    assert got == [hashlib.sha256(PNG).hexdigest()[:32], hashlib.sha256(b"B").hexdigest()[:32]]


def test_image_length_route_before_image_n():
    paths = [getattr(r, "path", "") for r in storage_router.router.routes]
    assert paths.index("/api/v2/storage/novel/{novel_id}/chapter/{chapter_id}/image/length") < \
           paths.index("/api/v2/storage/novel/{novel_id}/chapter/{chapter_id}/image/{n}")


def test_image_n_negative_404(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: _chapter_store({"ch1": (Illustration(raw_data=PNG),)}))
    with pytest.raises(HTTPException) as e:
        asyncio.run(storage_router.get_chapter_image("n1", "ch1", -1))
    assert e.value.status_code == 404


def test_cover_image_empty_raw_404(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: FakeStore({"n1": Illustration(raw_data=None)}))
    with pytest.raises(HTTPException) as e:
        asyncio.run(storage_router.get_cover_image("n1"))
    assert e.value.status_code == 404


# ── HTTP 层：V2ResponseMiddleware 包装契约 ──────────────────────

def _get(path: str):
    from backend.main import app

    async def _go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            return await c.get(path)
    return asyncio.run(_go())


def test_http_binary_not_wrapped(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: FakeStore({"n1": Illustration(raw_data=PNG)}))
    resp = _get("/api/v2/storage/novel/n1/meta/image")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")
    assert resp.content == PNG


def test_http_hash_data_is_string(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: FakeStore({"n1": Illustration(raw_data=PNG)}))
    body = _get("/api/v2/storage/novel/n1/meta/image/hash").json()
    assert body["ok"] is True
    assert isinstance(body["data"], str)
    assert body["data"] == hashlib.sha256(PNG).hexdigest()[:32]


def test_http_length_data_is_int(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: _chapter_store({"ch1": (Illustration(raw_data=PNG), Illustration(raw_data=PNG))}))
    body = _get("/api/v2/storage/novel/n1/chapter/ch1/image/length").json()
    assert isinstance(body["data"], int)
    assert body["data"] == 2


def test_http_images_hash_data_is_list(monkeypatch):
    monkeypatch.setattr(storage_router, "_get_storage",
        lambda: _chapter_store({"ch1": (Illustration(raw_data=PNG), Illustration(raw_data=b"B"))}))
    body = _get("/api/v2/storage/novel/n1/chapter/ch1/images/hash").json()
    assert body["data"] == [hashlib.sha256(PNG).hexdigest()[:32], hashlib.sha256(b"B").hexdigest()[:32]]
