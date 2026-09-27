"""构建期拦截：sources/ 下 source_name 撞名时 build_manifest 必须中止（非零退出）。"""
import json
from pathlib import Path

import pytest

from novelbase.utils import build_manifest as bm


def _source(root: Path, dirname: str, source_name: str) -> Path:
    d = root / dirname
    d.mkdir(parents=True, exist_ok=True)
    (d / "source.json").write_text(json.dumps({
        "source_name": source_name,
        "enabled": True,
        "default_config": {"search": {"mode": "requests"}},
    }, ensure_ascii=False), encoding="utf-8")
    (d / "search.py").write_text(
        "async def search(query, engine, **kwargs):\n    return ()\n", encoding="utf-8")
    return d


def test_build_aborts_on_duplicate(tmp_path, monkeypatch):
    src = tmp_path / "sources"
    _source(src, "demo_a", "demo-requests-default")
    _source(src, "demo_b", "demo-requests-default")
    out = tmp_path / "_manifest.py"
    monkeypatch.setattr(bm, "SRC", src)
    monkeypatch.setattr(bm, "OUT", out)

    with pytest.raises(SystemExit) as ei:
        bm.build()

    assert "重复" in str(ei.value)
    assert not out.exists(), "撞名时不得写出 half-baked 的 _manifest.py"


def test_build_generates_when_unique(tmp_path, monkeypatch):
    src = tmp_path / "sources"
    _source(src, "demo_a", "demo-requests-default")
    out = tmp_path / "_manifest.py"
    monkeypatch.setattr(bm, "SRC", src)
    monkeypatch.setattr(bm, "OUT", out)

    bm.build()

    text = out.read_text(encoding="utf-8")
    assert "'demo-requests-default': 'demo_a'" in text
    assert "SOURCES: dict[str, dict] = {" in text
