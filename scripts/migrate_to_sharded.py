#!/usr/bin/env python3
"""novels.db 单库 → 一小说一库 迁移脚本。

用法::

    python scripts/migrate_to_sharded.py
    python scripts/migrate_to_sharded.py --db app_data/storage/novels.db --base-dir app_data/storage
    python scripts/migrate_to_sharded.py --dry-run
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path


def migrate(db_path: str, base_dir: str, dry_run: bool = False) -> None:
    src_path = Path(db_path)
    if not src_path.exists():
        print(f"错误: 源库不存在 — {src_path}")
        sys.exit(1)

    dst_dir = Path(base_dir)

    src = sqlite3.connect(str(src_path))
    src.row_factory = sqlite3.Row

    # 读取所有小说
    novels = src.execute(
        "SELECT id, title, url, author, serial, description, tags, count "
        "FROM novels ORDER BY title"
    ).fetchall()

    if not novels:
        print("源库中没有小说数据，无需迁移。")
        src.close()
        return

    print(f"找到 {len(novels)} 本小说")
    if dry_run:
        for n in novels:
            print(f"  [{n['id']}] {n['title']} ({n['author']})")
        src.close()
        return

    dst_dir.mkdir(parents=True, exist_ok=True)

    for i, row in enumerate(novels, 1):
        novel_id = row["id"]
        novel_path = dst_dir / f"{novel_id}.db"
        print(f"[{i}/{len(novels)}] {row['title']} → {novel_path.name}")
        _migrate_novel(src, str(novel_path), novel_id)

    src.close()

    # 旧库改名
    bak_path = src_path.with_suffix(".db.bak")
    os.rename(str(src_path), str(bak_path))
    print(f"\n迁移完成。旧库已重命名为 {bak_path.name}")


def _migrate_novel(src: sqlite3.Connection, dst_path: str, novel_id: str) -> None:
    """把一本小说的所有数据从源库迁移到目标 .db。"""
    dst = sqlite3.connect(dst_path)
    dst.execute("PRAGMA journal_mode=WAL")
    dst.execute("PRAGMA foreign_keys=ON")
    _init_novel_db(dst)

    # meta
    row = src.execute(
        "SELECT id, title, url, author, serial, description, tags, count, created_at "
        "FROM novels WHERE id = ?", (novel_id,)
    ).fetchone()
    if row:
        dst.execute("""
            INSERT OR REPLACE INTO meta (id, title, url, author, serial,
                description, tags, count, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, tuple(row))

    # 封面（novel 类型插图）
    cover_rows = src.execute(
        "SELECT owner_type, owner_id, alt, url, insert_pos, raw_data, format "
        "FROM illustrations WHERE owner_type = 'novel' AND owner_id = ? "
        "ORDER BY insert_pos", (novel_id,)
    ).fetchall()
    for cr in cover_rows:
        dst.execute("""
            INSERT INTO illustrations (owner_type, owner_id, alt, url, insert_pos, raw_data, format)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, tuple(cr))

    # 章节
    chapters = src.execute(
        "SELECT id, url, title, \"order\", volume, content, time, count "
        "FROM chapters WHERE novel_id = ? ORDER BY \"order\"", (novel_id,)
    ).fetchall()
    for ch in chapters:
        dst.execute("""
            INSERT INTO chapters (id, url, title, "order", volume, content, time, count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, tuple(ch))

        # 章节插图
        ch_imgs = src.execute(
            "SELECT owner_type, owner_id, alt, url, insert_pos, raw_data, format "
            "FROM illustrations WHERE owner_type = 'chapter' AND owner_id = ? "
            "ORDER BY insert_pos", (ch["id"],)
        ).fetchall()
        for ci in ch_imgs:
            dst.execute("""
                INSERT INTO illustrations (owner_type, owner_id, alt, url, insert_pos, raw_data, format)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, tuple(ci))

    dst.commit()
    dst.close()


def _init_novel_db(conn: sqlite3.Connection) -> None:
    """初始化单本小说的库。"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meta (
            id          TEXT PRIMARY KEY,
            title       TEXT NOT NULL,
            url         TEXT NOT NULL,
            author      TEXT NOT NULL DEFAULT '',
            serial      INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            tags        TEXT NOT NULL DEFAULT '[]',
            count       INTEGER,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS chapters (
            id          TEXT PRIMARY KEY,
            url         TEXT NOT NULL,
            title       TEXT NOT NULL,
            "order"     INTEGER NOT NULL DEFAULT 0,
            volume      TEXT,
            content     TEXT,
            time        REAL,
            count       INTEGER
        );
        CREATE TABLE IF NOT EXISTS illustrations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_type  TEXT NOT NULL CHECK(owner_type IN ('novel','chapter')),
            owner_id    TEXT NOT NULL,
            alt         TEXT,
            url         TEXT NOT NULL,
            insert_pos  INTEGER,
            raw_data    BLOB,
            format      TEXT,
            UNIQUE(owner_type, owner_id, insert_pos)
        );
        CREATE INDEX IF NOT EXISTS idx_chapters_order
            ON chapters("order");
        CREATE INDEX IF NOT EXISTS idx_illustrations_owner
            ON illustrations(owner_type, owner_id);
    """)


def main():
    parser = argparse.ArgumentParser(description="novels.db → 一小说一库迁移")
    parser.add_argument("--db", default="app_data/storage/novels.db",
                        help="旧单库路径（默认 app_data/storage/novels.db）")
    parser.add_argument("--base-dir", default="app_data/storage",
                        help="输出目录（默认 app_data/storage）")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览，不实际写入")
    args = parser.parse_args()
    migrate(args.db, args.base_dir, args.dry_run)


if __name__ == "__main__":
    main()
