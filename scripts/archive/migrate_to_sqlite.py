#!/usr/bin/env python3
"""将本地 JSON 存储的所有小说迁移到 SQLite 数据库。

用法:
    python scripts/migrate_to_sqlite.py [--db sqlite:///app_data/storage/novels.db] [--dry-run]
"""

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from main import APP_DATA
from novelbase.core.storage import LocalStorage, SQLiteStorage, create_storage
from novelbase.core.options import StorageOptions
from novelbase.utils.logger import get_logger

_log = get_logger("migrate_to_sqlite")


def migrate(source_dir: Path, db_url: str, dry_run: bool = False):
    src = LocalStorage(source_dir)
    dst = SQLiteStorage(StorageOptions(
        backend="sqlite",
        database_url=db_url,
    ))

    total_novels = 0
    total_chapters = 0

    for novel in src.iter_metas():
        total_novels += 1
        print(f"\n[{total_novels}] {novel.title}  — {novel.author}  [{novel.id}]")

        if not dry_run:
            dst.save_meta(novel)

        chapters = src.load_chapters(novel.id)
        if not dry_run and chapters:
            dst.save_chapter(novel, chapters)

        n = len(chapters)
        total_chapters += n
        print(f"      {n} 章")

    action = "将会迁移" if dry_run else "已迁移"
    print(f"\n{action} {total_novels} 本小说, {total_chapters} 章 → {db_url}")


def main():
    p = argparse.ArgumentParser(description="本地 JSON → SQLite 迁移")
    p.add_argument("--db", default="sqlite:///app_data/storage/novels.db",
                   help="目标 SQLite 数据库路径 (默认: sqlite:///app_data/storage/novels.db)")
    p.add_argument("--source", default=str(APP_DATA / "storage"),
                   help="源 JSON 存储目录 (默认: app_data/storage)")
    p.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    args = p.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"源目录不存在: {source}")
        sys.exit(1)

    if args.dry_run:
        print("[DRY RUN] 预览模式\n")

    migrate(source, args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
