"""scripts/migrate_private_sources_out.py：把敏感源从仓库迁到用户源根。

与 migrate_sources_to_builtin.py 的分工：那个把官方源收进 `builtin/`（结构分离），
这个把不能公开的源搬出仓库（合规分离）。
"""

import importlib.util
import sys
from pathlib import Path


def _load_script():
    p = Path(__file__).resolve().parents[1] / "scripts" / "migrate_private_sources_out.py"
    spec = importlib.util.spec_from_file_location("migrate_private_sources_out", p)
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


def test_plan_moves_only_takes_named_sources(tmp_path):
    mod = _load_script()
    builtin = tmp_path / "builtin"
    for name in mod.PRIVATE_SOURCE_DIRS:
        _make_source(builtin, name)
    _make_source(builtin, "fanqie_requests_default")   # 可公开，不在名单
    moves = mod.plan_moves(builtin, tmp_path / "user")
    assert sorted(src.name for src, _ in moves) == sorted(mod.PRIVATE_SOURCE_DIRS)
    assert all(dst.parent == tmp_path / "user" for _, dst in moves)


def test_missing_named_source_is_skipped(tmp_path):
    mod = _load_script()
    builtin = tmp_path / "builtin"
    _make_source(builtin, mod.PRIVATE_SOURCE_DIRS[0])
    moves = mod.plan_moves(builtin, tmp_path / "user")
    assert [src.name for src, _ in moves] == [mod.PRIVATE_SOURCE_DIRS[0]]


def test_dry_run_does_not_touch_disk(tmp_path):
    mod = _load_script()
    builtin = tmp_path / "builtin"
    _make_source(builtin, mod.PRIVATE_SOURCE_DIRS[0])
    mod.apply_moves(mod.plan_moves(builtin, tmp_path / "user"), dry_run=True)
    assert (builtin / mod.PRIVATE_SOURCE_DIRS[0]).is_dir()
    assert not (tmp_path / "user" / mod.PRIVATE_SOURCE_DIRS[0]).exists()


def test_apply_is_idempotent(tmp_path):
    mod = _load_script()
    builtin, user = tmp_path / "builtin", tmp_path / "user"
    _make_source(builtin, mod.PRIVATE_SOURCE_DIRS[0])
    mod.apply_moves(mod.plan_moves(builtin, user), dry_run=False)
    assert (user / mod.PRIVATE_SOURCE_DIRS[0] / "source.json").is_file()
    assert mod.plan_moves(builtin, user) == []


def test_apply_refuses_to_overwrite_existing_target(tmp_path):
    import pytest

    mod = _load_script()
    builtin, user = tmp_path / "builtin", tmp_path / "user"
    name = mod.PRIVATE_SOURCE_DIRS[0]
    _make_source(builtin, name)
    _make_source(user, name)
    with pytest.raises(FileExistsError):
        mod.apply_moves(mod.plan_moves(builtin, user), dry_run=False)
    assert (builtin / name).is_dir()
