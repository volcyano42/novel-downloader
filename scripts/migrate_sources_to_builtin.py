#!/usr/bin/env python
"""把 `novelbase/sources/` 下的官方书源目录迁入 `novelbase/sources/builtin/`。

一次性脚本（2026-10-26「书源与 core 结构分离」）。迁移后 `novelbase/sources/`
只保留 core 机制（`contracts.py` / `manifest.py`），官方源作为「随包发行的数据」
下沉到 `builtin/`，与用户源根走同一条加载路径。

默认 dry-run，只打印计划；`--apply` 才动盘。

用法::

    python scripts/migrate_sources_to_builtin.py            # 只看计划
    python scripts/migrate_sources_to_builtin.py --apply    # 执行迁移

迁移完成后记得同步：

- `pyproject.toml` 的 `[tool.setuptools.package-data]` 键
- `novelbase/utils/build_manifest.py` 与 `tests/check_imports.py` 的扫描根
- `pyproject.toml` 的 `[tool.novel-downloader.migration] exclude` 与 `PUBLIC_MANIFEST.md`
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES_DIR = REPO_ROOT / "novelbase" / "sources"
BUILTIN_NAME = "builtin"
MANIFEST_NAME = "source.json"


def plan_moves(sources_dir: Path) -> list[tuple[Path, Path]]:
    """列出待迁移的 `(源目录, 目标目录)`。

    只认 `sources_dir` 的**直接子目录**，且该子目录含 `source.json`；
    跳过 `builtin/` 自身、`_`/`__pycache__` 一类下划线开头的目录、以及非目录项。
    """
    sources_dir = Path(sources_dir)
    dest_root = sources_dir / BUILTIN_NAME
    moves: list[tuple[Path, Path]] = []
    for entry in sorted(sources_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("_"):
            continue
        if entry.name == BUILTIN_NAME:
            continue
        if not (entry / MANIFEST_NAME).is_file():
            continue
        moves.append((entry, dest_root / entry.name))
    return moves


def _drop_pycache(root: Path) -> None:
    """删掉迁移后的字节码缓存（路径变了，旧缓存只会误导）。"""
    for cache in root.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def apply_moves(
    moves: list[tuple[Path, Path]], *, dry_run: bool = True
) -> list[str]:
    """执行迁移，返回 `源 -> 目标` 的可读行。

    **先全量校验再动手**：任何一个目标已存在就整体放弃（`FileExistsError`），
    绝不半途而废留下「一半迁了、一半没迁」的中间态。
    """
    conflicts = [dst for _, dst in moves if dst.exists()]
    if conflicts:
        listed = "\n".join(f"  {c}" for c in conflicts)
        raise FileExistsError(
            f"目标目录已存在，放弃迁移（未移动任何文件）：\n{listed}"
        )

    lines: list[str] = []
    for src, dst in moves:
        lines.append(f"{src} -> {dst}")
        if dry_run:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        _drop_pycache(dst)
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="把官方书源迁入 novelbase/sources/builtin/")
    ap.add_argument("--apply", action="store_true", help="真正执行迁移（默认 dry-run）")
    ap.add_argument(
        "--sources-dir", default=str(DEFAULT_SOURCES_DIR), help="书源目录（默认仓库内）"
    )
    args = ap.parse_args(argv)

    moves = plan_moves(Path(args.sources_dir))
    if not moves:
        print("没有需要迁移的书源（已迁移或目录为空）")
        return 0

    lines = apply_moves(moves, dry_run=not args.apply)
    verb = "已迁移" if args.apply else "计划迁移"
    print(f"{verb} {len(lines)} 个书源：")
    for line in lines:
        print(f"  {line}")
    if not args.apply:
        print("\n这是 dry-run，磁盘未改动。确认无误后加 --apply 执行。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
