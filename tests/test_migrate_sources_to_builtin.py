"""scripts/migrate_sources_to_builtin.py：一次性迁移脚本的正确性。

迁移脚本没有第二次机会，所以幂等性与 dry-run 只读这两条必须钉住。
"""

import importlib.util
import sys
from pathlib import Path


def _load_script():
    p = Path(__file__).resolve().parents[1] / "scripts" / "migrate_sources_to_builtin.py"
    spec = importlib.util.spec_from_file_location("migrate_sources_to_builtin", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _make_source(root: Path, dirname: str) -> Path:
    d = root / dirname
    d.mkdir(parents=True)
    (d / "__init__.py").write_text("", encoding="utf-8")
    (d / "source.json").write_text('{"source_name": "x"}', encoding="utf-8")
    return d


def test_plan_moves_finds_top_level_sources_only(tmp_path):
    mod = _load_script()
    _make_source(tmp_path, "src_a")
    _make_source(tmp_path, "src_b")
    (tmp_path / "builtin").mkdir()
    _make_source(tmp_path / "builtin", "already")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "no_manifest").mkdir()
    moves = mod.plan_moves(tmp_path)
    assert sorted(src.name for src, _ in moves) == ["src_a", "src_b"]
    assert all(dst.parent == tmp_path / "builtin" for _, dst in moves)


def test_dry_run_does_not_touch_disk(tmp_path):
    mod = _load_script()
    _make_source(tmp_path, "src_a")
    mod.apply_moves(mod.plan_moves(tmp_path), dry_run=True)
    assert (tmp_path / "src_a").is_dir()
    assert not (tmp_path / "builtin" / "src_a").exists()


def test_apply_is_idempotent(tmp_path):
    mod = _load_script()
    _make_source(tmp_path, "src_a")
    mod.apply_moves(mod.plan_moves(tmp_path), dry_run=False)
    assert (tmp_path / "builtin" / "src_a" / "source.json").is_file()
    assert mod.plan_moves(tmp_path) == []


def test_apply_refuses_to_overwrite_existing_target(tmp_path):
    import pytest

    mod = _load_script()
    _make_source(tmp_path, "src_a")
    _make_source(tmp_path / "builtin", "src_a")
    with pytest.raises(FileExistsError):
        mod.apply_moves(mod.plan_moves(tmp_path), dry_run=False)
    assert (tmp_path / "src_a").is_dir()   # 源目录没有被删掉
